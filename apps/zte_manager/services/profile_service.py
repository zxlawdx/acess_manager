from copy import deepcopy
from dataclasses import dataclass
from apps.zte_manager.repositories.profile_repository import ProfileRepository
from apps.zte_manager.runtime import data_dir


# Perfil inicial baseado na configuração padrão informada para o atendimento.
# Cada atendente pode sobrescrever esses valores pela interface.
DEFAULT_PROFILE = {
    "wifi": {
        "2.4GHz": {
            "auto_channel": True,
            "channel": None,
            "standard": "b,g,n",
            "country": "BRI",
            "bandwidth": "20MHz",
            "sgi": False,
            "beacon_interval": 100,
            "tx_power": "100%",
        },
        "5GHz": {
            "auto_channel": True,
            "channel": None,
            "standard": "a,n,ac",
            "country": "BRI",
            "bandwidth": "80MHz",
            "sgi": False,
            "beacon_interval": 100,
            "tx_power": "100%",
        },
    },
    "dns": {
        "domain_name": "",
        "ipv4_1": "177.221.56.3",
        "ipv4_2": "177.221.56.10",
        "ipv6_1": "2804:1128::3",
        "ipv6_2": "2804:1128::10",
        "hosts": [
            {
                "nome": "cloudflare",
                "ip": "1.1.1.1",
            },
            {
                "nome": "google",
                "ip": "8.8.8.8",
            },
        ],
    },
}


# =========================================================
# COMMAND / COMPOSITE PATTERN
# =========================================================


@dataclass
class ConfigurationResult:
    name: str
    success: bool
    detail: str


class ConfigurationCommand:
    name = "configuração"

    def execute(self, zte):
        raise NotImplementedError


class WifiRadioCommand(ConfigurationCommand):
    def __init__(
        self,
        band,
        config
    ):
        self.band = band
        self.config = config
        self.name = f"Wi-Fi {band}"

    def execute(self, zte):
        zte.set_radio_config(
            self.band,
            self.config
        )

        return ConfigurationResult(
            name=self.name,
            success=True,
            detail="Configuração aplicada."
        )


class DnsCommand(ConfigurationCommand):
    name = "DNS"

    def __init__(self, config):
        self.config = config

    def execute(self, zte):
        zte.set_dns(
            self.config
        )

        return ConfigurationResult(
            name=self.name,
            success=True,
            detail="Configuração aplicada."
        )


class ApplyProfileCommand:
    """
    Composite de comandos de configuração.

    O perfil é dividido em etapas independentes. Se uma falhar, registramos a
    falha e seguimos para a próxima para o atendente saber exatamente o que foi
    aplicado e o que precisa ser revisado.
    """

    def __init__(self, profile):
        self.profile = profile
        self.commands = self._build_commands()

    def _build_commands(self):
        commands = []

        wifi = self.profile.get(
            "wifi",
            {}
        )

        for band in (
            "2.4GHz",
            "5GHz"
        ):
            config = wifi.get(
                band
            )

            if config:
                commands.append(
                    WifiRadioCommand(
                        band,
                        config
                    )
                )

        dns = self.profile.get(
            "dns"
        )

        if dns:
            commands.append(
                DnsCommand(
                    dns
                )
            )

        return commands

    def execute(self, zte):
        resultados = []

        for command in self.commands:
            try:
                resultado = command.execute(
                    zte
                )

            except Exception as erro:
                resultado = ConfigurationResult(
                    name=command.name,
                    success=False,
                    detail=str(erro)
                )

                resultados.append({
                    "name": resultado.name,
                    "success": resultado.success,
                    "detail": resultado.detail,
                })

                # Aplicar perfil é um fluxo de escrita encadeado. Se o primeiro
                # POST é recusado por token/Check/sessão, continuar para 5 GHz
                # e DNS só repete requisições inválidas e pode derrubar a sessão
                # administrativa do equipamento. Paramos e devolvemos a etapa
                # exata que falhou para a UI.
                break

            resultados.append({
                "name": resultado.name,
                "success": resultado.success,
                "detail": resultado.detail,
            })

        return {
            "success": bool(resultados) and all(
                item["success"]
                for item in resultados
            ),
            "steps": resultados,
        }


# =========================================================
# PROFILE SERVICE
# =========================================================


class ProfileService:
    def __init__(self):
        self.repository = ProfileRepository(
            data_dir()
            / "attendant_profiles.json"
        )

    def list_profiles(self):
        return self.repository.list()

    def get_profile(self, attendant):
        perfil = self.repository.get(
            attendant
        )

        if perfil is not None:
            return _normalize_profile(
                perfil
            )

        return deepcopy(
            DEFAULT_PROFILE
        )

    def save_profile(
        self,
        attendant,
        profile
    ):
        perfil = _normalize_profile(
            profile
        )

        return self.repository.save(
            attendant,
            perfil
        )

    def apply_profile(
        self,
        zte,
        attendant
    ):
        profile = self.get_profile(
            attendant
        )

        command = ApplyProfileCommand(
            profile
        )

        return command.execute(
            zte
        )


def _normalize_profile(profile):
    resultado = deepcopy(
        DEFAULT_PROFILE
    )

    wifi = profile.get(
        "wifi",
        {}
    )

    for band in (
        "2.4GHz",
        "5GHz"
    ):
        if band in wifi:
            resultado["wifi"][band].update(
                wifi[band]
            )

    if "dns" in profile:
        dns = profile["dns"]

        # Allow-list do formato persistido. Campos internos do protocolo ZTE
        # não vazam para o perfil do atendente.
        for campo in (
            "domain_name",
            "ipv4_1",
            "ipv4_2",
            "ipv6_1",
            "ipv6_2",
            "hosts",
        ):
            if campo in dns:
                resultado["dns"][campo] = deepcopy(
                    dns[campo]
                )

    return resultado


profile_service = ProfileService()
