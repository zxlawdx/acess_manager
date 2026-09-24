import xml.etree.ElementTree as ET

import requests
import urllib3

from .zte_configuration import (
    zte_advanced,
    zte_backup,
    zte_clients,
    zte_connection_status,
    zte_diagnostics,
    zte_dns,
    zte_device_management,
    zte_get_menu,
    zte_lan,
    zte_management,
    zte_mesh,
    zte_network_management,
    zte_save_content,
    zte_session,
    zte_support_diagnostics,
    zte_wan_config,
    zte_wifi,
    zte_wlan_channel_configuration,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ZTE:
    """
    Facade do protocolo HTTP da ONT.

    A classe concentra o estado da sessão. Os módulos em zte_configuration
    cuidam de cada área do equipamento e recebem esta instância para usar a
    mesma requests.Session, cookies e tokens durante todo o atendimento.
    """

    def __init__(self, ip, username, password, https=False):
        protocolo = "https" if https else "http"

        self.base_url = f"{protocolo}://{ip}"
        self.username = username
        self.password = password

        # Token do fluxo de login.
        self.session_token = None

        # Token temporário criado pela menuView. É este token que o firmware
        # usa nos POSTs de menuData e também na criptografia de alguns campos.
        self.session_tmp_token = None

        # A chave do Check muda entre firmwares. Ela é extraída da página em
        # tempo de execução, sem deixar uma chave de outro firmware hardcoded.
        self.public_key_pem = None
        self.integrity_check = None
        self.security_source = None

        self.session = requests.Session()
        self.session.verify = False

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.base_url + "/",
        })

    # =========================================================
    # SESSÃO
    # =========================================================

    def login(self):
        return zte_session.login(self)

    def logout(self):
        return zte_session.logout(self)

    # =========================================================
    # REQUISIÇÕES
    # =========================================================

    def get_view(self, tag, **extras):
        return zte_get_menu.get_view(
            self,
            tag,
            **extras
        )

    def get_menu(self, tag, **extras):
        return zte_get_menu.get_menu(
            self,
            tag,
            **extras
        )

    # =========================================================
    # REQUISIÇÕES RAW
    # =========================================================

    def device_status_raw(self):
        return zte_connection_status.device_status(self)

    def wan_status_raw(self):
        return zte_connection_status.wan_status(self)

    def wifi_status_raw(self):
        return zte_wifi.wifi_status(self)

    def optical_status_raw(self):
        return zte_device_management.optical_raw(self)

    def wifi_clients_raw(self):
        return zte_clients.wifi_clients(self)

    def lan_clients_raw(self):
        return zte_clients.lan_clients(self)

    def lan_ports_raw(self):
        return zte_lan.lan_ports_raw(self)

    def wlan_channel_raw(self):
        return zte_wlan_channel_configuration.get_channel(self)

    def dns_status_raw(self):
        return zte_dns.dns_status_raw(self)

    def wan_config_raw(self):
        return zte_wan_config.wan_config_raw(self)

    # =========================================================
    # PARSER XML
    # =========================================================

    @staticmethod
    def _parse_instances(xml_text):
        root = ET.fromstring(xml_text)

        resultado = {}

        for objeto in root:
            if not (
                objeto.tag.startswith("OBJ_")
                or objeto.tag.startswith("ID_")
                or objeto.tag == "ALLDNSHOST"
            ):
                continue

            instancias = []

            for instance in objeto.findall("Instance"):
                dados = {}
                filhos = list(instance)

                i = 0

                while i < len(filhos) - 1:
                    if (
                        filhos[i].tag == "ParaName"
                        and filhos[i + 1].tag == "ParaValue"
                    ):
                        nome = filhos[i].text or ""
                        valor = filhos[i + 1].text or ""

                        dados[nome] = valor
                        i += 2

                    else:
                        i += 1

                instancias.append(dados)

            resultado[objeto.tag] = instancias

        return resultado

    @staticmethod
    def _validar_resposta(xml_text):
        """
        O ZTE costuma devolver HTTP 200 mesmo quando a operação falhou.
        Por isso o erro real precisa ser lido de IF_ERRORSTR.
        """

        if "SessionTimeout" in xml_text:
            raise RuntimeError(
                "A sessão do ZTE expirou ou a view necessária não foi aberta."
            )

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return xml_text

        erro = root.findtext(
            "IF_ERRORSTR"
        )

        if erro and erro not in (
            "SUCC",
            "SUCCESS",
            "OK",
        ):
            raise RuntimeError(
                f"A ZTE retornou erro: {erro}"
            )

        return xml_text

    # =========================================================
    # DEVICE
    # =========================================================

    def device_status(self):
        xml = self.device_status_raw()

        self._validar_resposta(xml)

        dados = self._parse_instances(xml)

        info = dados.get("OBJ_DEVINFO_ID", [])
        cpu = dados.get("OBJ_CPUMEMUSAGE_ID", [])
        uptime = dados.get("OBJ_POWERONTIME_ID", [])
        temperatura = dados.get("OBJ_CPU_TEMPERATURE_ID", [])
        optical = dados.get("OBJ_PON_OPTICALPARA_ID", [])
        flash = dados.get("OBJ_FLASHINFO_ID", [])

        resultado = {}

        if info:
            dispositivo = info[0]

            resultado.update({
                "fabricante": dispositivo.get("ManuFacturer"),
                "modelo": dispositivo.get("ModelName"),
                "firmware": dispositivo.get("SoftwareVer"),
                "firmware_extendido": dispositivo.get(
                    "SoftwareVerExtent"
                ),
                "hardware": dispositivo.get("HardwareVer"),
                "boot": dispositivo.get("BootVer"),
                "serial": dispositivo.get("SerialNumber"),
            })

        if cpu:
            uso = cpu[0]

            resultado["memoria_percent"] = uso.get(
                "MemUsage"
            )

            resultado["cpu"] = {
                "cpu1": uso.get("CpuUsage1"),
                "cpu2": uso.get("CpuUsage2"),
                "cpu3": uso.get("CpuUsage3"),
                "cpu4": uso.get("CpuUsage4"),
            }

        if uptime:
            segundos = int(
                uptime[0].get("PowerOnTime", 0)
            )

            resultado["uptime_segundos"] = segundos
            resultado["uptime_dias"] = segundos // 86400

        if temperatura:
            resultado["temperatura_cpu"] = (
                temperatura[0].get("CPUTemp")
            )

        if optical:
            resultado["temperatura_pon"] = (
                optical[0].get("Temp")
            )

        if flash:
            resultado["flash_usado_percent"] = (
                flash[0].get("Flash_Percent_Used")
            )

        return resultado

    # =========================================================
    # WIFI
    # =========================================================

    def wifi_networks(
        self,
        reveal_password=False
    ):
        return zte_wifi.wifi_networks(
            self,
            reveal_password=reveal_password
        )

    def set_ssid_config(
        self,
        ssid_id,
        config
    ):
        return zte_wifi.set_ssid_config(
            self,
            ssid_id,
            config
        )

    def wifi_clients(self):
        xml = self.wifi_clients_raw()

        self._validar_resposta(xml)

        dados = self._parse_instances(xml)

        clientes = dados.get(
            "OBJ_WLAN_AD_ID",
            []
        )

        aps = dados.get(
            "OBJ_WLANAP_ID",
            []
        )

        ssids = {
            ap.get("_InstID"): ap.get("ESSID")
            for ap in aps
        }

        resultado = []

        for cliente in clientes:
            ap = cliente.get("AliasName")

            resultado.append({
                "hostname": (
                    cliente.get("HostName")
                    or "Desconhecido"
                ),
                "ip": cliente.get("IPAddress"),
                "ipv6": cliente.get("IPV6Address"),
                "mac": cliente.get("MACAddress"),
                "ssid": ssids.get(ap, ap),
                "ap": ap,
                "rssi": cliente.get("RSSI"),
                "snr": cliente.get("SNR"),
                "noise": cliente.get("NOISE"),
                "modo": cliente.get("CurrentMode"),
                "largura": cliente.get("BAND"),
                "mcs": cliente.get("MCS"),
                "rx_rate": cliente.get("RxRate"),
                "tx_rate": cliente.get("TxRate"),
                "rx_bytes": cliente.get("RXBytes"),
                "tx_bytes": cliente.get("TXBytes"),
                "tempo_conectado": cliente.get("LinkTime"),
                "conectado_desde": cliente.get("ConnectTime"),
            })

        return resultado

    # =========================================================
    # LAN
    # =========================================================

    def lan_clients(self):
        xml = self.lan_clients_raw()

        self._validar_resposta(xml)

        dados = self._parse_instances(xml)

        clientes = dados.get(
            "OBJ_ACCESSDEV_ID",
            []
        )

        resultado = []

        for cliente in clientes:
            resultado.append({
                "hostname": (
                    cliente.get("HostName")
                    or "Desconhecido"
                ),
                "ip": cliente.get("IPAddress"),
                "mac": cliente.get("MACAddress"),
                "interface": (
                    cliente.get("Interface")
                    or cliente.get("Layer2Interface")
                    or cliente.get("InterfaceName")
                ),
                "raw": cliente,
            })

        return resultado

    def lan_ports(self):
        return zte_lan.lan_ports(
            self
        )

    # =========================================================
    # WLAN ADVANCED
    # =========================================================

    def channel_status(self):
        xml = self.wlan_channel_raw()

        self._validar_resposta(xml)

        dados = self._parse_instances(xml)

        radios = dados.get(
            "OBJ_WLANSETTING_ID",
            []
        )

        resultado = []

        for radio in radios:
            resultado.append({
                "id": radio.get("_InstID"),
                "banda": radio.get("Band"),
                "canal": radio.get("Channel"),
                "canal_automatico": (
                    radio.get("AutoChannelEnabled") == "1"
                ),
                "largura": radio.get("BandWidth"),
                "padrao": radio.get("Standard"),
                "potencia": radio.get("TxPower"),
                "radio_ativo": (
                    radio.get("RadioStatus") == "1"
                ),
                "sideband": radio.get("SideBand"),
                "pais": radio.get("CountryCode"),
                "sgi": radio.get("SGIEnabled") == "1",
                "beacon_interval": radio.get("BeaconInterval"),
                "ssid_isolation": (
                    radio.get("SSIDIsolationEnable") == "1"
                ),
                "mu_mimo": radio.get("MUMIMOEnable") == "1",
                "uplink_mu_mimo": radio.get("UPLinkMUMIMO") == "1",
                "downlink_mu_mimo": radio.get("DownLinkMUMIMO") == "1",
                "uplink_ofdma": radio.get("UPLinkOFDMA") == "1",
                "downlink_ofdma": radio.get("DownLinkOFDMA") == "1",
                "twt": radio.get("TWTSupport") == "1",
                "spatial_reuse": radio.get("SpatialReuse") == "1",
                "qos_type": radio.get("QosType"),
                "work_mode": radio.get("WorkMode"),
                "rts_cts": _int_or_value(radio.get("RtsCts")),
                "dtim": _int_or_value(radio.get("DTIM")),
                "preamble_type": radio.get("PreambleType"),
            })

        return resultado

    def available_channels(
        self,
        band=None,
        bandwidth=None,
        country="BRI"
    ):
        xml = self.wlan_channel_raw()

        self._validar_resposta(xml)

        dados = self._parse_instances(xml)

        configuracoes = dados.get(
            "OBJ_CHANNEL_ID",
            []
        )

        resultado = []

        for config in configuracoes:
            if country and config.get("CountryCode") != country:
                continue

            if band and config.get("Band") != band:
                continue

            if bandwidth and config.get("BandWidth") != bandwidth:
                continue

            lista = config.get(
                "ChannelList",
                ""
            )

            canais = []

            for canal in lista.split(","):
                canal = canal.strip()

                if not canal:
                    continue

                try:
                    canais.append(
                        int(canal)
                    )
                except ValueError:
                    canais.append(
                        canal
                    )

            resultado.append({
                "id": config.get("_InstID"),
                "banda": config.get("Band"),
                "largura": config.get("BandWidth"),
                "pais": config.get("CountryCode"),
                "canais": canais,
            })

        return resultado

    def set_radio_config(
        self,
        band,
        config
    ):
        return zte_wlan_channel_configuration.set_radio_config(
            self,
            band,
            config
        )


    # =========================================================
    # ADVANCED / FEATURE CONTROLS
    # =========================================================

    def radio_power_status(self):
        return zte_advanced.radio_power_status(
            self
        )

    def set_radio_power(
        self,
        band,
        enabled
    ):
        return zte_advanced.set_radio_power(
            self,
            band,
            enabled
        )

    def wifi_schedule_status(self):
        return zte_advanced.wifi_schedule_status(
            self
        )

    def set_wifi_schedule(
        self,
        config
    ):
        return zte_advanced.set_wifi_schedule(
            self,
            config
        )

    def wps_status(self):
        return zte_advanced.wps_status(
            self
        )

    def set_wps(
        self,
        band,
        mode
    ):
        return zte_advanced.set_wps(
            self,
            band,
            mode
        )

    def upnp_status(self):
        return zte_advanced.upnp_status(
            self
        )

    def set_upnp(
        self,
        config
    ):
        return zte_advanced.set_upnp(
            self,
            config
        )

    def mesh_status(self):
        return zte_mesh.mesh_status(
            self
        )

    def configure_mesh(
        self,
        config
    ):
        return zte_mesh.configure_mesh(
            self,
            config
        )

    def start_mesh_pairing(self):
        return zte_mesh.start_mesh_pairing(
            self
        )

    def band_steering_status(self):
        return zte_advanced.band_steering_status(
            self
        )

    def set_band_steering(
        self,
        enabled
    ):
        return zte_advanced.set_band_steering(
            self,
            enabled
        )

    def configure_band_steering(
        self,
        config
    ):
        return zte_advanced.configure_band_steering(
            self,
            config
        )

    # =========================================================
    # DHCP / NAT
    # =========================================================

    def dhcp_status(self):
        return zte_network_management.dhcp_status(
            self
        )

    def set_dhcp_basic(
        self,
        config
    ):
        return zte_network_management.set_dhcp_basic(
            self,
            config
        )

    def save_dhcp_reservation(
        self,
        config
    ):
        return zte_network_management.save_dhcp_reservation(
            self,
            config
        )

    def delete_dhcp_reservation(
        self,
        instance_id
    ):
        return zte_network_management.delete_dhcp_reservation(
            self,
            instance_id
        )

    def port_forwarding_status(self):
        return zte_network_management.port_forwarding_status(
            self
        )

    def save_port_forward(
        self,
        config
    ):
        return zte_network_management.save_port_forward(
            self,
            config
        )

    def delete_port_forward(
        self,
        instance_id
    ):
        return zte_network_management.delete_port_forward(
            self,
            instance_id
        )

    def dmz_status(self):
        return zte_network_management.dmz_status(
            self
        )

    def set_dmz(
        self,
        config
    ):
        return zte_network_management.set_dmz(
            self,
            config
        )

    # =========================================================
    # CPE MANAGEMENT
    # =========================================================

    def qos_status(self):
        return zte_management.qos_status(
            self
        )

    def save_qos(
        self,
        kind,
        config
    ):
        return zte_management.save_qos(
            self,
            kind,
            config
        )

    def delete_qos(
        self,
        kind,
        instance_id
    ):
        return zte_management.delete_qos(
            self,
            kind,
            instance_id
        )

    def firewall_management_status(self):
        return zte_management.firewall_status(
            self
        )

    def firewall_rules(self):
        return zte_management.firewall_rules(
            self
        )

    def save_firewall_rule(
        self,
        kind,
        config
    ):
        return zte_management.save_firewall_rule(
            self,
            kind,
            config
        )

    def delete_firewall_rule(
        self,
        kind,
        instance_id
    ):
        return zte_management.delete_firewall_rule(
            self,
            kind,
            instance_id
        )

    def set_filter_global(
        self,
        config
    ):
        return zte_management.set_filter_global(
            self,
            config
        )

    def set_firewall_management(
        self,
        config
    ):
        return zte_management.set_firewall(
            self,
            config
        )

    def sntp_management_status(self):
        return zte_management.sntp_status(
            self
        )

    def set_sntp_management(
        self,
        config
    ):
        return zte_management.set_sntp(
            self,
            config
        )

    def tr069_management_status(self):
        return zte_management.tr069_status(
            self
        )

    def set_tr069_management(
        self,
        config
    ):
        return zte_management.set_tr069(
            self,
            config
        )

    def wan_configurations(self):
        return zte_management.wan_configurations(
            self
        )

    def create_wan(
        self,
        config
    ):
        return zte_management.create_wan(
            self,
            config
        )

    def update_wan(
        self,
        instance_id,
        config
    ):
        return zte_management.update_wan(
            self,
            instance_id,
            config
        )

    def delete_wan(
        self,
        instance_id
    ):
        return zte_management.delete_wan(
            self,
            instance_id
        )

    def wan_action(
        self,
        instance_id,
        action
    ):
        return zte_management.wan_action(
            self,
            instance_id,
            action
        )

    def bridge_assistant(
        self,
        instance_id,
        config
    ):
        return zte_management.bridge_assistant(
            self,
            instance_id,
            config
        )

    def firmware_management_status(self):
        return zte_management.firmware_status(
            self
        )

    def upload_firmware(
        self,
        file_path
    ):
        return zte_management.upload_firmware(
            self,
            file_path
        )

    def restore_configuration(
        self,
        file_path
    ):
        return zte_management.restore_configuration(
            self,
            file_path
        )

    # =========================================================
    # DNS
    # =========================================================

    def dns_status(self):
        return zte_dns.dns_status(
            self
        )

    def set_dns(self, config):
        return zte_dns.set_dns(
            self,
            config
        )

    # =========================================================
    # DEVICE MANAGEMENT / PON
    # =========================================================

    def optical_status(self):
        return zte_device_management.optical_status(
            self
        )

    def reboot(self):
        return zte_device_management.reboot(
            self
        )

    def account_status(self):
        return zte_device_management.account_status(
            self
        )

    def change_admin_password(
        self,
        new_password
    ):
        return zte_device_management.change_admin_password(
            self,
            new_password
        )

    def export_user_configuration(
        self,
        device=None
    ):
        return zte_backup.export_user_configuration(
            self,
            device=device,
        )

    # =========================================================
    # WAN / PPPOE
    # =========================================================

    def wan_status(self):
        xml = self.wan_status_raw()

        self._validar_resposta(xml)

        dados = self._parse_instances(xml)

        conexoes = dados.get(
            "ID_WAN_COMFIG",
            []
        )

        resultado = []

        for wan in conexoes:
            resultado.append({
                "id": wan.get("_InstID"),
                "nome": wan.get("WANCName"),
                "status": wan.get("ConnStatus"),
                "status_ipv6": wan.get("ConnStatus6"),
                "tipo": wan.get("TransType"),
                "wan_type": wan.get("wantype"),
                "modo": wan.get("mode"),
                "ip": wan.get("IPAddress"),
                "gateway": wan.get("GateWay"),
                "dns1": wan.get("DNS1"),
                "dns2": wan.get("DNS2"),
                "dns_ipv6_1": wan.get("Dns1v6"),
                "dns_ipv6_2": wan.get("Dns2v6"),
                "ipv6": wan.get("Gua1"),
                "prefixo_ipv6": wan.get("Pd"),
                "prefixo_ipv6_len": wan.get("PdLen"),
                "vlan": wan.get("VLANID"),
                "mtu": wan.get("MTU"),
                "nat": wan.get("IsNAT"),
                "uptime": wan.get("UpTime"),
                "rx_bytes": wan.get("RxBytes"),
                "tx_bytes": wan.get("TxBytes"),
                "rx_packets": wan.get("RxPackets"),
                "tx_packets": wan.get("TxPackets"),
                "erro": wan.get("ConnError"),
            })

        return resultado

    def pppoe_status(
        self,
        reveal_password=False
    ):
        return zte_wan_config.pppoe_status(
            self,
            reveal_password=reveal_password
        )

    # =========================================================
    # DIAGNÓSTICOS
    # =========================================================

    def ping(self, config):
        diagnostico = zte_diagnostics.PingDiagnostic()

        return diagnostico.run(
            self,
            config
        )

    def traceroute(self, config):
        diagnostico = zte_diagnostics.TracerouteDiagnostic()

        return diagnostico.run(
            self,
            config
        )

    def wifi_neighbor_scan(
        self,
        band
    ):
        return zte_support_diagnostics.wifi_neighbor_scan(
            self,
            band
        )

    def nslookup(
        self,
        hostname,
        **options
    ):
        return zte_support_diagnostics.nslookup(
            self,
            hostname,
            **options
        )

    def native_speedtest_servers(self):
        return zte_support_diagnostics.native_speedtest_servers(
            self
        )

    def native_speedtest(
        self,
        **options
    ):
        return zte_support_diagnostics.native_speedtest(
            self,
            **options
        )

    # =========================================================
    # CONFIGURAÇÃO ATUAL / PERFIL
    # =========================================================

    def current_standard_configuration(self):
        radios = self.channel_status()
        dns = self.dns_status()

        wifi = {}

        for radio in radios:
            wifi[radio.get("banda")] = {
                "auto_channel": radio.get("canal_automatico", True),
                "channel": (
                    None
                    if radio.get("canal_automatico")
                    else _int_or_value(
                        radio.get("canal")
                    )
                ),
                "standard": radio.get("padrao"),
                "country": radio.get("pais"),
                "bandwidth": radio.get("largura"),
                "sgi": radio.get("sgi", False),
                "beacon_interval": _int_or_value(
                    radio.get("beacon_interval") or 100
                ),
                "tx_power": radio.get("potencia"),
            }

        return {
            "wifi": wifi,
            "dns": {
                "domain_name": dns.get("domain_name"),
                "ipv4_1": dns.get("ipv4_1"),
                "ipv4_2": dns.get("ipv4_2"),
                "ipv6_1": dns.get("ipv6_1"),
                "ipv6_2": dns.get("ipv6_2"),
                "hosts": [
                    {
                        "nome": host.get("nome"),
                        "ip": host.get("ip"),
                    }
                    for host in dns.get("hosts", [])
                    if host.get("nome") and host.get("ip")
                ],
            },
        }

    # =========================================================
    # UTILIDADES
    # =========================================================

    @staticmethod
    def salvar(nome, conteudo):
        return zte_save_content.salvar(
            nome,
            conteudo
        )


def _int_or_value(valor):
    try:
        return int(valor)
    except (
        TypeError,
        ValueError
    ):
        return valor
