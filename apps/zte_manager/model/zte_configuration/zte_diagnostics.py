import time

from .zte_post import post_menu


# =========================================================
# STRATEGY PATTERN - DIAGNÓSTICOS
# =========================================================


class DiagnosticStrategy:
    """
    Contrato comum para testes executados pela própria ONT.
    """

    def run(self, zte, config):
        raise NotImplementedError


class PingDiagnostic(DiagnosticStrategy):
    def run(self, zte, config):
        host = config.get(
            "host"
        )

        if not host:
            raise ValueError(
                "Informe o host para o ping."
            )

        # A mesma view networkDiag publica os backends de ping e traceroute.
        zte.get_view(
            "networkDiag",
            Menu3Location=0
        )

        zte.get_menu(
            "networkdiag_ping_lua.lua"
        )

        campos = [
            ("IF_ACTION", "PingDiagnosis"),
            ("_InstID", ""),
            ("Host", host),
            ("Interface", config.get("interface", "")),
            ("IPVersion", config.get("ip_version", "IPv4")),
            ("Btn_PingDiagnosis", ""),
        ]

        resposta = post_menu(
            zte,
            "networkdiag_ping_lua.lua",
            campos
        )

        zte._validar_resposta(
            resposta
        )

        # O JS oficial consulta o resultado até 8 vezes. Fazemos a primeira
        # leitura imediatamente e só esperamos 3 s quando o resultado é NULL.
        for tentativa in range(8):
            xml = zte.get_menu(
                "networkdiag_ping_lua.lua"
            )

            zte._validar_resposta(
                xml
            )

            instancias = (
                zte._parse_instances(xml)
                .get(
                    "OBJ_DEVPING_ID",
                    []
                )
            )

            if instancias:
                dados = instancias[0]
                resultado = dados.get(
                    "PingAck"
                )

                if resultado and resultado != "NULL":
                    return {
                        "host": host,
                        "interface": config.get("interface") or "Auto",
                        "ip_version": config.get("ip_version", "IPv4"),
                        "resultado": resultado,
                        "minimo_ms": dados.get("MinimumResponseTime"),
                        "maximo_ms": dados.get("MaximumResponseTime"),
                        "medio_ms": dados.get("AverageResponseTime"),
                        "sucesso": dados.get("SuccessCount"),
                        "falha": dados.get("FailureCount"),
                    }

            if tentativa < 7:
                time.sleep(3)

        raise TimeoutError(
            "A ONT não finalizou o ping dentro do tempo esperado."
        )


class TracerouteDiagnostic(DiagnosticStrategy):
    def run(self, zte, config):
        host = config.get(
            "host"
        )

        if not host:
            raise ValueError(
                "Informe o host para o traceroute."
            )

        max_hops = int(
            config.get("max_hops", 30)
        )

        timeout = int(
            config.get("timeout", 5000)
        )

        if not 1 <= max_hops <= 64:
            raise ValueError(
                "max_hops deve ficar entre 1 e 64."
            )

        if not 2000 <= timeout <= 10000:
            raise ValueError(
                "timeout deve ficar entre 2000 e 10000 ms."
            )

        zte.get_view(
            "networkDiag",
            Menu3Location=0
        )

        zte.get_menu(
            "networkdiag_traceroute_lua.lua"
        )

        campos = [
            ("IF_ACTION", "TraceRouteDiagnosis"),
            ("_InstID", ""),
            ("Control", "0"),
            ("Host", host),
            ("Interface", config.get("interface", "")),
            ("MaxHopCount", max_hops),
            ("Timeout", timeout),
            ("Protocol", config.get("protocol", "ICMP")),
            ("IPVersion", config.get("ip_version", "IPv4")),
            ("Btn_TraceRouteDiagnosis", ""),
        ]

        resposta = post_menu(
            zte,
            "networkdiag_traceroute_lua.lua",
            campos
        )

        zte._validar_resposta(
            resposta
        )

        # O firmware pode manter traceroute por muito tempo. Para não segurar
        # o atendimento indefinidamente, a API limita o polling a 60 segundos.
        for tentativa in range(20):
            xml = zte.get_menu(
                "networkdiag_traceroute_lua.lua"
            )

            zte._validar_resposta(
                xml
            )

            instancias = (
                zte._parse_instances(xml)
                .get(
                    "OBJ_TRACERT_ID",
                    []
                )
            )

            if instancias:
                dados = instancias[0]

                if dados.get("Flag") != "1":
                    return {
                        "host": host,
                        "interface": config.get("interface") or "Auto",
                        "ip_version": config.get("ip_version", "IPv4"),
                        "protocol": config.get("protocol", "ICMP"),
                        "resultado": dados.get("Result"),
                        "hops": dados.get("NumberOfPRouteHops"),
                        "response_time": dados.get("ResponseTime"),
                    }

            if tentativa < 19:
                time.sleep(3)

        # O backend também expõe TRStop. Se a nossa janela de polling acabar,
        # encerramos o diagnóstico na ONT antes de devolver timeout para a UI.
        # A parada é best effort para não esconder o erro original caso o
        # firmware já tenha encerrado a sessão do diagnóstico.
        try:
            post_menu(
                zte,
                "networkdiag_traceroute_lua.lua",
                [
                    ("IF_ACTION", "TRStop"),
                    ("_InstID", ""),
                    ("Control", "0"),
                    ("Host", host),
                    ("Interface", config.get("interface", "")),
                    ("MaxHopCount", max_hops),
                    ("Timeout", timeout),
                    ("Protocol", config.get("protocol", "ICMP")),
                    ("IPVersion", config.get("ip_version", "IPv4")),
                ]
            )
        except Exception:
            pass

        raise TimeoutError(
            "A ONT não finalizou o traceroute dentro do tempo esperado."
        )
