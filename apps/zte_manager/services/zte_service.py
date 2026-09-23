from threading import RLock
from typing import Optional

from apps.zte_manager.model.zte import ZTE
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
                }

            # Para trocar de equipamento/credencial fechamos somente o socket
            # local. Não chamamos logout remoto automaticamente porque isso
            # pode invalidar a sessão administrativa que o atendente mantém
            # aberta na própria interface da ZTE. O botão Desconectar continua
            # executando logout explícito quando essa for a intenção.
            if self._zte is not None:
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

            return {
                "success": True,
                "attendant": self.current_attendant,
                "host": self.current_host,
                "reused_session": False,
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
                self._zte.session.close()
            finally:
                self._zte = None
                self.current_host = None
                self.current_attendant = None

    def get_client(self) -> ZTE:
        if self._zte is None:
            raise RuntimeError(
                "Nenhuma ONT ZTE conectada."
            )

        return self._zte

    @property
    def connected(self) -> bool:
        return self._zte is not None

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
            return self.get_client().device_status()

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
            self._zte = None
            self.current_host = None

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
            return self.get_client().set_band_steering(
                enabled
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
