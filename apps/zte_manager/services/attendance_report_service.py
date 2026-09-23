from __future__ import annotations

from typing import Any


_OPERATION_LABELS = {
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

        changes = [
            item
            for item in timeline.get(
                "changes",
                []
            )
            if item.get("success")
        ]

        if changes:
            lines.extend([
                "",
                "Procedimentos realizados:",
            ])

            for change in reversed(
                changes
            ):
                operation = change.get(
                    "operation"
                )

                label = _OPERATION_LABELS.get(
                    operation,
                    operation,
                )

                target = change.get(
                    "target"
                )

                difference = self._change_summary(
                    change.get("before_json"),
                    change.get("after_json"),
                )

                text = f"- {label}"

                if target:
                    text += f" ({target})"

                if difference:
                    text += f": {difference}"

                lines.append(
                    text + "."
                )

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
            self._final_status(
                result
            ),
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
        return (
            "teste nativo executado pela ONT"
            if speed.get(
                "source"
            ) == "ont_native"
            else "teste HTTP executado pelo computador do atendente"
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
                "password",
                "passwd",
                "passphrase",
                "secret",
            )
        )
