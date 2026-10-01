from __future__ import annotations

from typing import Any


_OPERATION_LABELS = {
    "profile_apply": "Aplicação da configuração padrão",
    "wifi_radio_update": "Ajuste de rádio Wi-Fi",
    "wifi_auto_optimization": "Otimização automática de canal Wi-Fi",
    "ssid_update": "Alteração de SSID",
    "dns_update": "Alteração de DNS",
    "band_steering_toggle": "Alteração de Band Steering",
    "band_steering_parameters": "Ajuste dos parâmetros de Band Steering",
    "wifi_radio_power": "Alteração do estado do rádio Wi-Fi",
    "dhcp_basic": "Alteração do DHCP",
    "dhcp_reservation": "Alteração de reserva DHCP",
    "upnp_update": "Alteração de UPnP",
    "f6201b_profile_apply": "Aplicação do perfil Wi-Fi e DNS",
    "f6201b_ssid_update": "Configuração de SSID",
    "f6201b_dns_update": "Configuração de DNS",
    "f6201b_form_update": "Configuração avançada do equipamento",
    "diagnostic_ping": "Teste de ping na ONT",
    "diagnostic_traceroute": "Teste de traceroute na ONT",
    "dhcp_reservation_save": "Cadastro de reserva DHCP",
    "dhcp_reservation_delete": "Exclusão de reserva DHCP",
    "wifi_schedule": "Configuração de horários Wi-Fi",
    "wps_update": "Configuração WPS",
    "dmz": "Configuração de DMZ",
    "admin_password": "Alteração de senha administrativa",
    "backup_configuration": "Backup de configuração",
    "easymesh_configure": "Configuração EasyMesh",
    "easymesh_pairing": "Pareamento EasyMesh",
    "port_forward_save": "Cadastro de redirecionamento de portas",
    "port_forward_delete": "Exclusão de redirecionamento de portas",
    "huawei_ipv4_filter_create": "IPv4 Filtering",
    "huawei_ipv4_filter_update": "IPv4 Filtering",
    "huawei_ipv4_filter_delete": "IPv4 Filtering",
}


class AttendanceReportService:
    """Builder do texto final da OS usando diagnóstico + audit trail."""

    def build(
        self,
        *,
        diagnostic: dict[str, Any],
        timeline: dict[str, Any],
    ) -> dict[str, Any]:
        result = (
            diagnostic.get(
                "post_validation"
            )
            or diagnostic
        )

        sections = result.get(
            "sections",
            {}
        )

        mode = diagnostic.get(
            "mode"
        ) or result.get(
            "mode"
        ) or "general"

        lines = [
            "Queixa:",
            self._complaint(
                mode
            ),
            "",
            "Diagnóstico:",
        ]

        device = sections.get(
            "device"
        ) or {}
        if not device and diagnostic.get("source") == "backend_authenticated_ont":
            device = {
                "modelo": diagnostic.get("model"),
                "firmware": diagnostic.get("firmware"),
            }

        if device:
            model = (
                device.get("modelo")
                or device.get("model")
                or "ZTE"
            )

            firmware = (
                device.get("firmware")
                or device.get("software")
            )

            lines.append(
                (
                    f"ONT {model}"
                    + (
                        f" / firmware {firmware}"
                        if firmware
                        else ""
                    )
                    + "."
                )
            )

        important = [
            item
            for item in result.get(
                "findings",
                []
            )
            if item.get("severity") in {
                "critical",
                "warning",
                "ok",
            }
        ]

        for finding in important:
            message = str(
                finding.get("message")
                or ""
            ).strip()

            if message:
                lines.append(
                    f"- {message}"
                )

        # A OS pertence à sessão inteira, não só ao último diagnóstico.
        # Inclui leituras/execuções registradas em outras abas, alterações
        # efetivas, tentativas não confirmadas e testes manuais, sempre
        # distinguindo um POST executado de uma alteração verificada.
        changes = timeline.get("changes", [])
        events = []
        for change in changes:
            operation = str(change.get("operation") or "operação")
            label = _OPERATION_LABELS.get(operation, operation.replace("_", " "))
            target = change.get("target")
            # Never include the attendant's saved profile identifier as a
            # hardware target in a customer-facing copy of the report.
            description = label + (
                " (" + self._safe_target(target) + ")"
                if target and operation != "profile_apply" else ""
            )
            outcome = change.get("outcome") or (
                "legacy_success_unverified" if change.get("success") else "failed"
            )
            # Older rows have no trustworthy field-specific verification.
            difference = self._change_summary(
                change.get("before_json"), change.get("after_json")
            ) if (outcome == "verified" or (
                outcome == "legacy_success_unverified" and change.get("success")
            )) else ""
            if operation == "profile_apply":
                details = self._profile_change_summary(
                    change.get("before_json"), change.get("after_json")
                )
                if details:
                    description += ": " + details
                # List executed steps even when the generic ZTE POST/readback
                # cannot certify every field. Do not call an accepted write
                # "modified" without specific verification evidence.
                stages = (change.get("after_json") or {}).get("_profile_steps", [])
                if isinstance(stages, list):
                    readable = [
                        step["name"] + (
                            " (comando aceito)" if step.get("accepted")
                            else " (falhou)"
                        )
                        for step in stages
                        if isinstance(step, dict) and step.get("name") in {
                            "Wi-Fi 2,4 GHz", "Wi-Fi 5 GHz", "Servidores DNS",
                        }
                    ]
                    if readable:
                        description += "; etapas: " + ", ".join(readable)
            elif operation in {
                "huawei_ipv4_filter_create",
                "huawei_ipv4_filter_update",
                "huawei_ipv4_filter_delete",
            }:
                details = self._huawei_ipv4_filter_summary(
                    change
                )
                if details:
                    description = details
            elif operation == "f6201b_profile_apply":
                safe = change.get("after_json") or {}
                stages = safe.get("stages", [])
                if isinstance(stages, list):
                    labels = []
                    for stage in stages:
                        if not isinstance(stage, dict):
                            continue
                        name = str(stage.get("name") or "").lower()
                        if "2.4" in name or "2,4" in name:
                            title = "Wi-Fi 2,4 GHz"
                        elif "5ghz" in name or "5 ghz" in name:
                            title = "Wi-Fi 5 GHz"
                        elif "dns" in name:
                            title = "Servidores DNS"
                        else:
                            continue
                        labels.append(title + (
                            " (verificada)" if stage.get("verified")
                            else " (não confirmada)"
                        ))
                    if labels:
                        description += "; etapas: " + ", ".join(labels)
                elif safe.get("noop") is True:
                    description += "; o equipamento já correspondia ao perfil"
            if (
                difference
                and operation not in {
                    "profile_apply",
                    "f6201b_profile_apply",
                    "huawei_ipv4_filter_create",
                    "huawei_ipv4_filter_update",
                    "huawei_ipv4_filter_delete",
                }
            ):
                description += ": " + difference
            description += {
                "verified": " — alteração verificada por releitura",
                "accepted": " — comando aceito; alteração ainda não verificada",
                "uncertain": " — resultado incerto após a tentativa",
                "failed": " — tentativa sem confirmação (falhou)",
                "attempted": " — tentativa iniciada",
                "legacy_success_unverified": (
                    " — execução registrada pelo fluxo legado; "
                    "sem prova padronizada de releitura"
                ),
            }.get(outcome, " — tentativa sem confirmação")
            events.append((change.get("created_at") or "", "change",
                           change.get("id") or 0, description))

        for entry in timeline.get("diagnostics", []):
            payload = entry.get("payload_json") or {}
            if not isinstance(payload, dict):
                payload = {}
            if payload.get("source") == "backend_authenticated_ont":
                count = len(payload.get("firmware_readings") or {})
                options = [
                    str(item.get("operation", "etapa")).replace("_", " ")
                    for item in payload.get("performed", [])
                    if isinstance(item, dict) and item.get("operation") != "leitura"
                ]
                detail = (f"Diagnóstico F6201B: {count} leituras confirmadas" +
                          ("; " + ", ".join(options) if options else ""))
            else:
                mode_name = {
                    "general": "geral",
                    "low_speed": "de velocidade",
                    "drops": "de quedas/intermitência",
                    "no_internet": "de ausência de Internet",
                    "wifi": "Wi-Fi",
                }.get(
                    str(payload.get("mode") or ""),
                    self._safe_target(entry.get("summary") or "geral"),
                )
                detail = "Diagnóstico " + mode_name
            errors = payload.get("errors") or {}
            if errors:
                detail += ("; etapas sem confirmação: " +
                           ", ".join(str(key) for key in errors.keys()))
            events.append((entry.get("created_at") or "", "diagnostic",
                           entry.get("id") or 0, detail))

        known_snapshots = {
            "speedtest": "Teste de velocidade realizado",
            "manual": "Captura manual das informações da ONT",
            "backup_configuration": "Backup da configuração",
            "automatic_diagnostic": "Coleta do diagnóstico automático",
            "firmware_diagnostic_get": "Inspeção de firmware realizada",
            "workstation_diagnostic": (
                "Verificação adicional do computador do técnico "
                "(não representa a conexão do cliente)"
            ),
        }
        for snapshot in timeline.get("snapshots", []):
            reason = snapshot.get("reason")
            if reason in known_snapshots:
                events.append((
                    snapshot.get("captured_at") or "", "snapshot",
                    snapshot.get("id") or 0, known_snapshots[reason],
                ))

        if events:
            lines.extend(["", "Atividades registradas nesta conexão:"])
            for _date, _kind, _id, description in sorted(events):
                lines.append("- " + description + ".")

        # Operational metrics belong to the customer's ONT only when the
        # authenticated ONT collector actually produced them. PC tests are
        # recorded separately in the session timeline above.
        ping = sections.get("ping") or {}
        if isinstance(ping, dict) and ping:
            lines.extend(["", "Conectividade testada pela ONT:"])
            if ping.get("medio_ms") not in (None, ""):
                lines.append("- Latência média: " +
                             self._fmt(ping["medio_ms"]) + " ms")
            try:
                success_count = int(ping["sucesso"])
                fail_count = int(ping["falha"])
                total = success_count + fail_count
                if total > 0 and success_count >= 0 and fail_count >= 0:
                    lines.append(
                        f"- Perda ICMP observada: {100 * fail_count / total:.1f}% "
                        f"({fail_count} falhas em {total} tentativas)"
                    )
            except (KeyError, ValueError, TypeError):
                pass
        trace = sections.get("traceroute") or {}
        if isinstance(trace, dict) and trace.get("hops") is not None:
            try:
                lines.append("- Traceroute da ONT: " +
                             str(int(trace["hops"])) + " saltos informados")
            except (ValueError, TypeError):
                pass

        speed = sections.get(
            "speedtest"
        ) or {}

        if speed:
            lines.extend([
                "",
                "Teste de velocidade:",
                (
                    f"- Download: {self._fmt(speed.get('download_mbps'))} Mbps"
                ),
                (
                    f"- Upload: {self._fmt(speed.get('upload_mbps'))} Mbps"
                ),
                (
                    f"- Origem: {self._speed_source(speed)}"
                ),
            ])

            if speed.get(
                "latency_ms"
            ) is not None:
                lines.append(
                    f"- Latência HTTP: {self._fmt(speed.get('latency_ms'))} ms"
                )

            if speed.get(
                "jitter_ms"
            ) is not None:
                lines.append(
                    f"- Jitter: {self._fmt(speed.get('jitter_ms'))} ms"
                )

        lines.extend([
            "",
            "Situação final:",
            (self._final_status(result) if diagnostic.get("sections") or
             diagnostic.get("post_validation") or
             diagnostic.get("firmware_readings") else
             "Não houve diagnóstico consolidado nesta sessão; " +
             "as ações acima refletem somente o histórico registrado."),
        ])

        return {
            "text": "\n".join(
                lines
            ),
            "status": result.get(
                "status"
            ),
            "mode": mode,
            "changes": len(
                changes
            ),
        }

    @staticmethod
    def _huawei_ipv4_filter_summary(
        change,
    ) -> str:
        operation = str(
            change.get("operation") or ""
        )
        source = (
            change.get("before_json")
            if operation == "huawei_ipv4_filter_delete"
            else change.get("after_json")
        )
        if not isinstance(source, dict):
            source = {}

        action = {
            "huawei_ipv4_filter_create": "Regra criada",
            "huawei_ipv4_filter_update": "Regra editada",
            "huawei_ipv4_filter_delete": "Regra excluída",
        }.get(
            operation,
            "Regra alterada",
        )
        name = str(
            source.get("name")
            or change.get("target")
            or "-"
        )
        protocol = str(
            source.get("protocol") or "-"
        )
        lan_start = str(
            source.get("lan_start_ip") or "-"
        )
        lan_end = str(
            source.get("lan_end_ip") or "-"
        )
        wan_start = str(
            source.get("wan_start_ip") or "-"
        )
        wan_end = str(
            source.get("wan_end_ip") or "-"
        )

        if protocol.upper() == "UDP":
            lan_port = source.get("lan_udp_port")
            wan_port = source.get("wan_udp_port")
        else:
            lan_port = source.get("lan_tcp_port")
            wan_port = source.get("wan_tcp_port")

        parts = [
            f"IPv4 Filtering - {action}: {name}",
            f"Protocolo: {protocol}",
            f"LAN: {lan_start}-{lan_end}",
            f"WAN: {wan_start}-{wan_end}",
        ]
        if lan_port not in (None, ""):
            parts.append(
                f"Porta LAN: {lan_port}"
            )
        if wan_port not in (None, ""):
            parts.append(
                f"Porta WAN: {wan_port}"
            )
        return "; ".join(parts)

    @staticmethod
    def _profile_change_summary(before, after) -> str:
        """Only safe, explicit configuration fields from pre/post readback.

        These differences are observations, not proof that a write succeeded:
        a parallel management client might have changed the equipment.
        """
        if not isinstance(before, dict) or not isinstance(after, dict):
            return ""
        previous = before.get("wifi") or {}
        current = after.get("wifi") or {}
        observed = []
        names = {
            "auto_channel": "modo do canal",
            "channel": "canal",
            "bandwidth": "largura",
            "standard": "padrão",
            "tx_power": "potência",
        }
        for band, public_band in (
            ("2.4GHz", "Wi-Fi 2,4 GHz"), ("5GHz", "Wi-Fi 5 GHz")
        ):
            prior = previous.get(band) if isinstance(previous, dict) else None
            latest = current.get(band) if isinstance(current, dict) else None
            if not isinstance(prior, dict) or not isinstance(latest, dict):
                continue
            changed = [
                description for key, description in names.items()
                if key in prior and key in latest
                and prior[key] != latest[key]
                # Channel is irrelevant when both readings still say Auto.
                and not (
                    key == "channel"
                    and prior.get("auto_channel") is True
                    and latest.get("auto_channel") is True
                )
            ]
            if changed:
                observed.append(public_band + ": " + ", ".join(changed))
        old_dns = before.get("dns")
        new_dns = after.get("dns")
        if isinstance(old_dns, dict) and isinstance(new_dns, dict):
            fields = ("ipv4_1", "ipv4_2", "ipv6_1", "ipv6_2", "domain_name")
            if any(key in old_dns and key in new_dns
                   and old_dns[key] != new_dns[key] for key in fields):
                observed.append("Servidores DNS: parâmetros diferentes")
        return ("diferenças observadas na releitura (não comprovam a "
                "origem da alteração): " + "; ".join(observed)) if observed else ""

    @staticmethod
    def _safe_target(value):
        # Nunca inserir identificadores de clientes ou URLs do roteador
        # diretamente em uma OS copiada para outro sistema.
        import re
        text = str(value or "")[:100]
        text = re.sub(
            r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b",
            "[MAC oculto]", text,
        )
        return text

    @staticmethod
    def _complaint(
        mode,
    ):
        return {
            "low_speed": "Cliente relata baixa velocidade/banda abaixo do esperado.",
            "drops": "Cliente relata quedas ou intermitência na conexão.",
            "no_internet": "Cliente relata ausência de conexão com a Internet.",
            "wifi": "Cliente relata problema relacionado à rede Wi-Fi.",
            "general": "Realizada verificação geral da conexão.",
        }.get(
            mode,
            "Realizada verificação da conexão.",
        )

    @staticmethod
    def _final_status(
        result,
    ):
        status = result.get(
            "status"
        )

        if status == "critical":
            return (
                "Diagnóstico finalizou com alerta crítico; necessário prosseguir "
                "com a tratativa indicada antes de encerrar o atendimento."
            )

        if status == "warning":
            return (
                "Conexão funcional, porém o diagnóstico manteve pontos de atenção "
                "descritos acima."
            )

        return (
            "Testes concluídos sem alertas relevantes nos critérios disponíveis."
        )

    @staticmethod
    def _speed_source(
        speed,
    ):
        if speed.get(
            "source"
        ) == "ont_native":
            return "teste nativo executado pela ONT"

        provider = {
            "cloudflare": "Cloudflare",
            "fast.com": "FAST.com / Netflix",
            "speedtest.net": "Speedtest.net",
            "librespeed": "LibreSpeed",
        }.get(
            speed.get("provider"),
            speed.get("provider") or "HTTP",
        )

        return (
            "teste executado pelo computador do atendente "
            f"via {provider}"
        )

    @staticmethod
    def _fmt(
        value,
    ):
        try:
            return f"{float(value):.1f}"
        except (
            TypeError,
            ValueError,
        ):
            return "-"

    def _change_summary(
        self,
        before,
        after,
    ) -> str:
        before_flat = self._flatten(
            before
        )

        after_flat = self._flatten(
            after
        )

        changed = []

        for key in sorted(
            set(before_flat)
            | set(after_flat)
        ):
            old = before_flat.get(
                key
            )

            new = after_flat.get(
                key
            )

            if old == new:
                continue

            if self._secret_key(
                key
            ):
                continue

            changed.append(
                f"{key.split('.')[-1]}: {old} → {new}"
            )

            if len(
                changed
            ) >= 4:
                break

        return "; ".join(
            changed
        )

    def _flatten(
        self,
        value,
        prefix="",
    ):
        result = {}

        if isinstance(
            value,
            dict,
        ):
            for key, item in value.items():
                path = (
                    f"{prefix}.{key}"
                    if prefix
                    else str(key)
                )

                result.update(
                    self._flatten(
                        item,
                        path,
                    )
                )

            return result

        if isinstance(
            value,
            list,
        ):
            for index, item in enumerate(
                value
            ):
                path = (
                    f"{prefix}[{index}]"
                )

                result.update(
                    self._flatten(
                        item,
                        path,
                    )
                )

            return result

        result[
            prefix
        ] = value

        return result

    @staticmethod
    def _secret_key(
        key,
    ):
        lower = str(
            key
        ).lower()

        return any(
            marker in lower
            for marker in (
                "password", "passwd", "passphrase", "secret",
                "token", "credential", "username", "private",
                "macaddr", "macaddress", "serial", "keypassphrase",
            )
        )
