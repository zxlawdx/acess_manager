from dataclasses import replace
from uuid import uuid4
from threading import RLock
from typing import Optional

from apps.zte_manager.model.device_adapters import select_adapter
from apps.zte_manager.model.zte import ZTE
from apps.zte_manager.repositories.history_repository import history_repository
from apps.zte_manager.repositories.management_repository import (
    management_repository,
)
from apps.zte_manager.services.automatic_diagnostic_service import (
    AutomaticDiagnosticService,
    DiagnosticThresholds,
)
from apps.zte_manager.services.attendance_report_service import (
    AttendanceReportService,
)
from apps.zte_manager.services.capability_service import CapabilityService
from apps.zte_manager.services import multimodel_service
from apps.zte_manager.services import model_diagnostic_service
from apps.zte_manager.services import f6201b_capture
from apps.zte_manager.services.f6201b_writes import ExperimentalF6201BWrites, EXACT_FIRMWARE
from apps.zte_manager.services.f6201b_dns_writes import ExperimentalF6201BDNS
from apps.zte_manager.services.f6201b_profile import ExperimentalF6201BProfile
from apps.zte_manager.services.f6201b_diagnostics import F6201BDiagnostics, PING, TRACE
from apps.zte_manager.services.f6201b_support import run_f6201b_support
from apps.zte_manager.services import f6201b_dhcp
from apps.zte_manager.services.f6201b_workbench import CapturedFormWorkbench, catalog as captured_catalog
from apps.zte_manager.services.profile_service import profile_service
from apps.zte_manager.services.speed_test_service import SpeedTestService
from apps.zte_manager.services.support_diagnostic_service import (
    SupportDiagnosticOptions,
    SupportDiagnosticService,
)


class ZTEService:
    """
    Service Layer / Facade da aplicação.

    A API fala somente com este objeto. Ele mantém uma sessão única da ONT e
    serializa as operações com RLock porque o firmware depende do contexto:

        menuView -> menuData -> POST

    Duas requisições concorrentes poderiam trocar a view no meio do fluxo e
    causar SessionTimeout mesmo com o login ainda válido.
    """

    def __init__(self):
        self._zte: Optional[ZTE] = None
        self._lock = RLock()
        self.current_attendant = None
        self.current_host = None
        self._adapter = None
        self._capability_service = None
        self._history_session_id = None
        self._device_info = {}
        self._selected_model = None
        self._model_verified = False
        self._session_revision = uuid4().hex
        self._f6201b_writer = ExperimentalF6201BWrites()
        self._f6201b_dns = ExperimentalF6201BDNS()
        self._f6201b_profile = ExperimentalF6201BProfile()
        self._f6201b_diagnostics = F6201BDiagnostics()
        self._captured_workbench = CapturedFormWorkbench()
        self._readonly_original_post = None

    # =========================================================
    # CONEXÃO
    # =========================================================

    def connect(
        self,
        ip: str,
        username: str,
        password: str,
        https: bool = False,
        attendant: str | None = None,
        model_hint: str | None = None,
    ):
        with self._lock:
            # O zte_tracker documenta o mesmo desafio loginData para a
            # família Vue, porém seus endpoints de leitura usam vueData.
            # Nunca assumir que os menus de escrita ThinkLua sejam compatíveis.

            protocolo = "https" if https else "http"
            base_url = f"{protocolo}://{ip}"

            # Trocar somente o atendente na UI não deve derrubar a sessão da
            # ONT. O firmware costuma aceitar uma sessão administrativa por
            # vez; enviar logout/login desnecessariamente também expulsa uma
            # aba da interface original aberta no navegador.
            if (
                self._zte is not None
                and self._zte.base_url == base_url
                and self._zte.username == username
                and self._zte.password == password
            ):
                self.current_attendant = (
                    attendant.strip()
                    if attendant and attendant.strip()
                    else self.current_attendant
                    or "default"
                )

                # Um novo clique em Conectar pode trazer outra escolha
                # manual para o MESMO endereço. Não preservar a identidade
                # anterior sem revalidar o equipamento.
                actual = {}
                try:
                    actual = self._zte.device_status() or {}
                except Exception:
                    pass
                claimed, _ = multimodel_service.find_family(model_hint)
                detected, _ = multimodel_service.find_family(
                    actual.get("modelo") or ""
                )
                if claimed and detected and claimed != detected:
                    raise ValueError(
                        "O modelo escolhido diverge da identificação atual "
                        "do equipamento; escolha o modelo detectado."
                    )
                if claimed and self._selected_model:
                    selected, _ = multimodel_service.find_family(
                        self._selected_model
                    )
                    if selected and claimed != selected and not detected:
                        raise ValueError(
                            "Não foi possível confirmar uma troca de modelo "
                            "reutilizando a sessão. Desconecte e reconecte."
                        )
                if detected:
                    previous, _ = multimodel_service.find_family(self._selected_model)
                    if previous and previous != detected:
                        # A mesma porta HTTP pode apontar para outra ONT
                        # (proxy/VPN redirecionado). A sessão antiga precisa
                        # ser encerrada e o adaptador criado novamente.
                        raise ValueError(
                            "O equipamento conectado mudou desde o login "
                            "anterior. Desconecte e conecte novamente para "
                            "recriar o adaptador correto."
                        )
                    self._device_info = actual
                    self._selected_model = detected
                    self._model_verified = True
                elif actual:
                    # Não substituir dados válidos por uma resposta parcial.
                    self._device_info.update({
                        k: v for k, v in actual.items() if v is not None
                    })
                self.current_host = ip

                return {
                    "success": True,
                    "writes_enabled": getattr(self._zte, "writes_enabled", True),
                    "attendant": self.current_attendant,
                    "host": self.current_host,
                    "reused_session": True,
                    "model": self._selected_model,
                    "model_verified": self._model_verified,
                    "session_revision": self._session_revision,
                    "device": self._device_info,
                    "adapter": (
                        self._adapter.name
                        if self._adapter
                        else None
                    ),
                }

            # Para trocar de equipamento/credencial fechamos somente o socket
            # local. Não chamamos logout remoto automaticamente porque isso
            # pode invalidar a sessão administrativa que o atendente mantém
            # aberta na própria interface da ZTE. O botão Desconectar continua
            # executando logout explícito quando essa for a intenção.
            if self._zte is not None:
                history_repository.end_session(
                    self._history_session_id
                )

                try:
                    self._zte.session.close()
                except Exception:
                    pass

            self._f6201b_writer.clear()
            self._f6201b_dns.clear()
            self._f6201b_profile.clear()
            self._captured_workbench.clear()
            self._readonly_original_post = None
            self._session_revision = uuid4().hex
            self._model_verified = False
            self._selected_model = None
            self._device_info = {}
            self._zte = ZTE(
                ip=ip,
                username=username,
                password=password,
                https=https
            )

            resposta = self._zte.login()

            if not resposta:
                self._zte = None

                raise RuntimeError(
                    "Não foi possível autenticar na ONT."
                )

            self.current_attendant = (
                attendant.strip()
                if attendant and attendant.strip()
                else "default"
            )

            self.current_host = ip

            # DeviceAdapter é escolhido uma vez por sessão. Se uma leitura de
            # status não estiver disponível para esse login, o fallback
            # ThinkLua continua funcional e o probe decide recurso por recurso.
            # Vue (AX3000/BE7200) não responde menuView/statusMgr como os
            # firmwares ThinkLua. Não trocar o contexto da sessão recém
            # autenticada antes da primeira consulta vueData.
            _, hinted_family = multimodel_service.find_family(model_hint)
            if hinted_family == "vue":
                self._device_info = {"modelo": model_hint}
            else:
                try:
                    self._device_info = self._zte.device_status()
                except Exception:
                    self._device_info = {}

            detected_model = self._device_info.get("modelo")
            if model_hint and detected_model:
                from apps.zte_manager.services.multimodel_service import find_family
                claimed, _ = find_family(model_hint)
                actual, _ = find_family(detected_model)
                if claimed and actual and claimed != actual:
                    self._zte.session.close()
                    self._zte = None
                    raise ValueError(
                        "Modelo informado diverge do modelo retornado "
                        "pelo equipamento. Verifique o perfil selecionado."
                    )

            # Vários firmwares retornam apenas "ZTE", sem modelo. Nesses
            # casos respeitamos o perfil escolhido, sem fingir confirmação.
            from apps.zte_manager.services.multimodel_service import find_family
            known_detected, _ = find_family(detected_model)
            selected_model = (
                detected_model if known_detected or not model_hint
                else model_hint
            )
            self._adapter = select_adapter(
                selected_model,
                self._device_info.get("firmware"),
            )
            self._selected_model = selected_model
            self._model_verified = bool(known_detected)
            # Somente os adaptadores originais possuem rotinas de escrita
            # implementadas/testadas; os novos perfis iniciam read-only.
            from apps.zte_manager.model.device_adapters import (
                F6600PAdapter, F670LAdapter,
            )
            # Modelos sem identificação confirmada permanecem READ ONLY.
            self._zte.writes_enabled = isinstance(
                self._adapter,
                (F6600PAdapter, F670LAdapter),
            ) and bool(detected_model or model_hint)

            if not self._zte.writes_enabled:
                # Defesa em profundidade: as APIs de alguns firmwares
                # usam POST direto fora de post_menu (backup, reboot etc.).
                # Bloquear no transporte evita que um botão antigo faça
                # alterações por acidente no equipamento recém-cadastrado.
                def read_only_post(*args, **kwargs):
                    raise PermissionError(
                        "Sessão de descoberta somente leitura. "
                        "POST bloqueado até existir adaptador de escrita validado."
                    )

                self._readonly_original_post = self._zte.session.post
                self._zte.session.post = read_only_post

            self._capability_service = CapabilityService(
                self._zte,
                self._adapter,
            )

            self._history_session_id = (
                history_repository.start_session(
                    host=self.current_host,
                    attendant=self.current_attendant,
                    device=self._device_info,
                )
            )

            history_repository.save_snapshot(
                self._history_session_id,
                "connect",
                {
                    "device": self._device_info,
                    "adapter": self._adapter.describe(),
                },
            )

            # Registro leve imediato: a ONT já aparece no inventário ao
            # conectar. A sincronização completa (óptico/config/capabilities)
            # pode ser executada na área de gerenciamento.
            try:
                serial = (
                    self._device_info.get("serial")
                    or self._device_info.get("serial_number")
                    or self._device_info.get("sn")
                    or self._device_info.get("SerialNumber")
                )

                mac = (
                    self._device_info.get("mac")
                    or self._device_info.get("mac_address")
                    or self._device_info.get("MACAddress")
                )

                management_repository.upsert_device({
                    "key": (
                        serial
                        or mac
                        or self.current_host
                    ),
                    "host": self.current_host,
                    "model": (
                        self._device_info.get("modelo")
                        or self._device_info.get("model")
                    ),
                    "serial": serial,
                    "mac": mac,
                    "firmware": (
                        self._device_info.get("firmware")
                        or self._device_info.get("software")
                    ),
                    "status": "online",
                    "metadata": {
                        "device": self._device_info,
                        "adapter": self._adapter.name,
                        "attendant": self.current_attendant,
                    },
                })
            except Exception:
                # Inventário não pode impedir o atendimento/login.
                pass

            return {
                "success": True,
                "attendant": self.current_attendant,
                "host": self.current_host,
                "reused_session": False,
                "model": self._selected_model,
                "model_verified": self._model_verified,
                "session_revision": self._session_revision,
                "writes_enabled": self._zte.writes_enabled,
                "device": self._device_info,
                "adapter": self._adapter.name,
            }

    def disconnect(self):
        with self._lock:
            if self._zte is None:
                return

            # Encerramos somente a sessão HTTP local. Não chamamos
            # logout_entry automaticamente: alguns firmwares ZTE trabalham
            # com uma única sessão administrativa e um logout remoto pode
            # derrubar também a aba original do equipamento que o atendente
            # deixou aberta no navegador.
            try:
                history_repository.end_session(
                    self._history_session_id
                )

                self._zte.session.close()
            finally:
                self._zte = None
                self.current_host = None
                self.current_attendant = None
                self._adapter = None
                self._capability_service = None
                self._history_session_id = None
                self._device_info = {}
                self._selected_model = None
                self._model_verified = False
                self._session_revision = uuid4().hex
                self._f6201b_writer.clear()
                self._f6201b_dns.clear()
                self._f6201b_profile.clear()
                self._captured_workbench.clear()
                self._readonly_original_post = None

    def get_client(self) -> ZTE:
        if self._zte is None:
            raise RuntimeError(
                "Nenhuma ONT ZTE conectada."
            )

        return self._zte

    @property
    def connected(self) -> bool:
        return self._zte is not None

    def _capabilities(self) -> CapabilityService:
        if self._capability_service is None:
            raise RuntimeError(
                "A capability service ainda não foi inicializada."
            )

        return self._capability_service

    @staticmethod
    def _safe_capture(reader):
        try:
            return reader()
        except Exception as error:
            return {
                "_error": str(error),
            }

    def _run_change(
        self,
        *,
        operation,
        target,
        before_reader,
        action,
        after_reader=None,
    ):
        """
        Template Method de auditoria.

        Toda escrita nova passa pelo mesmo before -> action -> after e grava
        sucesso/falha no Repository. Isso evita cópia de try/except por feature.
        """
        before = self._safe_capture(
            before_reader
        )

        try:
            result = action()
        except Exception as error:
            history_repository.save_change(
                self._history_session_id,
                operation=operation,
                target=target,
                before=before,
                after=None,
                success=False,
                message=str(error),
            )
            raise

        after = self._safe_capture(
            after_reader or before_reader
        )

        history_repository.save_change(
            self._history_session_id,
            operation=operation,
            target=target,
            before=before,
            after=after,
            success=True,
        )

        return result

    def _audit_device_command(self, operation, target, command):
        """Audit direct F6201B commands which do not use _run_change.

        Record operation and confirmation status, never router data, raw
        credentials, passwords or unfiltered exception strings.
        """
        try:
            outcome = command()
        except Exception as exc:
            history_repository.save_change(
                self._history_session_id, operation=operation,
                target=target, before=None, after=None, success=False,
                message=type(exc).__name__,
            )
            raise
        ok = isinstance(outcome, dict) and outcome.get("success") is True
        summary = {
            "verified": outcome.get("verified", False)
            if isinstance(outcome, dict) else False,
            "noop": outcome.get("noop", False)
            if isinstance(outcome, dict) else False,
            "uncertain": outcome.get("uncertain", False)
            if isinstance(outcome, dict) else False,
        }
        if isinstance(outcome, dict):
            summary["stages"] = [
                {"name": str(step.get("name", ""))[:80],
                 "verified": bool(step.get("verified", step.get("success", False)))}
                for step in outcome.get("steps", [])
                if isinstance(step, dict)
            ][:32]
            summary["fields"] = [
                str(field)[:80] for field in (
                    outcome.get("changed_fields")
                    or outcome.get("verified_fields")
                    or []
                )
                if not any(word in str(field).lower()
                           for word in ("pass", "secret", "token", "key"))
            ][:64]
        history_repository.save_change(
            self._history_session_id, operation=operation,
            target=target, before=None, after=summary, success=ok,
            message=None if ok else "device_result_not_confirmed",
        )
        return outcome

    def _snapshot_payload(self):
        zte = self.get_client()

        readers = {
            "device": zte.device_status,
            "optical": zte.optical_status,
            "wan": zte.wan_status,
            "lan_ports": zte.lan_ports,
            "wifi_radios": zte.channel_status,
            "wifi_networks": lambda: zte.wifi_networks(
                reveal_password=False
            ),
            "dns": zte.dns_status,
        }

        return {
            name: self._safe_capture(reader)
            for name, reader in readers.items()
        }

    def security_status(self):
        with self._lock:
            zte = self.get_client()

            # Não retornamos token nem chave pública completa. A rota existe
            # apenas para confirmar se o contexto necessário aos POSTs foi
            # carregado corretamente após o login/menuView.
            return {
                "session_tmp_token": bool(
                    zte.session_tmp_token
                ),
                "public_key": bool(
                    zte.public_key_pem
                ),
                "integrity_check": zte.integrity_check,
                "source": zte.security_source,
            }

    # =========================================================
    # DEVICE
    # =========================================================

    def device_status(self):
        with self._lock:
            result = self.get_client().device_status()

            if isinstance(result, dict):
                self._device_info = result

            return result

    def optical_status(self):
        with self._lock:
            return self.get_client().optical_status()

    def account_status(self):
        with self._lock:
            return self.get_client().account_status()

    def export_user_configuration(self):
        with self._lock:
            zte = self.get_client()

            result = zte.export_user_configuration(
                device=self._device_info
            )

            history_repository.save_change(
                self._history_session_id,
                operation="backup_configuration",
                target=result.get("filename"),
                before=None,
                after={
                    "path": result.get("path"),
                    "size": result.get("size"),
                },
                success=True,
                message="Backup local exportado.",
            )

            return result

    def change_admin_password(
        self,
        new_password
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="admin_password",
                target=self.current_host,
                before_reader=zte.account_status,
                action=lambda: zte.change_admin_password(
                    new_password
                ),
                after_reader=zte.account_status,
            )

    def reboot(self):
        with self._lock:
            resultado = self.get_client().reboot()

            # Depois de Restart não existe mais uma sessão útil. Não enviamos
            # logout: o equipamento está reiniciando e a conexão cairá sozinha.
            history_repository.end_session(
                self._history_session_id
            )

            self._zte = None
            self.current_host = None
            self._adapter = None
            self._capability_service = None
            self._history_session_id = None

            return resultado

    # =========================================================
    # WAN / PPPOE
    # =========================================================

    def wan_status(self):
        with self._lock:
            return self.get_client().wan_status()

    def pppoe_status(
        self,
        reveal_password=False
    ):
        with self._lock:
            return self.get_client().pppoe_status(
                reveal_password=reveal_password
            )

    # =========================================================
    # CLIENTES
    # =========================================================

    def _multimodel_client_family(self):
        _, family = multimodel_service.find_family(
            self._selected_model
        )
        # A família F6640 reutiliza os mesmos menus da F6600P/F670L.
        return family if family in {"h288a", "h388x", "h2640", "vue",
                                    "f6201b_candidate"} else None

    def wifi_clients(self):
        with self._lock:
            family = self._multimodel_client_family()
            if family:
                return multimodel_service.read_clients(
                    self.get_client(), self._selected_model, "wifi_clients"
                )
            return self.get_client().wifi_clients()

    def lan_clients(self):
        with self._lock:
            family = self._multimodel_client_family()
            if family == "f6201b_candidate":
                # Captura comprova DHCP leases e tabela ARP, não usuários
                # Ethernet ativos. Evitar falso positivo de cliente online.
                return []
            if family:
                return multimodel_service.read_clients(
                    self.get_client(), self._selected_model, "lan_clients"
                )
            return self.get_client().lan_clients()

    def lan_ports(self):
        with self._lock:
            return self.get_client().lan_ports()

    def all_clients(self):
        with self._lock:
            zte = self.get_client()

            return {
                "wifi": self.wifi_clients(),
                "lan": self.lan_clients()
            }

    # =========================================================
    # WIFI
    # =========================================================

    def wifi_networks(
        self,
        reveal_password=False
    ):
        with self._lock:
            return self.get_client().wifi_networks(
                reveal_password=reveal_password
            )

    def set_ssid_config(
        self,
        ssid_id,
        config
    ):
        with self._lock:
            zte = self.get_client()
            reader = lambda: zte.wifi_networks(
                reveal_password=False
            )

            return self._run_change(
                operation="ssid_update",
                target=ssid_id,
                before_reader=reader,
                action=lambda: zte.set_ssid_config(
                    ssid_id,
                    config
                ),
                after_reader=reader,
            )

    def wifi_radios(self):
        with self._lock:
            return self.get_client().channel_status()

    def wifi_channels(
        self,
        band: str | None = None,
        bandwidth: str | None = None,
        country: str = "BRI"
    ):
        with self._lock:
            return self.get_client().available_channels(
                band=band,
                bandwidth=bandwidth,
                country=country
            )

    def set_wifi_radio(
        self,
        band,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="wifi_radio_update",
                target=band,
                before_reader=zte.channel_status,
                action=lambda: zte.set_radio_config(
                    band,
                    config
                ),
                after_reader=zte.channel_status,
            )

    # =========================================================
    # ADVANCED / FEATURE CONTROLS
    # =========================================================

    def radio_power_status(self):
        with self._lock:
            return self.get_client().radio_power_status()

    def set_radio_power(
        self,
        band,
        enabled
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="wifi_radio_power",
                target=band,
                before_reader=zte.radio_power_status,
                action=lambda: zte.set_radio_power(
                    band,
                    enabled
                ),
                after_reader=zte.radio_power_status,
            )

    def wifi_schedule_status(self):
        with self._lock:
            return self.get_client().wifi_schedule_status()

    def set_wifi_schedule(
        self,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="wifi_schedule",
                target="wifi",
                before_reader=zte.wifi_schedule_status,
                action=lambda: zte.set_wifi_schedule(config),
            )

    def wps_status(self):
        with self._lock:
            return self.get_client().wps_status()

    def set_wps(
        self,
        band,
        mode
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="wps_update",
                target=band,
                before_reader=zte.wps_status,
                action=lambda: zte.set_wps(
                    band,
                    mode
                ),
                after_reader=zte.wps_status,
            )

    def upnp_status(self):
        with self._lock:
            return self.get_client().upnp_status()

    def set_upnp(
        self,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="upnp_update",
                target="upnp",
                before_reader=zte.upnp_status,
                action=lambda: zte.set_upnp(
                    config
                ),
                after_reader=zte.upnp_status,
            )

    def mesh_status(self):
        with self._lock:
            return self.get_client().mesh_status()

    def configure_mesh(
        self,
        config,
        *,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="easymesh_configure",
                target="wifi_mesh",
                before_reader=zte.mesh_status,
                action=lambda: zte.configure_mesh(
                    config
                ),
                after_reader=zte.mesh_status,
            )

    def start_mesh_pairing(
        self,
        *,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="easymesh_pairing",
                target="wifi_mesh",
                before_reader=zte.mesh_status,
                action=zte.start_mesh_pairing,
                after_reader=zte.mesh_status,
            )

    def band_steering_status(self):
        with self._lock:
            return self.get_client().band_steering_status()

    def set_band_steering(
        self,
        enabled
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="band_steering_toggle",
                target="wifi",
                before_reader=zte.band_steering_status,
                action=lambda: zte.set_band_steering(
                    enabled
                ),
            )

    def configure_band_steering(
        self,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="band_steering_parameters",
                target="wifi",
                before_reader=zte.band_steering_status,
                action=lambda: zte.configure_band_steering(
                    config
                ),
            )

    # =========================================================
    # DHCP / NAT
    # =========================================================

    def _is_captured_f6201b(self):
        detected, _ = multimodel_service.find_family(
            self._device_info.get("modelo") or ""
        )
        return detected == "F6201B"

    def dhcp_status(self):
        with self._lock:
            if self._is_captured_f6201b():
                self._f6201b_write_firmware()
                return f6201b_dhcp.status(self.get_client())
            return self.get_client().dhcp_status()

    def set_dhcp_basic(self, config):
        with self._lock:
            if self._is_captured_f6201b():
                self._f6201b_write_firmware()
                return self._audit_device_command(
                    "dhcp_basic", "LAN / DHCP",
                    lambda: f6201b_dhcp.change(
                        self._captured_workbench, self.get_client(),
                        config=config, host=self.current_host,
                        revision=self._session_revision,
                        attendant=self.current_attendant,
                        original_post=self._readonly_original_post,
                    ),
                )
            zte = self.get_client()
            return self._run_change(
                operation="dhcp_basic", target="lan",
                before_reader=zte.dhcp_status,
                action=lambda: zte.set_dhcp_basic(config),
            )

    def save_dhcp_reservation(
        self,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="dhcp_reservation_save",
                target=config.get("id") or config.get("mac"),
                before_reader=zte.dhcp_status,
                action=lambda: zte.save_dhcp_reservation(
                    config
                ),
            )

    def delete_dhcp_reservation(
        self,
        instance_id
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="dhcp_reservation_delete",
                target=instance_id,
                before_reader=zte.dhcp_status,
                action=lambda: zte.delete_dhcp_reservation(
                    instance_id
                ),
            )

    def port_forwarding_status(self):
        with self._lock:
            return self.get_client().port_forwarding_status()

    def save_port_forward(
        self,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="port_forward_save",
                target=config.get("id") or config.get("name"),
                before_reader=zte.port_forwarding_status,
                action=lambda: zte.save_port_forward(
                    config
                ),
            )

    def delete_port_forward(
        self,
        instance_id,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="port_forward_delete",
                target=instance_id,
                before_reader=zte.port_forwarding_status,
                action=lambda: zte.delete_port_forward(
                    instance_id
                ),
            )

    def dmz_status(self):
        with self._lock:
            return self.get_client().dmz_status()

    def set_dmz(
        self,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="dmz",
                target=config.get("internal_client") or "dmz",
                before_reader=zte.dmz_status,
                action=lambda: zte.set_dmz(
                    config
                ),
            )

    # =========================================================
    # CAPABILITIES / INSPEÇÃO SEGURA
    # =========================================================

    def capability_catalog(self):
        with self._lock:
            return self._capabilities().catalog()

    def probe_capabilities(
        self,
        features=None
    ):
        with self._lock:
            return self._capabilities().probe(
                features
            )

    def multimodel_catalog(self):
        return multimodel_service.catalog()

    def _confirmed_probe_model(self, requested=None):
        """Não sondar endpoints de OUTRA família no equipamento conectado."""
        detected = (
            self._device_info.get("modelo")
            or self._device_info.get("model")
            or ""
        )
        confirmed, confirmed_family = multimodel_service.find_family(detected)
        selected, selected_family = multimodel_service.find_family(
            self._selected_model
        )
        proposed, proposed_family = multimodel_service.find_family(requested)
        if requested and confirmed and (
            proposed != confirmed or proposed_family != confirmed_family
        ):
            raise ValueError(
                "O perfil solicitado não corresponde ao modelo identificado "
                "pelo equipamento. Reconecte escolhendo o perfil correto."
            )
        if requested and (
            (
                selected and (
                    proposed != selected or proposed_family != selected_family
                )
            )
            or (
                not selected and self._selected_model
                and multimodel_service.normalize_model(requested)
                != multimodel_service.normalize_model(self._selected_model)
            )
        ):
            raise ValueError(
                "O perfil solicitado difere do escolhido na conexão. "
                "Reconecte para alterar o modelo."
            )
        return self._selected_model or detected or requested or ""

    def multimodel_mesh(self, model=None):
        with self._lock:
            selected = self._confirmed_probe_model(model)
            return multimodel_service.mesh_summary(
                self.get_client(), selected
            )

    def multimodel_probe(self, model=None, max_endpoints=4, start=0):
        with self._lock:
            selected = self._confirmed_probe_model(model)
            return multimodel_service.probe(
                self.get_client(), selected,
                max_endpoints=max_endpoints,
                start=start,
            )

    def multimodel_diagnostic(self, model=None, section=None):
        with self._lock:
            selected = self._confirmed_probe_model(model)
            return model_diagnostic_service.diagnostic(
                self.get_client(), selected, section=section,
            )

    def _f6201b_write_firmware(self):
        """Hardware/firmware compatibility, never an employee permissions gate.

        Selection in a dropdown is not proof of capabilities; the authenticated
        device status is authoritative and rechecked for captured POSTs.
        """
        device = self.get_client().device_status()
        detected, _ = multimodel_service.find_family(
            device.get("modelo") or ""
        )
        if detected != "F6201B":
            raise ValueError(
                "A ONT não confirmou suporte ao adaptador F6201B."
            )
        firmware = device.get("firmware")
        if firmware != EXACT_FIRMWARE:
            raise ValueError(
                "Este firmware requer seu próprio mapeamento de comandos."
            )
        return firmware

    def f6201b_write_status(self):
        with self._lock:
            detected, _ = multimodel_service.find_family(
                self._device_info.get("modelo") or ""
            )
            if detected != "F6201B":
                raise ValueError("A ONT conectada não foi identificada como F6201B.")
            return self._f6201b_writer.capabilities(
                self._device_info.get("firmware")
            )

    def f6201b_write_ssids(self):
        with self._lock:
            self._f6201b_write_firmware()
            return self._f6201b_writer.list_ssids(self.get_client())

    def f6201b_write_preview(self, ssid_id, config):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            return self._f6201b_writer.preview(
                self.get_client(), host=self.current_host,
                firmware=firmware, ssid_id=ssid_id, config=config,
            )

    def f6201b_write_apply(self, nonce, confirmation):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            return self._f6201b_writer.apply(
                self.get_client(), host=self.current_host,
                firmware=firmware, nonce=nonce, confirmation=confirmation,
                original_post=self._readonly_original_post,
            )

    def f6201b_wan_summary(self):
        """WAN local para cartões antigos; nunca salvar credenciais."""
        with self._lock:
            self._f6201b_write_firmware()
            endpoint = multimodel_service.FAMILY[
                "f6201b_candidate"]["wan"]
            zte = self.get_client()
            raw = multimodel_service._fetch(zte, endpoint)
            multimodel_service._shape(raw, endpoint.root)
            records = zte._parse_instances(raw).get(
                "ID_WAN_COMFIG", []
            )
            # Campos observados no segundo GET status, sem UserName,
            # Password, serial/MAC ou dados de provisionamento.
            return [{
                "id": row.get("_InstID"),
                "nome": row.get("WANCName"),
                "status": row.get("ConnStatus"),
                "wan_type": row.get("TransType"),
                "ip": row.get("IPAddress"),
                "gateway": row.get("GateWay"),
                "vlan": row.get("VLANID"),
                "mtu": row.get("MTU"),
                "dns1": row.get("DNS1"),
                "dns2": row.get("DNS2"),
                "nat": row.get("IsNAT"),
                "uptime": row.get("UpTime"),
                "rx_bytes": row.get("RxBytes"),
                "tx_bytes": row.get("TxBytes"),
                "rx_errors": row.get("ErrorsReceived"),
                "tx_errors": row.get("ErrorsSent"),
            } for row in records[:12]]

    def f6201b_dns_status(self):
        with self._lock:
            self._f6201b_write_firmware()
            return self._f6201b_dns.read(self.get_client())

    def f6201b_dns_preview(self, changes):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            return self._f6201b_dns.preview(
                self.get_client(), host=self.current_host,
                firmware=firmware, changes=changes
            )

    def f6201b_dns_apply(self, nonce, confirmation):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            return self._f6201b_dns.apply(
                self.get_client(), host=self.current_host,
                firmware=firmware, nonce=nonce,
                confirmation=confirmation,
                original_post=self._readonly_original_post,
            )

    def f6201b_profile_preview(self, attendant):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            # "attendant" chooses a saved preset; it is not a permission role.
            return self._f6201b_profile.preview(
                self.get_client(), host=self.current_host,
                revision=self._session_revision, firmware=firmware,
                profile=profile_service.get_profile(attendant),
                dns_adapter=self._f6201b_dns,
            )

    def f6201b_profile_apply(self, nonce, confirmation):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            return self._f6201b_profile.apply(
                self.get_client(), host=self.current_host,
                revision=self._session_revision, firmware=firmware,
                nonce=nonce, confirmation=confirmation,
                original_post=self._readonly_original_post,
                dns_adapter=self._f6201b_dns,
            )

    def f6201b_profile_apply_saved(self, attendant):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            return self._audit_device_command(
                "f6201b_profile_apply", "Wi-Fi 2.4/5 GHz e DNS",
                lambda: self._f6201b_profile.apply_saved(
                    self.get_client(), host=self.current_host,
                    revision=self._session_revision, firmware=firmware,
                    profile=profile_service.get_profile(attendant),
                    original_post=self._readonly_original_post,
                    dns_adapter=self._f6201b_dns,
                ),
            )

    def f6201b_ssid_update(self, ssid_id, config):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            return self._audit_device_command(
                "f6201b_ssid_update", "SSID",
                lambda: self._f6201b_writer.apply_changes(
                    self.get_client(), host=self.current_host, firmware=firmware,
                    ssid_id=ssid_id, config=config,
                    original_post=self._readonly_original_post,
                ),
            )

    def f6201b_dns_update(self, changes):
        with self._lock:
            firmware = self._f6201b_write_firmware()
            return self._audit_device_command(
                "f6201b_dns_update", "DNS",
                lambda: self._f6201b_dns.apply_changes(
                    self.get_client(), host=self.current_host,
                    firmware=firmware, changes=changes,
                    original_post=self._readonly_original_post,
                ),
            )

    def captured_workbench_update(self, tag, instance_id, changes):
        with self._lock:
            self._f6201b_write_firmware()
            return self._audit_device_command(
                "f6201b_form_update", str(tag)[:95],
                lambda: self._captured_workbench.apply_changes(
                    self.get_client(), tag=tag, instance_id=instance_id,
                    changes=changes, host=self.current_host,
                    revision=self._session_revision,
                    attendant=self.current_attendant,
                    original_post=self._readonly_original_post,
                ),
            )

    # Comandos capturados com Strategy específica por formulário.
    # Estas rotas preservam o transporte read-only salvo na conexão.
    def captured_workbench_catalog(self):
        return captured_catalog()

    def captured_workbench_inspect(self, tag):
        with self._lock:
            self._f6201b_write_firmware()
            return self._captured_workbench.inspect(self.get_client(), tag)

    def captured_workbench_preview(self, tag, instance_id, changes):
        with self._lock:
            self._f6201b_write_firmware()
            return self._captured_workbench.preview(
                self.get_client(), tag=tag, instance_id=instance_id,
                changes=changes, host=self.current_host,
                revision=self._session_revision,
                attendant=self.current_attendant,
            )

    def captured_workbench_apply(self, nonce, confirmation, risk_ack):
        with self._lock:
            self._f6201b_write_firmware()
            return self._captured_workbench.apply(
                self.get_client(), host=self.current_host,
                revision=self._session_revision,
                attendant=self.current_attendant, nonce=nonce,
                confirmation=confirmation, risk_ack=risk_ack,
                original_post=self._readonly_original_post,
            )

    def mapped_f6201b_routes(self):
        # Catálogo local, não depende da sessão nem consulta o equipamento.
        return f6201b_capture.catalog()

    def inspect_mapped_f6201b_route(self, tag):
        with self._lock:
            selected = self._confirmed_probe_model()
            model, _ = multimodel_service.find_family(selected)
            if model != "F6201B":
                raise ValueError(
                    "A inspeção capturada somente está habilitada em F6201B."
                )
            return f6201b_capture.inspect(self.get_client(), tag)

    def capability_shape(self, feature):
        with self._lock:
            return self._capabilities().shape(feature)

    def read_capability(
        self,
        feature
    ):
        with self._lock:
            return self._capabilities().read(
                feature
            )

    # =========================================================
    # DNS
    # =========================================================

    def dns_status(self):
        with self._lock:
            return self.get_client().dns_status()

    def set_dns(self, config):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="dns_update",
                target="dns",
                before_reader=zte.dns_status,
                action=lambda: zte.set_dns(
                    config
                ),
                after_reader=zte.dns_status,
            )

    # =========================================================
    # DIAGNÓSTICOS
    # =========================================================

    def _captured_diagnostic(self, tag, config):
        if self._f6201b_write_firmware() != EXACT_FIRMWARE:
            raise ValueError("O firmware não expôs o diagnóstico capturado.")
        return self._f6201b_diagnostics.execute(
            self.get_client(), self._readonly_original_post, tag, config,
        )

    def ping(self, config):
        with self._lock:
            detected, _ = multimodel_service.find_family(
                self._device_info.get("modelo") or ""
            )
            if detected == "F6201B":
                return self._captured_diagnostic(PING, config)
            return self.get_client().ping(config)

    def traceroute(self, config):
        with self._lock:
            detected, _ = multimodel_service.find_family(
                self._device_info.get("modelo") or ""
            )
            if detected == "F6201B":
                return self._captured_diagnostic(TRACE, config)
            return self.get_client().traceroute(config)

    # =========================================================
    # DIAGNÓSTICO AUTOMÁTICO / HISTÓRICO
    # =========================================================

    @staticmethod
    def _diagnostic_thresholds(
        config
    ):
        return DiagnosticThresholds(
            optical_rx_min=config.get(
                "optical_rx_min",
                -27.0
            ),
            optical_rx_max=config.get(
                "optical_rx_max",
                -8.0
            ),
            wifi_rssi_warning=config.get(
                "wifi_rssi_warning",
                -70
            ),
            wifi_rssi_bad=config.get(
                "wifi_rssi_bad",
                -80
            ),
            expected_lan_mbps=config.get(
                "expected_lan_mbps",
                1000
            ),
            ping_warning_ms=config.get(
                "ping_warning_ms",
                80.0
            ),
        )

    @staticmethod
    def _support_options(
        config
    ):
        return SupportDiagnosticOptions(
            mode=config.get(
                "mode",
                "general"
            ),
            affected_mac=config.get(
                "affected_mac"
            ),
            affected_ip=config.get(
                "affected_ip"
            ),
            ping_host=config.get(
                "ping_host",
                "1.1.1.1"
            ),
            dns_host=config.get(
                "dns_host",
                "cloudflare.com"
            ),
            include_traceroute=config.get(
                "include_traceroute",
                False
            ),
            include_speedtest=config.get(
                "include_speedtest",
                True
            ),
            allow_speedtest_fallback=config.get(
                "allow_speedtest_fallback",
                True
            ),
            speedtest_provider=config.get(
                "speedtest_provider",
                "native_auto"
            ),
            speedtest_base_url=config.get(
                "speedtest_base_url"
            ),
            expected_download_mbps=config.get(
                "expected_download_mbps"
            ),
            expected_upload_mbps=config.get(
                "expected_upload_mbps"
            ),
        )

    def automatic_diagnostic(
        self,
        config
    ):
        with self._lock:
            thresholds = self._diagnostic_thresholds(
                config
            )

            result = AutomaticDiagnosticService(
                self.get_client()
            ).run(
                ping_host=config.get(
                    "ping_host",
                    "8.8.8.8"
                ),
                include_traceroute=config.get(
                    "include_traceroute",
                    False
                ),
                thresholds=thresholds,
            )

            diagnostic_id = (
                history_repository.save_diagnostic(
                    self._history_session_id,
                    result,
                )
            )

            history_repository.save_snapshot(
                self._history_session_id,
                "automatic_diagnostic",
                result.get("sections", {}),
            )

            return {
                **result,
                "history_id": diagnostic_id,
            }

    def f6201b_support_diagnostic(self, config):
        """Run the original full support form against the actual F6201B.

        Checkboxes control actual, independently measured operations;
        unsupported firmware actions produce an explicit error, not an
        uncheckable visual control or an invented successful result.
        """
        with self._lock:
            firmware = self._f6201b_write_firmware()
            def get_section(section):
                return model_diagnostic_service.diagnostic(
                    self.get_client(), "F6201B", section=section
                )
            def active(tag, params):
                return self._f6201b_diagnostics.execute(
                    self.get_client(), self._readonly_original_post,
                    tag, params,
                )
            def measure(payload):
                return SpeedTestService(self.get_client()).run(
                    provider=payload.get("speedtest_provider", "native_auto"),
                    allow_fallback=payload.get("allow_speedtest_fallback", True),
                    fallback_base_url=payload.get("speedtest_base_url"),
                )
            def optimize():
                # Auto-channel is the mapped and captured Wi-Fi command.
                # The operation touches neither passwords nor the saved
                # technician preset and requires an explicit checkbox.
                return self._audit_device_command(
                    "wifi_auto_optimization", "Wi-Fi 2.4/5 GHz",
                    lambda: self._f6201b_profile.apply_saved(
                        self.get_client(), host=self.current_host,
                        revision=self._session_revision, firmware=firmware,
                        profile={"wifi": {
                            "2.4GHz": {"auto_channel": True},
                            "5GHz": {"auto_channel": True},
                        }, "dns": {}},
                        original_post=self._readonly_original_post,
                        dns_adapter=self._f6201b_dns,
                    ),
                )
            result = run_f6201b_support(
                config=config, firmware=firmware, read_section=get_section,
                ping=lambda opts: active(PING, opts),
                traceroute=lambda opts: active(TRACE, opts),
                speedtest=measure, optimize=optimize,
            )
            run_id = history_repository.save_diagnostic(
                self._history_session_id, result
            )
            # The report contains only whitelisted model diagnostic fields.
            return {**result, "history_id": run_id}

    def support_diagnostic(
        self,
        config
    ):
        """
        Diagnóstico completo do atendimento.

        O engine só lê. Se auto_optimize_wifi estiver habilitado, a camada
        Service aplica as recomendações seguras através de _run_change e roda
        uma validação final. Assim diagnóstico e escrita nunca se misturam.
        """
        with self._lock:
            zte = self.get_client()
            thresholds = self._diagnostic_thresholds(
                config
            )
            options = self._support_options(
                config
            )
            engine = SupportDiagnosticService(
                zte,
                self._capabilities(),
            )

            result = engine.run(
                options,
                thresholds,
            )

            result["mode"] = options.mode
            result["remediations"] = []

            if config.get(
                "auto_optimize_wifi",
                False
            ):
                result[
                    "remediations"
                ] = self._apply_safe_wifi_recommendations(
                    result
                )

                if result[
                    "remediations"
                ]:
                    validation_options = replace(
                        options,
                        include_speedtest=False,
                        include_traceroute=False,
                    )

                    validation = engine.run(
                        validation_options,
                        thresholds,
                    )

                    validation["mode"] = (
                        options.mode
                    )

                    # Speed Test não é repetido após a mudança de canal para
                    # evitar tráfego duplicado. Mantemos a medição inicial no
                    # relatório final quando ela existiu.
                    initial_speed = (
                        result.get(
                            "sections",
                            {}
                        ).get(
                            "speedtest"
                        )
                    )

                    if initial_speed:
                        validation.setdefault(
                            "sections",
                            {},
                        )[
                            "speedtest"
                        ] = initial_speed

                    result[
                        "post_validation"
                    ] = validation

            diagnostic_id = (
                history_repository.save_diagnostic(
                    self._history_session_id,
                    result,
                )
            )

            history_repository.save_snapshot(
                self._history_session_id,
                "support_diagnostic",
                (
                    result.get(
                        "post_validation"
                    )
                    or result
                ).get(
                    "sections",
                    {}
                ),
            )

            return {
                **result,
                "history_id": diagnostic_id,
            }

    def _apply_safe_wifi_recommendations(
        self,
        diagnostic
    ):
        zte = self.get_client()
        applied = []
        seen_bands = set()

        for recommendation in diagnostic.get(
            "recommendations",
            []
        ):
            if not recommendation.get(
                "safe"
            ):
                continue

            action = recommendation.get(
                "action"
            ) or {}

            action_type = action.get(
                "type"
            )

            if action_type not in {
                "wifi_channel",
                "wifi_auto_channel",
            }:
                continue

            band = action.get(
                "band"
            )

            if (
                not band
                or band in seen_bands
            ):
                continue

            if action_type == "wifi_channel":
                channel = action.get(
                    "channel"
                )

                if channel is None:
                    continue

                config = {
                    "auto_channel": False,
                    "channel": int(
                        channel
                    ),
                }
            else:
                config = {
                    "auto_channel": True,
                }

            result = self._run_change(
                operation="wifi_auto_optimization",
                target=band,
                before_reader=zte.channel_status,
                action=lambda b=band, cfg=config: zte.set_radio_config(
                    b,
                    cfg
                ),
                after_reader=zte.channel_status,
            )

            applied.append({
                "band": band,
                "action": action,
                "result": result,
            })

            seen_bands.add(
                band
            )

        return applied

    def remediate_diagnostic(
        self,
        config
    ):
        """Aplica uma recomendação escolhida manualmente na UI."""
        with self._lock:
            zte = self.get_client()
            action = str(
                config.get("action")
                or ""
            )

            band = config.get(
                "band"
            )

            if action == "wifi_channel":
                channel = config.get(
                    "channel"
                )

                if (
                    not band
                    or channel is None
                ):
                    raise ValueError(
                        "Informe banda e canal para a otimização."
                    )

                radio_config = {
                    "auto_channel": False,
                    "channel": int(
                        channel
                    ),
                }

            elif action == "wifi_auto_channel":
                if not band:
                    raise ValueError(
                        "Informe a banda para ativar o canal automático."
                    )

                radio_config = {
                    "auto_channel": True,
                }

            else:
                raise ValueError(
                    "Ação de remediação não suportada."
                )

            result = self._run_change(
                operation="wifi_auto_optimization",
                target=band,
                before_reader=zte.channel_status,
                action=lambda: zte.set_radio_config(
                    band,
                    radio_config
                ),
                after_reader=zte.channel_status,
            )

            return {
                "success": True,
                "action": action,
                "band": band,
                "result": result,
            }

    def speedtest(
        self,
        config
    ):
        with self._lock:
            result = SpeedTestService(
                self.get_client()
            ).run(
                allow_fallback=config.get(
                    "allow_fallback",
                    True
                ),
                server_url=config.get(
                    "server_url"
                ),
                fallback_base_url=config.get(
                    "fallback_base_url"
                ),
                provider=config.get(
                    "provider",
                    "native_auto"
                ),
            )

            history_repository.save_snapshot(
                self._history_session_id,
                "speedtest",
                result,
            )

            return result

    def generate_attendance(
        self,
        diagnostic_id=None
    ):
        with self._lock:
            diagnostic = (
                history_repository.diagnostic(
                    diagnostic_id,
                    session_id=(
                        self._history_session_id
                    ),
                )
            )

            if not diagnostic:
                raise ValueError(
                    "Execute um diagnóstico antes de gerar o atendimento."
                )

            session_id = (
                diagnostic.get(
                    "session_id"
                )
                or self._history_session_id
            )

            timeline = (
                history_repository.session_timeline(
                    session_id
                )
            )

            report = AttendanceReportService().build(
                diagnostic=diagnostic,
                timeline=timeline,
            )

            return {
                **report,
                "diagnostic_id": diagnostic.get(
                    "history_id"
                ),
                "session_id": session_id,
            }

    def capture_snapshot(
        self,
        reason="manual"
    ):
        with self._lock:
            payload = self._snapshot_payload()
            snapshot_id = (
                history_repository.save_snapshot(
                    self._history_session_id,
                    reason,
                    payload,
                )
            )

            failed_sections = [
                name
                for name, data in payload.items()
                if isinstance(data, dict)
                and data.get("_error")
            ]

            return {
                "success": True,
                "snapshot_id": snapshot_id,
                "payload": payload,
                "partial": bool(failed_sections),
                "failed_sections": failed_sections,
            }

    def history(
        self,
        limit=50
    ):
        return history_repository.recent(
            limit
        )

    # =========================================================
    # CPE MANAGEMENT / NETWORK CONTROL
    # =========================================================

    def management_overview(self):
        with self._lock:
            zte = self.get_client()

            readers = {
                "mesh": zte.mesh_status,
                "qos": zte.qos_status,
                "firewall": zte.firewall_management_status,
                "firewall_rules": zte.firewall_rules,
                "wan": zte.wan_configurations,
                "sntp": zte.sntp_management_status,
                "tr069": zte.tr069_management_status,
                "firmware": zte.firmware_management_status,
                "port_forwarding": zte.port_forwarding_status,
                "dmz": zte.dmz_status,
                "upnp": zte.upnp_status,
            }

            return {
                name: self._safe_capture(
                    reader
                )
                for name, reader in readers.items()
            }

    def qos_management_status(self):
        with self._lock:
            return self.get_client().qos_status()

    def save_management_qos(
        self,
        kind,
        config,
        *,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation=f"qos_{kind}_save",
                target=(
                    config.get("id")
                    or config.get("Alias")
                    or kind
                ),
                before_reader=zte.qos_status,
                action=lambda: zte.save_qos(
                    kind,
                    config
                ),
                after_reader=zte.qos_status,
            )

    def delete_management_qos(
        self,
        kind,
        instance_id,
        *,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation=f"qos_{kind}_delete",
                target=instance_id,
                before_reader=zte.qos_status,
                action=lambda: zte.delete_qos(
                    kind,
                    instance_id
                ),
                after_reader=zte.qos_status,
            )

    def firewall_management_status(self):
        with self._lock:
            return (
                self.get_client()
                .firewall_management_status()
            )

    def set_management_firewall(
        self,
        config,
        *,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="firewall_update",
                target="firewall",
                before_reader=(
                    zte.firewall_management_status
                ),
                action=lambda: (
                    zte.set_firewall_management(
                        config
                    )
                ),
                after_reader=(
                    zte.firewall_management_status
                ),
            )

    def firewall_rules(self):
        with self._lock:
            return self.get_client().firewall_rules()

    def save_management_firewall_rule(
        self,
        kind,
        config,
        *,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation=f"firewall_{kind}_rule_save",
                target=(
                    config.get("id")
                    or config.get("Name")
                    or kind
                ),
                before_reader=zte.firewall_rules,
                action=lambda: zte.save_firewall_rule(
                    kind,
                    config
                ),
                after_reader=zte.firewall_rules,
            )

    def delete_management_firewall_rule(
        self,
        kind,
        instance_id,
        *,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation=f"firewall_{kind}_rule_delete",
                target=instance_id,
                before_reader=zte.firewall_rules,
                action=lambda: zte.delete_firewall_rule(
                    kind,
                    instance_id
                ),
                after_reader=zte.firewall_rules,
            )

    def set_management_filter_global(
        self,
        config,
        *,
        confirm=False
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="firewall_filter_global",
                target="filterCriteria",
                before_reader=zte.firewall_rules,
                action=lambda: zte.set_filter_global(
                    config
                ),
                after_reader=zte.firewall_rules,
            )

    def sntp_management_status(self):
        with self._lock:
            return (
                self.get_client()
                .sntp_management_status()
            )

    def set_management_sntp(
        self,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="sntp_update",
                target="sntp",
                before_reader=(
                    zte.sntp_management_status
                ),
                action=lambda: (
                    zte.set_sntp_management(
                        config
                    )
                ),
                after_reader=(
                    zte.sntp_management_status
                ),
            )

    def tr069_management_status(self):
        with self._lock:
            return (
                self.get_client()
                .tr069_management_status()
            )

    def set_management_tr069(
        self,
        config,
        *,
        confirm=True
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="tr069_update",
                target="acs",
                before_reader=(
                    zte.tr069_management_status
                ),
                action=lambda: (
                    zte.set_tr069_management(
                        config
                    )
                ),
                after_reader=(
                    zte.tr069_management_status
                ),
            )

    def wan_configurations(self):
        with self._lock:
            return (
                self.get_client()
                .wan_configurations()
            )

    def create_management_wan(
        self,
        config,
        *,
        confirm=False,
        backup=True
    ):
        with self._lock:
            if backup:
                self.management_backup(
                    reason="pre_wan_create"
                )

            zte = self.get_client()

            return self._run_change(
                operation="wan_create",
                target=(
                    config.get("name")
                    or "new_wan"
                ),
                before_reader=zte.wan_configurations,
                action=lambda: zte.create_wan(
                    config
                ),
                after_reader=zte.wan_configurations,
            )

    def update_management_wan(
        self,
        instance_id,
        config,
        *,
        confirm=True,
        backup=True
    ):
        with self._lock:
            if backup:
                self.management_backup(
                    reason="pre_wan_change"
                )

            zte = self.get_client()

            return self._run_change(
                operation="wan_update",
                target=instance_id,
                before_reader=(
                    zte.wan_configurations
                ),
                action=lambda: zte.update_wan(
                    instance_id,
                    config
                ),
                after_reader=(
                    zte.wan_configurations
                ),
            )

    def delete_management_wan(
        self,
        instance_id,
        *,
        confirm=False
    ):
        with self._lock:
            self.management_backup(
                reason="pre_wan_delete"
            )

            zte = self.get_client()

            return self._run_change(
                operation="wan_delete",
                target=instance_id,
                before_reader=zte.wan_configurations,
                action=lambda: zte.delete_wan(
                    instance_id
                ),
                after_reader=zte.wan_configurations,
            )

    def management_wan_action(
        self,
        instance_id,
        action
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation=f"wan_{action}",
                target=instance_id,
                before_reader=(
                    zte.wan_configurations
                ),
                action=lambda: zte.wan_action(
                    instance_id,
                    action
                ),
                after_reader=(
                    zte.wan_configurations
                ),
            )

    def bridge_mode_assistant(
        self,
        instance_id,
        config,
        *,
        confirm=False
    ):
        with self._lock:
            backup = self.management_backup(
                reason="pre_bridge_mode"
            )

            zte = self.get_client()

            result = self._run_change(
                operation="bridge_mode",
                target=instance_id,
                before_reader=(
                    zte.wan_configurations
                ),
                action=lambda: (
                    zte.bridge_assistant(
                        instance_id,
                        config
                    )
                ),
                after_reader=(
                    zte.wan_configurations
                ),
            )

            return {
                **result,
                "backup": backup,
            }

    def _assert_management_device_matches_current(
        self,
        device_id,
    ):
        if device_id is None:
            return None

        device = management_repository.get_device(
            int(device_id)
        )

        if device is None:
            raise ValueError(
                "Equipamento do inventário não encontrado."
            )

        current_serial = (
            self._device_info.get("serial")
            or self._device_info.get("serial_number")
            or self._device_info.get("sn")
            or self._device_info.get("SerialNumber")
        )

        inventory_serial = device.get(
            "serial"
        )

        if (
            current_serial
            and inventory_serial
            and str(current_serial).strip()
            != str(inventory_serial).strip()
        ):
            raise RuntimeError(
                "A ONT conectada não corresponde ao equipamento selecionado no inventário."
            )

        current_host = str(
            self.current_host
            or ""
        ).split(
            ":",
            1,
        )[0]

        inventory_host = str(
            device.get("host")
            or ""
        ).split(
            ":",
            1,
        )[0]

        if (
            not (
                current_serial
                and inventory_serial
            )
            and current_host
            and inventory_host
            and current_host != inventory_host
        ):
            raise RuntimeError(
                "A ONT conectada não corresponde ao host do equipamento selecionado."
            )

        return device

    def management_backup(
        self,
        *,
        device_id=None,
        reason="manual"
    ):
        with self._lock:
            self._assert_management_device_matches_current(
                device_id
            )

            result = self.export_user_configuration()

            record = management_repository.register_backup(
                device_id=device_id,
                path=result.get(
                    "path"
                ),
                reason=reason,
                metadata={
                    "host": self.current_host,
                    "attendant": (
                        self.current_attendant
                    ),
                    "filename": result.get(
                        "filename"
                    ),
                    "size": result.get(
                        "size"
                    ),
                },
            )

            return {
                **result,
                "backup_id": record[
                    "id"
                ],
                "reason": reason,
            }

    def management_backups(
        self,
        device_id=None
    ):
        return management_repository.list_backups(
            device_id
        )

    def restore_management_backup(
        self,
        backup_id,
        *,
        confirm=False
    ):
        backups = management_repository.list_backups()

        backup = next((
            item
            for item in backups
            if int(
                item.get("id")
                or -1
            ) == int(
                backup_id
            )
        ), None)

        if backup is None:
            raise ValueError(
                "Backup não encontrado."
            )

        with self._lock:
            self._assert_management_device_matches_current(
                backup.get(
                    "device_id"
                )
            )

            zte = self.get_client()

            result = zte.restore_configuration(
                backup[
                    "path"
                ]
            )

            history_repository.save_change(
                self._history_session_id,
                operation="restore_configuration",
                target=backup[
                    "path"
                ],
                before=None,
                after={
                    "backup_id": backup_id,
                    "file": backup[
                        "path"
                    ],
                },
                success=True,
                message=(
                    "Restauração enviada; a ONT pode reiniciar."
                ),
            )

            return result

    def firmware_management_status(self):
        with self._lock:
            return (
                self.get_client()
                .firmware_management_status()
            )

    def upload_management_firmware(
        self,
        file_path,
        *,
        confirm=False,
        device_id=None
    ):
        with self._lock:
            self._assert_management_device_matches_current(
                device_id
            )

            backup = self.management_backup(
                device_id=device_id,
                reason="pre_firmware_upgrade",
            )

            result = (
                self.get_client()
                .upload_firmware(
                    file_path
                )
            )

            history_repository.save_change(
                self._history_session_id,
                operation="firmware_upgrade",
                target=file_path,
                before={
                    "backup_id": backup.get(
                        "backup_id"
                    ),
                    "device": self._device_info,
                },
                after={
                    "sha256": result.get(
                        "sha256"
                    ),
                    "size": result.get(
                        "size"
                    ),
                },
                success=True,
                message=(
                    "Firmware enviado; aguardando ciclo de upgrade/reboot."
                ),
            )

            return {
                **result,
                "backup": backup,
            }

    # =========================================================
    # PERFIL DO ATENDENTE
    # =========================================================

    def profiles(self):
        return profile_service.list_profiles()

    def get_profile(
        self,
        attendant=None
    ):
        attendant = (
            attendant
            or self.current_attendant
            or "default"
        )

        return profile_service.get_profile(
            attendant
        )

    def save_profile(
        self,
        attendant,
        profile
    ):
        attendant = (
            attendant
            or self.current_attendant
            or "default"
        )

        return profile_service.save_profile(
            attendant,
            profile
        )

    def current_configuration(self):
        with self._lock:
            return self.get_client().current_standard_configuration()

    def capture_profile(
        self,
        attendant=None
    ):
        with self._lock:
            attendant = (
                attendant
                or self.current_attendant
                or "default"
            )

            profile = self.get_client().current_standard_configuration()

            return profile_service.save_profile(
                attendant,
                profile
            )

    def apply_profile(
        self,
        attendant=None
    ):
        with self._lock:
            attendant = (
                attendant
                or self.current_attendant
                or "default"
            )

            zte = self.get_client()

            return self._run_change(
                operation="profile_apply",
                target=attendant,
                before_reader=zte.current_standard_configuration,
                action=lambda: profile_service.apply_profile(
                    zte,
                    attendant
                ),
                after_reader=zte.current_standard_configuration,
            )

    # =========================================================
    # RAW / DEBUG
    # =========================================================

    def wifi_raw(self):
        with self._lock:
            return self.get_client().wifi_status_raw()

    def channel_raw(self):
        with self._lock:
            return self.get_client().wlan_channel_raw()

    def device_raw(self):
        with self._lock:
            return self.get_client().device_status_raw()

    def wan_raw(self):
        with self._lock:
            return self.get_client().wan_status_raw()


# Uma instância por processo = uma sessão ativa da ONT para toda a API.
zte_service = ZTEService()
