from threading import RLock
from typing import Optional

from apps.zte_manager.model.device_adapters import select_adapter
from apps.zte_manager.model.zte import ZTE
from apps.zte_manager.repositories.history_repository import history_repository
from apps.zte_manager.services.automatic_diagnostic_service import (
    AutomaticDiagnosticService,
    DiagnosticThresholds,
)
from apps.zte_manager.services.capability_service import CapabilityService
from apps.zte_manager.services.profile_service import profile_service


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
    ):
        with self._lock:
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

                self.current_host = ip

                return {
                    "success": True,
                    "attendant": self.current_attendant,
                    "host": self.current_host,
                    "reused_session": True,
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
            try:
                self._device_info = self._zte.device_status()
            except Exception:
                self._device_info = {}

            self._adapter = select_adapter(
                self._device_info.get("modelo"),
                self._device_info.get("firmware"),
            )

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

            return {
                "success": True,
                "attendant": self.current_attendant,
                "host": self.current_host,
                "reused_session": False,
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

    def change_admin_password(
        self,
        new_password
    ):
        with self._lock:
            return self.get_client().change_admin_password(
                new_password
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

    def wifi_clients(self):
        with self._lock:
            return self.get_client().wifi_clients()

    def lan_clients(self):
        with self._lock:
            return self.get_client().lan_clients()

    def lan_ports(self):
        with self._lock:
            return self.get_client().lan_ports()

    def all_clients(self):
        with self._lock:
            zte = self.get_client()

            return {
                "wifi": zte.wifi_clients(),
                "lan": zte.lan_clients()
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
            return self.get_client().set_ssid_config(
                ssid_id,
                config
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
            return self.get_client().set_radio_config(
                band,
                config
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
            return self.get_client().set_radio_power(
                band,
                enabled
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
            return self.get_client().set_wps(
                band,
                mode
            )

    def upnp_status(self):
        with self._lock:
            return self.get_client().upnp_status()

    def set_upnp(
        self,
        config
    ):
        with self._lock:
            return self.get_client().set_upnp(
                config
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

    def dhcp_status(self):
        with self._lock:
            return self.get_client().dhcp_status()

    def set_dhcp_basic(
        self,
        config
    ):
        with self._lock:
            zte = self.get_client()

            return self._run_change(
                operation="dhcp_basic",
                target="lan",
                before_reader=zte.dhcp_status,
                action=lambda: zte.set_dhcp_basic(
                    config
                ),
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
        if not config.get("confirm"):
            raise ValueError(
                "Confirme explicitamente a alteração de port forwarding."
            )

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
        if not confirm:
            raise ValueError(
                "Confirme explicitamente a remoção do port forwarding."
            )

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
        if not config.get("confirm"):
            raise ValueError(
                "Confirme explicitamente a alteração da DMZ."
            )

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
            return self.get_client().set_dns(
                config
            )

    # =========================================================
    # DIAGNÓSTICOS
    # =========================================================

    def ping(self, config):
        with self._lock:
            return self.get_client().ping(
                config
            )

    def traceroute(self, config):
        with self._lock:
            return self.get_client().traceroute(
                config
            )

    # =========================================================
    # DIAGNÓSTICO AUTOMÁTICO / HISTÓRICO
    # =========================================================

    def automatic_diagnostic(
        self,
        config
    ):
        with self._lock:
            thresholds = DiagnosticThresholds(
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

            return {
                "success": True,
                "snapshot_id": snapshot_id,
                "payload": payload,
            }

    def history(
        self,
        limit=50
    ):
        return history_repository.recent(
            limit
        )

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

            return profile_service.apply_profile(
                self.get_client(),
                attendant
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
