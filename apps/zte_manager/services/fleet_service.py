from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Any, Callable

from apps.zte_manager.repositories.management_repository import (
    ManagementRepository,
    management_repository,
)


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _first_value(
    source: dict[str, Any],
    *keys: str,
):
    for key in keys:
        value = source.get(
            key
        )

        if value not in (
            None,
            "",
        ):
            return value

    return None


def _normalize_scalar(value):
    if isinstance(
        value,
        str,
    ):
        return value.strip()

    return value


def _diff(
    expected: Any,
    actual: Any,
    path: str = "",
) -> list[dict[str, Any]]:
    """
    Compara somente campos presentes no perfil esperado.

    Isso é importante para firmware heterogêneo: campos extras da ONT não
    viram drift apenas por não existirem no perfil corporativo.
    """
    result = []

    if isinstance(
        expected,
        dict,
    ):
        actual_dict = (
            actual
            if isinstance(actual, dict)
            else {}
        )

        for key, expected_value in expected.items():
            child = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            result.extend(
                _diff(
                    expected_value,
                    actual_dict.get(key),
                    child,
                )
            )

        return result

    if isinstance(
        expected,
        list,
    ):
        expected_normalized = [
            _normalize_scalar(item)
            for item in expected
        ]

        actual_normalized = (
            [
                _normalize_scalar(item)
                for item in actual
            ]
            if isinstance(actual, list)
            else []
        )

        if expected_normalized != actual_normalized:
            result.append({
                "path": path,
                "expected": expected,
                "actual": actual,
            })

        return result

    if _normalize_scalar(
        expected
    ) != _normalize_scalar(
        actual
    ):
        result.append({
            "path": path,
            "expected": expected,
            "actual": actual,
        })

    return result


class InventoryService:
    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository

    def sync_current(
        self,
        zte_service,
        *,
        customer_name: str | None = None,
        topology: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Captura a ONT da sessão atual e cria/atualiza o inventário.

        Senhas PPPoE/Wi-Fi não entram no inventário. O current_configuration
        utilizado aqui já é o formato normalizado do app e não pede reveal.
        """
        device = zte_service.device_status()
        optical = zte_service.optical_status()
        config = zte_service.current_configuration()

        try:
            capabilities = zte_service.probe_capabilities()
        except Exception as error:
            capabilities = {
                "error": str(error),
                "features": [],
            }

        topology = topology or {}

        serial = _first_value(
            device,
            "serial",
            "serial_number",
            "sn",
            "SerialNumber",
            "SerialNum",
        )

        mac = _first_value(
            device,
            "mac",
            "mac_address",
            "MacAddress",
            "MACAddress",
        )

        model = _first_value(
            device,
            "modelo",
            "model",
            "ModelName",
        )

        firmware = _first_value(
            device,
            "firmware",
            "software",
            "SoftwareVersion",
        )

        uptime = _first_value(
            optical,
            "pon_uptime",
            "uptime",
        )

        key = (
            str(serial).strip()
            if serial
            else str(mac).strip()
            if mac
            else str(
                zte_service.current_host
                or ""
            ).strip()
        )

        if not key:
            raise RuntimeError(
                "Não foi possível obter uma identidade estável da ONT."
            )

        record = self.repository.upsert_device({
            "key": key,
            "customer_name": customer_name,
            "host": zte_service.current_host,
            "model": model,
            "serial": serial,
            "mac": mac,
            "firmware": firmware,
            "status": "online",
            "rx_power": optical.get(
                "rx_power_dbm"
            ),
            "uptime": uptime,
            "olt": topology.get("olt"),
            "cto": topology.get("cto"),
            "pop": topology.get("pop"),
            "agent_id": topology.get(
                "agent_id"
            ),
            "tags": topology.get(
                "tags",
                [],
            ),
            "capabilities": capabilities,
            "current_config": config,
            "metadata": {
                "device": device,
                "optical": optical,
                "adapter": (
                    zte_service._adapter.name
                    if zte_service._adapter
                    else None
                ),
                "attendant": (
                    zte_service.current_attendant
                ),
            },
            "last_seen": _now(),
        })

        return {
            "success": True,
            "device": record,
        }

    def list(
        self,
        **filters,
    ):
        return self.repository.list_devices(
            **filters
        )

    def update(
        self,
        device_id: int,
        values: dict[str, Any],
    ):
        return self.repository.update_device_metadata(
            device_id,
            values,
        )


class DriftService:
    """
    Specification/Remediation service.

    O perfil corporativo pode conter wifi, dns, band_steering e outros blocos.
    A comparação é genérica; a correção automática é deliberadamente limitada
    às operações para as quais o app já possui writer validado.
    """

    SAFE_ROOTS = {
        "wifi",
        "dns",
        "band_steering",
    }

    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository

    def compare(
        self,
        current: dict[str, Any],
        expected: dict[str, Any],
    ) -> dict[str, Any]:
        items = _diff(
            expected,
            current,
        )

        for item in items:
            root = (
                item["path"].split(
                    ".",
                    1,
                )[0]
            )

            item["remediable"] = (
                root in self.SAFE_ROOTS
            )

            item["severity"] = (
                "warning"
                if item["remediable"]
                else "info"
            )

        return {
            "compliant": not items,
            "count": len(items),
            "remediable": sum(
                1
                for item in items
                if item["remediable"]
            ),
            "items": items,
        }

    def current(
        self,
        zte_service,
        *,
        profile_id: int | None = None,
        profile_name: str | None = None,
    ) -> dict[str, Any]:
        profile = self._profile(
            profile_id,
            profile_name,
        )

        current = zte_service.current_configuration()

        # O Band Steering não faz parte do perfil antigo de atendente, então
        # anexamos quando o perfil corporativo o utilizar.
        if "band_steering" in profile["config"]:
            try:
                current[
                    "band_steering"
                ] = zte_service.band_steering_status()
            except Exception as error:
                current[
                    "band_steering"
                ] = {
                    "available": False,
                    "error": str(error),
                }

        result = self.compare(
            current,
            profile["config"],
        )

        return {
            "profile": profile,
            "current": current,
            **result,
        }

    def remediate_current(
        self,
        zte_service,
        *,
        profile_id: int | None = None,
        profile_name: str | None = None,
    ) -> dict[str, Any]:
        assessment = self.current(
            zte_service,
            profile_id=profile_id,
            profile_name=profile_name,
        )

        config = assessment[
            "profile"
        ][
            "config"
        ]

        results = []

        wifi = config.get(
            "wifi"
        ) or {}

        for band, values in wifi.items():
            try:
                result = zte_service.set_wifi_radio(
                    band,
                    deepcopy(values),
                )

                results.append({
                    "section": f"wifi.{band}",
                    "success": True,
                    "result": result,
                })
            except Exception as error:
                results.append({
                    "section": f"wifi.{band}",
                    "success": False,
                    "error": str(error),
                })

        dns = config.get(
            "dns"
        )

        if dns:
            try:
                result = zte_service.set_dns(
                    deepcopy(dns)
                )

                results.append({
                    "section": "dns",
                    "success": True,
                    "result": result,
                })
            except Exception as error:
                results.append({
                    "section": "dns",
                    "success": False,
                    "error": str(error),
                })

        steering = config.get(
            "band_steering"
        )

        if steering:
            try:
                if "enabled" in steering:
                    zte_service.set_band_steering(
                        bool(
                            steering[
                                "enabled"
                            ]
                        )
                    )

                parameters = (
                    steering.get(
                        "parameters"
                    )
                    or {}
                )

                if parameters:
                    zte_service.configure_band_steering(
                        parameters
                    )

                results.append({
                    "section": "band_steering",
                    "success": True,
                })
            except Exception as error:
                results.append({
                    "section": "band_steering",
                    "success": False,
                    "error": str(error),
                })

        after = self.current(
            zte_service,
            profile_id=assessment[
                "profile"
            ][
                "id"
            ],
        )

        return {
            "success": all(
                item.get("success")
                for item in results
            ) if results else True,
            "steps": results,
            "before": assessment,
            "after": after,
        }

    def _profile(
        self,
        profile_id,
        profile_name,
    ) -> dict[str, Any]:
        profile = (
            self.repository.get_profile(
                profile_id
            )
            if profile_id is not None
            else self.repository.get_profile(
                name=profile_name
            )
            if profile_name
            else self.repository.get_profile(
                default=True
            )
        )

        if profile is None:
            raise ValueError(
                "Nenhum perfil corporativo foi encontrado."
            )

        return profile


class BatchManagementService:
    """
    Job manager para alterações em lote.

    A execução real é fornecida por callback. Isso permite usar a sessão local,
    um Agent ou um ACS sem duplicar o mecanismo de fila/auditoria.
    """

    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository
        self._threads: dict[int, Thread] = {}
        self._lock = Lock()

    def create(
        self,
        *,
        operation: str,
        device_ids: list[int],
        payload: dict[str, Any],
        executor: Callable[
            [dict[str, Any], str, dict[str, Any]],
            dict[str, Any]
        ],
    ) -> dict[str, Any]:
        if not device_ids:
            raise ValueError(
                "Selecione pelo menos um equipamento."
            )

        job = self.repository.create_batch_job(
            operation,
            device_ids,
            payload,
        )

        thread = Thread(
            target=self._run,
            args=(
                job["id"],
                operation,
                device_ids,
                payload,
                executor,
            ),
            daemon=True,
            name=f"cpe-batch-{job['id']}",
        )

        with self._lock:
            self._threads[
                job["id"]
            ] = thread

        thread.start()

        return {
            **job,
            "status": "running",
        }

    def _run(
        self,
        job_id: int,
        operation: str,
        device_ids: list[int],
        payload: dict[str, Any],
        executor,
    ):
        results = []

        self.repository.update_batch_job(
            job_id,
            status="running",
            results=results,
        )

        for device_id in device_ids:
            device = self.repository.get_device(
                device_id
            )

            if device is None:
                results.append({
                    "device_id": device_id,
                    "success": False,
                    "error": "Equipamento não encontrado.",
                })
                continue

            try:
                result = executor(
                    device,
                    operation,
                    deepcopy(payload),
                )

                results.append({
                    "device_id": device_id,
                    "success": bool(
                        result.get(
                            "success",
                            True,
                        )
                    ),
                    "result": result,
                })

            except Exception as error:
                results.append({
                    "device_id": device_id,
                    "success": False,
                    "error": str(error),
                })

            self.repository.update_batch_job(
                job_id,
                status="running",
                results=results,
            )

        final_status = (
            "completed"
            if all(
                item.get("success")
                for item in results
            )
            else "failed"
            if results and all(
                not item.get("success")
                for item in results
            )
            else "completed"
        )

        self.repository.update_batch_job(
            job_id,
            status=final_status,
            results=results,
        )

        with self._lock:
            self._threads.pop(
                job_id,
                None,
            )


inventory_service = InventoryService()
drift_service = DriftService()
batch_management_service = BatchManagementService()
