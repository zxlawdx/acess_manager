from __future__ import annotations

from typing import Any

from apps.zte_manager.repositories.management_repository import (
    management_repository,
)
from apps.zte_manager.services.backup_service import (
    backup_compare_service,
)
from apps.zte_manager.services.fleet_service import (
    batch_management_service,
    drift_service,
    inventory_service,
)
from apps.zte_manager.services.operations_monitoring_service import (
    incident_correlation_service,
    monitoring_service,
    topology_service,
)
from apps.zte_manager.services.provisioning_service import (
    acs_service,
    firmware_manager_service,
    zero_touch_service,
)
from apps.zte_manager.services.remote_access_service import (
    remote_access_service,
)


class CPEManagementService:
    """
    Application Facade da plataforma de gerenciamento.

    Ele não conhece o protocolo ThinkLua diretamente. As operações locais
    passam por ZTEService; operações de frota podem usar ACS/USP ou Agent.
    """

    # =====================================================
    # INVENTÁRIO / PERFIS / DRIFT
    # =====================================================

    def sync_inventory(
        self,
        zte_service,
        data: dict[str, Any],
    ):
        return inventory_service.sync_current(
            zte_service,
            customer_name=data.get(
                "customer_name"
            ),
            topology={
                "olt": data.get("olt"),
                "cto": data.get("cto"),
                "pop": data.get("pop"),
                "agent_id": data.get(
                    "agent_id"
                ),
                "tags": data.get(
                    "tags"
                ) or [],
            },
        )

    def devices(
        self,
        *,
        query=None,
        status=None,
        limit=500,
    ):
        return {
            "devices": inventory_service.list(
                query=query,
                status=status,
                limit=limit,
            )
        }

    def update_device(
        self,
        device_id,
        values,
    ):
        return inventory_service.update(
            device_id,
            values,
        )

    def save_profile(
        self,
        data,
    ):
        return management_repository.save_profile(
            data[
                "name"
            ],
            data.get(
                "config"
            ) or {},
            description=data.get(
                "description"
            ),
            is_default=bool(
                data.get(
                    "is_default"
                )
            ),
        )

    def profiles(self):
        return {
            "profiles": (
                management_repository
                .list_profiles()
            )
        }

    def drift(
        self,
        zte_service,
        data,
    ):
        return drift_service.current(
            zte_service,
            profile_id=data.get(
                "profile_id"
            ),
            profile_name=data.get(
                "profile_name"
            ),
        )

    def remediate_drift(
        self,
        zte_service,
        data,
    ):
        if not data.get(
            "confirm"
        ):
            raise ValueError(
                "Confirme a correção das divergências."
            )

        zte_service.management_backup(
            reason="pre_config_drift"
        )

        return drift_service.remediate_current(
            zte_service,
            profile_id=data.get(
                "profile_id"
            ),
            profile_name=data.get(
                "profile_name"
            ),
        )

    # =====================================================
    # BATCH
    # =====================================================

    def create_batch(
        self,
        zte_service,
        data,
    ):
        operation = str(
            data.get(
                "operation"
            )
            or ""
        ).strip()

        allowed = {
            "profile_remediate",
            "acs_parameters",
            "acs_reboot",
            "gateway_command",
            "sync_inventory",
        }

        if operation not in allowed:
            raise ValueError(
                "Operação em lote não suportada."
            )

        return batch_management_service.create(
            operation=operation,
            device_ids=[
                int(item)
                for item in (
                    data.get(
                        "device_ids"
                    )
                    or []
                )
            ],
            payload=(
                data.get(
                    "payload"
                )
                or {}
            ),
            executor=lambda device, op, payload: self._batch_execute(
                zte_service,
                device,
                op,
                payload,
            ),
        )

    def batch_jobs(self):
        return {
            "jobs": (
                management_repository
                .list_batch_jobs()
            )
        }

    def batch_job(
        self,
        job_id,
    ):
        job = (
            management_repository
            .get_batch_job(
                int(
                    job_id
                )
            )
        )

        if job is None:
            raise ValueError(
                "Job não encontrado."
            )

        return job

    def _batch_execute(
        self,
        zte_service,
        device,
        operation,
        payload,
    ):
        if operation == "acs_parameters":
            parameters = (
                payload.get(
                    "parameters"
                )
                or {}
            )

            if not parameters:
                raise ValueError(
                    "Nenhum parâmetro ACS foi informado."
                )

            return acs_service.set_parameters(
                device[
                    "id"
                ],
                parameters,
            )

        if operation == "acs_reboot":
            return acs_service.reboot(
                device[
                    "id"
                ]
            )

        if operation == "gateway_command":
            agent_id = (
                device.get(
                    "agent_id"
                )
                or payload.get(
                    "agent_id"
                )
            )

            if not agent_id:
                raise RuntimeError(
                    "Equipamento sem Agent associado."
                )

            return remote_access_service.run_gateway_command(
                int(
                    agent_id
                ),
                payload.get(
                    "command"
                )
                or "ping",
                {
                    **(
                        payload.get(
                            "params"
                        )
                        or {}
                    ),
                    "host": (
                        (
                            payload.get(
                                "params"
                            )
                            or {}
                        ).get(
                            "host"
                        )
                        or str(
                            device.get(
                                "host"
                            )
                            or ""
                        ).split(
                            ":",
                            1,
                        )[0]
                    ),
                },
            )

        is_current = (
            zte_service.connected
            and str(
                zte_service.current_host
                or ""
            ).split(
                ":",
                1,
            )[0]
            == str(
                device.get(
                    "host"
                )
                or ""
            ).split(
                ":",
                1,
            )[0]
        )

        if operation == "profile_remediate":
            if not is_current:
                raise RuntimeError(
                    "Perfil local exige que esta ONT esteja conectada; use ACS/USP para frota remota."
                )

            return drift_service.remediate_current(
                zte_service,
                profile_id=payload.get(
                    "profile_id"
                ),
                profile_name=payload.get(
                    "profile_name"
                ),
            )

        if operation == "sync_inventory":
            if not is_current:
                raise RuntimeError(
                    "Sincronização ThinkLua exige sessão local/Agent; esta ONT não é a sessão atual."
                )

            return inventory_service.sync_current(
                zte_service,
                customer_name=device.get(
                    "customer_name"
                ),
                topology={
                    "olt": device.get(
                        "olt"
                    ),
                    "cto": device.get(
                        "cto"
                    ),
                    "pop": device.get(
                        "pop"
                    ),
                    "agent_id": device.get(
                        "agent_id"
                    ),
                    "tags": device.get(
                        "tags"
                    )
                    or [],
                },
            )

        raise ValueError(
            "Operação em lote inválida."
        )

    # =====================================================
    # REMOTE / AGENT / VPN
    # =====================================================

    def save_agent(
        self,
        data,
    ):
        return remote_access_service.save_agent(
            data
        )

    def agents(self):
        return {
            "agents": remote_access_service.agents()
        }

    def test_agent(
        self,
        agent_id,
    ):
        return remote_access_service.test_agent(
            int(
                agent_id
            )
        )

    def open_remote(
        self,
        zte_service,
        data,
    ):
        return remote_access_service.open(
            device_id=int(
                data[
                    "device_id"
                ]
            ),
            attendant=(
                zte_service.current_attendant
                or data.get(
                    "attendant"
                )
                or "default"
            ),
            ttl_minutes=int(
                data.get(
                    "ttl_minutes"
                )
                or 30
            ),
            remote_port=int(
                data.get(
                    "remote_port"
                )
                or 80
            ),
        )

    def close_remote(
        self,
        session_id,
    ):
        return remote_access_service.close(
            int(
                session_id
            )
        )

    def remote_sessions(self):
        return {
            "sessions": (
                remote_access_service.sessions()
            )
        }

    def gateway_command(
        self,
        data,
    ):
        return remote_access_service.run_gateway_command(
            int(
                data[
                    "agent_id"
                ]
            ),
            data[
                "command"
            ],
            data.get(
                "params"
            )
            or {},
        )

    # =====================================================
    # MONITORAMENTO / TOPOLOGIA / INCIDENTES
    # =====================================================

    def start_monitor(
        self,
        zte_service,
        data,
    ):
        return monitoring_service.start_current(
            zte_service,
            device_id=data.get(
                "device_id"
            ),
            duration_seconds=int(
                data.get(
                    "duration_seconds"
                )
                or 300
            ),
            interval_seconds=int(
                data.get(
                    "interval_seconds"
                )
                or 10
            ),
            ping_host=data.get(
                "ping_host"
            )
            or "1.1.1.1",
        )

    def monitor_status(
        self,
        run_id,
    ):
        return monitoring_service.status(
            int(
                run_id
            )
        )

    def stop_monitor(
        self,
        run_id,
    ):
        return monitoring_service.stop(
            int(
                run_id
            )
        )

    def topology(
        self,
        zte_service,
        device_id,
    ):
        device = (
            management_repository
            .get_device(
                int(
                    device_id
                )
            )
        )

        if device is None:
            raise ValueError(
                "Equipamento não encontrado."
            )

        current_clients = None

        if (
            zte_service.connected
            and str(
                zte_service.current_host
                or ""
            ).split(
                ":",
                1,
            )[0]
            == str(
                device.get(
                    "host"
                )
                or ""
            ).split(
                ":",
                1,
            )[0]
        ):
            try:
                current_clients = (
                    zte_service.all_clients()
                )
            except Exception:
                current_clients = None

        return topology_service.build(
            int(
                device_id
            ),
            current_clients=current_clients,
        )

    def correlate_incidents(
        self,
        minimum_devices=5,
    ):
        return (
            incident_correlation_service
            .correlate(
                minimum_devices=int(
                    minimum_devices
                )
            )
        )

    def incidents(
        self,
        status=None,
    ):
        return {
            "incidents": (
                incident_correlation_service
                .list(
                    status=status
                )
            )
        }

    # =====================================================
    # NETWORK CONTROL
    # =====================================================

    def network_overview(
        self,
        zte_service,
    ):
        return (
            zte_service
            .management_overview()
        )

    def qos_save(
        self,
        zte_service,
        data,
    ):
        return zte_service.save_management_qos(
            data[
                "kind"
            ],
            data.get(
                "config"
            )
            or {},
            confirm=bool(
                data.get(
                    "confirm"
                )
            ),
        )

    def qos_delete(
        self,
        zte_service,
        data,
    ):
        return zte_service.delete_management_qos(
            data[
                "kind"
            ],
            data[
                "id"
            ],
            confirm=bool(
                data.get(
                    "confirm"
                )
            ),
        )

    def firewall_set(
        self,
        zte_service,
        data,
    ):
        return zte_service.set_management_firewall(
            data.get(
                "config"
            )
            or {},
            confirm=bool(
                data.get(
                    "confirm"
                )
            ),
        )

    def firewall_rules(
        self,
        zte_service,
    ):
        return zte_service.firewall_rules()

    def firewall_rule_save(
        self,
        zte_service,
        data,
    ):
        return (
            zte_service
            .save_management_firewall_rule(
                data["kind"],
                data.get("config")
                or {},
                confirm=bool(
                    data.get("confirm")
                ),
            )
        )

    def firewall_rule_delete(
        self,
        zte_service,
        data,
    ):
        if not data.get(
            "id"
        ):
            raise ValueError(
                "Informe o id do filtro."
            )

        return (
            zte_service
            .delete_management_firewall_rule(
                data["kind"],
                data["id"],
                confirm=bool(
                    data.get("confirm")
                ),
            )
        )

    def filter_global_set(
        self,
        zte_service,
        data,
    ):
        return (
            zte_service
            .set_management_filter_global(
                data.get("config")
                or {},
                confirm=bool(
                    data.get("confirm")
                ),
            )
        )

    def sntp_set(
        self,
        zte_service,
        data,
    ):
        return zte_service.set_management_sntp(
            data.get(
                "config"
            )
            or {}
        )

    def tr069_set(
        self,
        zte_service,
        data,
    ):
        return zte_service.set_management_tr069(
            data.get(
                "config"
            )
            or {},
            confirm=bool(
                data.get(
                    "confirm"
                )
            ),
        )

    def wan_create(
        self,
        zte_service,
        data,
    ):
        return (
            zte_service
            .create_management_wan(
                data.get("config")
                or {},
                confirm=bool(
                    data.get("confirm")
                ),
                backup=True,
            )
        )

    def wan_update(
        self,
        zte_service,
        data,
    ):
        return zte_service.update_management_wan(
            data[
                "id"
            ],
            data.get(
                "config"
            )
            or {},
            confirm=bool(
                data.get(
                    "confirm"
                )
            ),
            backup=True,
        )

    def wan_action(
        self,
        zte_service,
        data,
    ):
        return zte_service.management_wan_action(
            data[
                "id"
            ],
            data[
                "action"
            ],
        )

    def bridge(
        self,
        zte_service,
        data,
    ):
        return zte_service.bridge_mode_assistant(
            data[
                "id"
            ],
            data.get(
                "config"
            )
            or {},
            confirm=bool(
                data.get(
                    "confirm"
                )
            ),
        )

    # =====================================================
    # BACKUP / FIRMWARE
    # =====================================================

    def backup(
        self,
        zte_service,
        data,
    ):
        return zte_service.management_backup(
            device_id=data.get(
                "device_id"
            ),
            reason=data.get(
                "reason"
            )
            or "manual",
        )

    def backups(
        self,
        device_id=None,
    ):
        return {
            "backups": (
                management_repository
                .list_backups(
                    device_id
                )
            )
        }

    def restore(
        self,
        zte_service,
        data,
    ):
        return zte_service.restore_management_backup(
            data[
                "backup_id"
            ],
            confirm=bool(
                data.get(
                    "confirm"
                )
            ),
        )

    def compare_backups(
        self,
        data,
    ):
        return backup_compare_service.compare(
            int(
                data["left_id"]
            ),
            int(
                data["right_id"]
            ),
        )

    def firmware_register(
        self,
        data,
    ):
        return firmware_manager_service.register(
            data
        )

    def firmware_list(
        self,
        model=None,
    ):
        return {
            "firmware": (
                firmware_manager_service
                .list(
                    model
                )
            )
        }

    def firmware_upgrade(
        self,
        zte_service,
        data,
    ):
        device_id = int(
            data[
                "device_id"
            ]
        )

        device = (
            management_repository
            .get_device(
                device_id
            )
        )

        if device is None:
            raise ValueError(
                "Equipamento não encontrado."
            )

        validation = (
            firmware_manager_service
            .validate_for_device(
                int(
                    data[
                        "firmware_id"
                    ]
                ),
                device,
            )
        )

        return zte_service.upload_management_firmware(
            validation[
                "firmware"
            ][
                "file_path"
            ],
            confirm=bool(
                data.get(
                    "confirm"
                )
            ),
            device_id=device_id,
        )

    # =====================================================
    # ACS / USP / ZERO TOUCH
    # =====================================================

    def configure_acs(
        self,
        data,
    ):
        return acs_service.configure(
            data
        )

    def acs_status(self):
        return acs_service.status()

    def acs_discover(
        self,
        device_id,
    ):
        return acs_service.discover(
            int(
                device_id
            )
        )

    def acs_parameters(
        self,
        data,
    ):
        return acs_service.set_parameters(
            int(
                data[
                    "device_id"
                ]
            ),
            data.get(
                "parameters"
            )
            or {},
        )

    def zero_touch(
        self,
        zte_service,
        data,
    ):
        if not data.get(
            "confirm"
        ):
            raise ValueError(
                "Confirme o provisionamento zero-touch."
            )

        return zero_touch_service.run_current(
            zte_service,
            profile_id=int(
                data[
                    "profile_id"
                ]
            ),
            customer_name=data.get(
                "customer_name"
            ),
            topology={
                "olt": data.get("olt"),
                "cto": data.get("cto"),
                "pop": data.get("pop"),
                "agent_id": data.get(
                    "agent_id"
                ),
                "tags": data.get(
                    "tags"
                )
                or [],
            },
        )


cpe_management_service = CPEManagementService()
