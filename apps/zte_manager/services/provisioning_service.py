from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from apps.zte_manager.repositories.management_repository import (
    ManagementRepository,
    management_repository,
)
from apps.zte_manager.services.fleet_service import (
    DriftService,
    InventoryService,
)


class ACSProvider(ABC):
    name = "acs"

    @abstractmethod
    def find_device(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def set_parameters(
        self,
        remote_id: str,
        parameters: dict[str, Any],
        *,
        connection_request: bool = True,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def reboot(
        self,
        remote_id: str,
    ) -> dict[str, Any]:
        raise NotImplementedError


class GenieACSProvider(ACSProvider):
    """
    Adapter para o NBI HTTP do GenieACS.

    Tokens/senhas não são persistidos em management.sqlite3. Use variáveis
    ZTE_ACS_TOKEN, ZTE_ACS_USER e ZTE_ACS_PASSWORD no ambiente do app.
    """

    name = "genieacs"

    def __init__(
        self,
        config: dict[str, Any],
    ):
        self.base_url = str(
            config.get(
                "base_url"
            )
            or "http://127.0.0.1:7557"
        ).rstrip("/")

        self.timeout = int(
            config.get(
                "timeout"
            )
            or 20
        )

        self.session = requests.Session()

        token = os.getenv(
            "ZTE_ACS_TOKEN"
        )

        if token:
            self.session.headers[
                "Authorization"
            ] = f"Bearer {token}"

        user = os.getenv(
            "ZTE_ACS_USER"
        )

        password = os.getenv(
            "ZTE_ACS_PASSWORD"
        )

        if user:
            self.session.auth = (
                user,
                password or "",
            )

    def find_device(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any] | None:
        clauses = []

        serial = device.get(
            "serial"
        )

        if serial:
            clauses.append({
                "_deviceId._SerialNumber": str(
                    serial
                ),
            })

        mac = device.get(
            "mac"
        )

        if mac:
            clauses.append({
                "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANIPConnection.1.MACAddress._value": str(
                    mac
                ),
            })

        for query in clauses:
            response = self.session.get(
                self.base_url + "/devices/",
                params={
                    "query": __import__(
                        "json"
                    ).dumps(
                        query
                    ),
                    "projection": (
                        "_id,_deviceId,"
                        "InternetGatewayDevice.DeviceInfo."
                        "SoftwareVersion"
                    ),
                },
                timeout=self.timeout,
            )

            response.raise_for_status()

            items = response.json()

            if items:
                return items[0]

        return None

    def _task(
        self,
        remote_id: str,
        task: dict[str, Any],
        *,
        connection_request: bool = True,
    ):
        response = self.session.post(
            (
                self.base_url
                + "/devices/"
                + quote(
                    remote_id,
                    safe="",
                )
                + "/tasks"
            ),
            params={
                "connection_request": (
                    "true"
                    if connection_request
                    else "false"
                ),
            },
            json=task,
            timeout=max(
                self.timeout,
                60,
            ),
        )

        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            payload = {
                "text": response.text,
            }

        return {
            "success": True,
            "provider": self.name,
            "response": payload,
        }

    def set_parameters(
        self,
        remote_id: str,
        parameters: dict[str, Any],
        *,
        connection_request: bool = True,
    ) -> dict[str, Any]:
        parameter_values = [
            [
                name,
                value,
                type_name,
            ]
            for name, spec in parameters.items()
            for value, type_name in [
                (
                    (
                        spec.get("value")
                        if isinstance(
                            spec,
                            dict,
                        )
                        else spec
                    ),
                    (
                        spec.get(
                            "type",
                            "xsd:string",
                        )
                        if isinstance(
                            spec,
                            dict,
                        )
                        else "xsd:string"
                    ),
                )
            ]
        ]

        return self._task(
            remote_id,
            {
                "name": "setParameterValues",
                "parameterValues": parameter_values,
            },
            connection_request=connection_request,
        )

    def reboot(
        self,
        remote_id: str,
    ) -> dict[str, Any]:
        return self._task(
            remote_id,
            {
                "name": "reboot",
            },
            connection_request=True,
        )


class USPBridgeProvider(ACSProvider):
    """
    Adapter para um controller USP/TR-369 externo.

    USP não padroniza uma API REST de operador. Portanto esta camada fala com
    um bridge configurável que exponha /devices/<endpoint>/operations.
    O token fica em ZTE_USP_TOKEN, nunca no banco local.
    """

    name = "usp_bridge"

    def __init__(
        self,
        config: dict[str, Any],
    ):
        self.base_url = str(
            config.get(
                "base_url"
            )
            or ""
        ).rstrip("/")

        if not self.base_url:
            raise RuntimeError(
                "Configure a URL do bridge USP."
            )

        self.timeout = int(
            config.get(
                "timeout"
            )
            or 20
        )

        self.session = requests.Session()

        token = os.getenv(
            "ZTE_USP_TOKEN"
        )

        if token:
            self.session.headers[
                "Authorization"
            ] = f"Bearer {token}"

    def find_device(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any] | None:
        key = (
            device.get(
                "serial"
            )
            or device.get(
                "mac"
            )
            or device.get(
                "key"
            )
        )

        if not key:
            return None

        response = self.session.get(
            self.base_url + "/devices",
            params={
                "q": key,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        payload = response.json()

        if isinstance(
            payload,
            dict,
        ):
            items = (
                payload.get(
                    "devices"
                )
                or payload.get(
                    "items"
                )
                or []
            )
        else:
            items = payload

        return (
            items[0]
            if items
            else None
        )

    def _operation(
        self,
        remote_id,
        payload,
    ):
        response = self.session.post(
            (
                self.base_url
                + "/devices/"
                + quote(
                    remote_id,
                    safe="",
                )
                + "/operations"
            ),
            json=payload,
            timeout=max(
                self.timeout,
                60,
            ),
        )

        response.raise_for_status()

        return {
            "success": True,
            "provider": self.name,
            "response": response.json(),
        }

    def set_parameters(
        self,
        remote_id: str,
        parameters: dict[str, Any],
        *,
        connection_request: bool = True,
    ) -> dict[str, Any]:
        return self._operation(
            remote_id,
            {
                "operation": "set",
                "parameters": parameters,
            },
        )

    def reboot(
        self,
        remote_id: str,
    ) -> dict[str, Any]:
        return self._operation(
            remote_id,
            {
                "operation": "operate",
                "command": (
                    "Device.Reboot()"
                ),
            },
        )


class ACSService:
    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository

    def configure(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        safe = {
            "provider": config.get(
                "provider"
            )
            or "genieacs",
            "base_url": config.get(
                "base_url"
            )
            or "",
            "timeout": int(
                config.get(
                    "timeout"
                )
                or 20
            ),
        }

        self.repository.set_setting(
            "acs",
            safe,
        )

        return {
            "success": True,
            "config": safe,
            "secrets": {
                "acs_token": bool(
                    os.getenv(
                        "ZTE_ACS_TOKEN"
                    )
                ),
                "acs_user": bool(
                    os.getenv(
                        "ZTE_ACS_USER"
                    )
                ),
                "usp_token": bool(
                    os.getenv(
                        "ZTE_USP_TOKEN"
                    )
                ),
            },
        }

    def status(self):
        config = (
            self.repository.get_setting(
                "acs",
                {},
            )
            or {}
        )

        return {
            "configured": bool(
                config.get(
                    "base_url"
                )
            ),
            "config": config,
            "secrets": {
                "acs_token": bool(
                    os.getenv(
                        "ZTE_ACS_TOKEN"
                    )
                ),
                "acs_user": bool(
                    os.getenv(
                        "ZTE_ACS_USER"
                    )
                ),
                "usp_token": bool(
                    os.getenv(
                        "ZTE_USP_TOKEN"
                    )
                ),
            },
        }

    def provider(self) -> ACSProvider:
        config = (
            self.repository.get_setting(
                "acs",
                {},
            )
            or {}
        )

        provider = str(
            config.get(
                "provider"
            )
            or "genieacs"
        ).lower()

        if provider == "genieacs":
            return GenieACSProvider(
                config
            )

        if provider in {
            "usp",
            "usp_bridge",
            "tr369",
        }:
            return USPBridgeProvider(
                config
            )

        raise ValueError(
            "Provider ACS/USP não suportado."
        )

    def discover(
        self,
        device_id: int,
    ):
        device = self.repository.get_device(
            device_id
        )

        if device is None:
            raise ValueError(
                "Equipamento não encontrado."
            )

        remote = self.provider().find_device(
            device
        )

        return {
            "success": remote is not None,
            "device": device,
            "remote": remote,
        }

    def set_parameters(
        self,
        device_id: int,
        parameters: dict[str, Any],
    ):
        device = self.repository.get_device(
            device_id
        )

        if device is None:
            raise ValueError(
                "Equipamento não encontrado."
            )

        provider = self.provider()
        remote = provider.find_device(
            device
        )

        if not remote:
            raise RuntimeError(
                "Equipamento não localizado no ACS/USP."
            )

        remote_id = (
            remote.get(
                "_id"
            )
            or remote.get(
                "endpoint_id"
            )
            or remote.get(
                "id"
            )
        )

        if not remote_id:
            raise RuntimeError(
                "ACS/USP não devolveu o identificador remoto do CPE."
            )

        return provider.set_parameters(
            str(
                remote_id
            ),
            parameters,
        )

    def reboot(
        self,
        device_id: int,
    ):
        device = self.repository.get_device(
            device_id
        )

        if device is None:
            raise ValueError(
                "Equipamento não encontrado."
            )

        provider = self.provider()
        remote = provider.find_device(
            device
        )

        if not remote:
            raise RuntimeError(
                "Equipamento não localizado no ACS/USP."
            )

        remote_id = (
            remote.get("_id")
            or remote.get(
                "endpoint_id"
            )
            or remote.get("id")
        )

        return provider.reboot(
            str(
                remote_id
            )
        )


class FirmwareManagerService:
    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
        digest = hashlib.sha256()

        with path.open(
            "rb"
        ) as handle:
            for chunk in iter(
                lambda: handle.read(
                    1024 * 1024
                ),
                b"",
            ):
                digest.update(
                    chunk
                )

        return digest.hexdigest()

    def register(
        self,
        data: dict[str, Any],
    ):
        path = Path(
            data.get(
                "file_path"
            )
            or ""
        ).expanduser()

        if not path.is_file():
            raise ValueError(
                "Arquivo de firmware não encontrado."
            )

        return self.repository.register_firmware({
            **data,
            "file_path": str(
                path.resolve()
            ),
            "sha256": self._sha256(
                path
            ),
        })

    def list(
        self,
        model=None,
    ):
        return self.repository.list_firmware(
            model
        )

    def validate_for_device(
        self,
        firmware_id: int,
        device: dict[str, Any],
    ) -> dict[str, Any]:
        entries = self.repository.list_firmware(
            device.get(
                "model"
            )
        )

        firmware = next((
            item
            for item in entries
            if int(
                item["id"]
            ) == int(
                firmware_id
            )
        ), None)

        if firmware is None:
            raise ValueError(
                "Firmware não cadastrado para este modelo."
            )

        if not firmware.get(
            "approved"
        ):
            raise RuntimeError(
                "Firmware não está marcado como aprovado."
            )

        path = Path(
            firmware[
                "file_path"
            ]
        )

        if not path.is_file():
            raise RuntimeError(
                "Arquivo de firmware não está mais disponível."
            )

        actual_sha = self._sha256(
            path
        )

        if (
            firmware.get(
                "sha256"
            )
            and actual_sha
            != firmware[
                "sha256"
            ]
        ):
            raise RuntimeError(
                "SHA-256 do firmware mudou desde o cadastro."
            )

        return {
            "firmware": firmware,
            "device": device,
            "sha256": actual_sha,
        }


class ZeroTouchProvisioningService:
    """
    Pipeline de provisionamento da ONT conectada.

    Profile format:
      wifi / dns / band_steering
      sntp
      tr069
      wan: {instance_id, ...}
      acs_parameters: {...}

    As etapas são independentes e cada resultado é persistido.
    """

    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository
        self.inventory = InventoryService(
            repository
        )
        self.drift = DriftService(
            repository
        )
        self.acs = ACSService(
            repository
        )

    def run_current(
        self,
        zte_service,
        *,
        profile_id: int,
        customer_name: str | None = None,
        topology: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = self.repository.get_profile(
            profile_id
        )

        if profile is None:
            raise ValueError(
                "Perfil de provisionamento não encontrado."
            )

        inventory = self.inventory.sync_current(
            zte_service,
            customer_name=customer_name,
            topology=topology,
        )

        device = inventory[
            "device"
        ]

        device_id = device[
            "id"
        ]

        steps = []

        def step(
            name,
            callback,
        ):
            self.repository.add_provisioning_event(
                device_id=device_id,
                status="running",
                step=name,
            )

            try:
                result = callback()

                item = {
                    "step": name,
                    "success": True,
                    "result": result,
                }

                self.repository.add_provisioning_event(
                    device_id=device_id,
                    status="success",
                    step=name,
                    payload=result,
                )

            except Exception as error:
                item = {
                    "step": name,
                    "success": False,
                    "error": str(error),
                }

                self.repository.add_provisioning_event(
                    device_id=device_id,
                    status="failed",
                    step=name,
                    payload={
                        "error": str(error),
                    },
                )

            steps.append(
                item
            )

            return item

        step(
            "backup",
            lambda: zte_service.management_backup(
                device_id=device_id,
                reason="zero_touch_pre",
            ),
        )

        step(
            "config_drift_remediation",
            lambda: self.drift.remediate_current(
                zte_service,
                profile_id=profile_id,
            ),
        )

        config = profile[
            "config"
        ]

        if config.get(
            "sntp"
        ):
            step(
                "sntp",
                lambda: zte_service.set_management_sntp(
                    config[
                        "sntp"
                    ]
                ),
            )

        if config.get(
            "tr069"
        ):
            step(
                "tr069",
                lambda: zte_service.set_management_tr069(
                    config[
                        "tr069"
                    ]
                ),
            )

        if config.get(
            "wan"
        ):
            wan = dict(
                config[
                    "wan"
                ]
            )
            instance_id = wan.pop(
                "instance_id",
                None,
            )

            if instance_id:
                step(
                    "wan",
                    lambda: zte_service.update_management_wan(
                        instance_id,
                        wan,
                    ),
                )

        acs_parameters = config.get(
            "acs_parameters"
        )

        if acs_parameters:
            step(
                "acs_parameters",
                lambda: self.acs.set_parameters(
                    device_id,
                    acs_parameters,
                ),
            )

        final_inventory = step(
            "validate_inventory",
            lambda: self.inventory.sync_current(
                zte_service,
                customer_name=(
                    customer_name
                    or device.get(
                        "customer_name"
                    )
                ),
                topology=topology,
            ),
        )

        success = all(
            item.get(
                "success"
            )
            for item in steps
        )

        self.repository.add_provisioning_event(
            device_id=device_id,
            status=(
                "completed"
                if success
                else "partial"
            ),
            step="complete",
            payload={
                "success": success,
            },
        )

        return {
            "success": success,
            "device_id": device_id,
            "profile": profile,
            "steps": steps,
            "device": (
                final_inventory.get(
                    "result",
                    {}
                ).get(
                    "device"
                )
                if final_inventory.get(
                    "success"
                )
                else device
            ),
        }


acs_service = ACSService()
firmware_manager_service = FirmwareManagerService()
zero_touch_service = ZeroTouchProvisioningService()
