from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from apps.zte_manager.repositories.management_repository import (
    ManagementRepository,
    management_repository,
)


def _now():
    return datetime.now(
        timezone.utc
    )


def _free_local_port() -> int:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        sock.bind(
            ("127.0.0.1", 0)
        )

        return int(
            sock.getsockname()[1]
        )


@dataclass(frozen=True)
class GatewayCommand:
    kind: str
    argv: list[str]
    description: str


class GatewayCommandPolicy:
    """
    Allow-list para o terminal do gateway.

    A UI oferece um terminal de diagnóstico, mas o backend não concatena texto
    do usuário em shell. Cada operação vira argv conhecido, reduzindo risco de
    command injection em um gateway de produção.
    """

    @staticmethod
    def build(
        kind: str,
        params: dict[str, Any],
    ) -> GatewayCommand:
        kind = str(
            kind or ""
        ).strip().lower()

        if kind == "ping":
            host = GatewayCommandPolicy._host(
                params.get("host")
            )
            count = max(
                1,
                min(
                    int(
                        params.get("count")
                        or 5
                    ),
                    20,
                ),
            )

            return GatewayCommand(
                kind,
                [
                    "ping",
                    "-c",
                    str(count),
                    host,
                ],
                f"Ping {host}",
            )

        if kind == "traceroute":
            host = GatewayCommandPolicy._host(
                params.get("host")
            )

            return GatewayCommand(
                kind,
                [
                    "traceroute",
                    "-n",
                    "-m",
                    "20",
                    host,
                ],
                f"Traceroute {host}",
            )

        if kind == "route":
            return GatewayCommand(
                kind,
                [
                    "ip",
                    "route",
                    "show",
                ],
                "Tabela de rotas",
            )

        if kind == "address":
            return GatewayCommand(
                kind,
                [
                    "ip",
                    "-br",
                    "address",
                    "show",
                ],
                "Interfaces e endereços",
            )

        if kind == "arp":
            return GatewayCommand(
                kind,
                [
                    "ip",
                    "neigh",
                    "show",
                ],
                "Tabela ARP/ND",
            )

        if kind == "dns":
            host = GatewayCommandPolicy._host(
                params.get("host")
            )

            return GatewayCommand(
                kind,
                [
                    "getent",
                    "ahosts",
                    host,
                ],
                f"DNS {host}",
            )

        if kind == "iperf3":
            host = GatewayCommandPolicy._host(
                params.get("host")
            )
            duration = max(
                1,
                min(
                    int(
                        params.get("duration")
                        or 10
                    ),
                    60,
                ),
            )
            streams = max(
                1,
                min(
                    int(
                        params.get("streams")
                        or 4
                    ),
                    16,
                ),
            )

            argv = [
                "iperf3",
                "-J",
                "-c",
                host,
                "-t",
                str(duration),
                "-P",
                str(streams),
            ]

            if params.get(
                "reverse"
            ):
                argv.append(
                    "-R"
                )

            if params.get(
                "udp"
            ):
                argv.extend([
                    "-u",
                    "-b",
                    str(
                        params.get(
                            "bandwidth"
                        )
                        or "100M"
                    ),
                ])

            return GatewayCommand(
                kind,
                argv,
                f"iperf3 para {host}",
            )

        if kind == "capture":
            interface = GatewayCommandPolicy._interface(
                params.get("interface")
            )
            duration = max(
                1,
                min(
                    int(
                        params.get("duration")
                        or 10
                    ),
                    30,
                ),
            )
            count = max(
                1,
                min(
                    int(
                        params.get("count")
                        or 100
                    ),
                    500,
                ),
            )

            argv = [
                "timeout",
                str(duration),
                "tcpdump",
                "-i",
                interface,
                "-nn",
                "-c",
                str(count),
            ]

            host = params.get(
                "host"
            )

            if host:
                argv.extend([
                    "host",
                    GatewayCommandPolicy._host(
                        host
                    ),
                ])

            return GatewayCommand(
                kind,
                argv,
                f"Captura em {interface}",
            )

        if kind == "zerotier_status":
            return GatewayCommand(
                kind,
                [
                    "zerotier-cli",
                    "info",
                ],
                "Status do ZeroTier",
            )

        if kind == "wireguard_status":
            return GatewayCommand(
                kind,
                [
                    "wg",
                    "show",
                ],
                "Status do WireGuard",
            )

        raise ValueError(
            "Comando remoto não permitido."
        )

    @staticmethod
    def _host(
        value,
    ) -> str:
        host = str(
            value or ""
        ).strip()

        if not host:
            raise ValueError(
                "Informe o host de destino."
            )

        allowed = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            ".:-_"
        )

        if any(
            char not in allowed
            for char in host
        ):
            raise ValueError(
                "Host contém caracteres inválidos."
            )

        return host

    @staticmethod
    def _interface(
        value,
    ) -> str:
        interface = str(
            value or ""
        ).strip()

        if not interface:
            raise ValueError(
                "Informe a interface."
            )

        allowed = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            "._:-"
        )

        if any(
            char not in allowed
            for char in interface
        ):
            raise ValueError(
                "Interface inválida."
            )

        return interface


class SSHGatewayClient:
    def __init__(
        self,
        agent: dict[str, Any],
    ):
        self.agent = agent

    def run(
        self,
        command: GatewayCommand,
        *,
        timeout: int = 60,
    ) -> dict[str, Any]:
        try:
            import paramiko
        except ImportError as error:
            raise RuntimeError(
                "Paramiko não está instalado; reinstale as dependências do projeto."
            ) from error

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        connect_kwargs = {
            "hostname": self.agent[
                "host"
            ],
            "port": int(
                self.agent.get(
                    "ssh_port"
                )
                or 22
            ),
            "username": self.agent[
                "ssh_user"
            ],
            "timeout": 10,
            "allow_agent": True,
            "look_for_keys": True,
        }

        key_path = self.agent.get(
            "ssh_key_path"
        )

        if key_path:
            connect_kwargs[
                "key_filename"
            ] = str(
                Path(
                    key_path
                ).expanduser()
            )

        client.connect(
            **connect_kwargs
        )

        # Paramiko recebe uma string. Como argv já passou pela allow-list,
        # fazemos quoting estrito de cada token.
        import shlex

        command_text = " ".join(
            shlex.quote(
                item
            )
            for item in command.argv
        )

        started = time.perf_counter()

        stdin, stdout, stderr = (
            client.exec_command(
                command_text,
                timeout=timeout,
            )
        )

        exit_code = (
            stdout.channel.recv_exit_status()
        )

        output = (
            stdout.read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        error_text = (
            stderr.read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        elapsed = (
            time.perf_counter()
            - started
        )

        client.close()

        return {
            "success": exit_code == 0,
            "command": command.kind,
            "description": command.description,
            "exit_code": exit_code,
            "stdout": output[-50000:],
            "stderr": error_text[-20000:],
            "elapsed_seconds": round(
                elapsed,
                3,
            ),
        }


class RemoteAccessService:
    """
    Sessão temporária de gerenciamento.

    O gateway Linux é o ponto de acesso. A ONT não precisa expor HTTP/HTTPS
    publicamente: o desktop cria um SSH local-forward através do Agent.

    ZeroTier/WireGuard entram como transporte já configurado entre redes; a
    sessão valida o estado do overlay antes de abrir o túnel.
    """

    def __init__(
        self,
        repository: ManagementRepository = management_repository,
    ):
        self.repository = repository
        self._processes: dict[int, subprocess.Popen] = {}
        self._lock = Lock()

    def save_agent(
        self,
        data: dict[str, Any],
    ):
        return self.repository.save_agent(
            data
        )

    def agents(self):
        return self.repository.list_agents()

    def test_agent(
        self,
        agent_id: int,
    ) -> dict[str, Any]:
        agent = self._agent(
            agent_id
        )

        command = GatewayCommand(
            "health",
            [
                "printf",
                "agent-ready",
            ],
            "Health check",
        )

        result = SSHGatewayClient(
            agent
        ).run(
            command,
            timeout=15,
        )

        if result.get(
            "success"
        ):
            self.repository.touch_agent(
                agent_id
            )

        return result

    def run_gateway_command(
        self,
        agent_id: int,
        kind: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        agent = self._agent(
            agent_id
        )

        command = GatewayCommandPolicy.build(
            kind,
            params,
        )

        timeout = (
            90
            if kind in {
                "iperf3",
                "capture",
            }
            else 30
        )

        result = SSHGatewayClient(
            agent
        ).run(
            command,
            timeout=timeout,
        )

        self.repository.touch_agent(
            agent_id
        )

        if kind == "iperf3":
            result[
                "iperf"
            ] = self._parse_iperf(
                result.get(
                    "stdout"
                )
            )

        return result

    def open(
        self,
        *,
        device_id: int,
        attendant: str,
        ttl_minutes: int = 30,
        remote_port: int = 80,
    ) -> dict[str, Any]:
        device = self.repository.get_device(
            device_id
        )

        if device is None:
            raise ValueError(
                "Equipamento não encontrado."
            )

        agent_id = device.get(
            "agent_id"
        )

        if not agent_id:
            raise ValueError(
                "Associe um gateway/agent ao equipamento antes de abrir acesso remoto."
            )

        agent = self._agent(
            int(agent_id)
        )

        target_host = str(
            device.get("host")
            or ""
        ).split(
            ":",
            1,
        )[0]

        if not target_host:
            raise ValueError(
                "Equipamento sem host no inventário."
            )

        ttl_minutes = max(
            5,
            min(
                int(ttl_minutes),
                240,
            ),
        )

        expires = (
            _now()
            + timedelta(
                minutes=ttl_minutes
            )
        )

        session = self.repository.start_remote_session({
            "device_id": device_id,
            "agent_id": agent_id,
            "attendant": attendant,
            "driver": agent.get(
                "vpn_driver"
            ) or "ssh",
            "status": "opening",
            "target_host": target_host,
            "expires_at": expires.isoformat(),
            "details": {},
        })

        try:
            overlay = self._overlay_status(
                agent
            )

            local_port = _free_local_port()
            process = self._open_ssh_tunnel(
                agent,
                local_port=local_port,
                target_host=target_host,
                remote_port=int(
                    remote_port
                ),
            )

            time.sleep(
                0.35
            )

            if process.poll() is not None:
                raise RuntimeError(
                    "O processo SSH encerrou antes de abrir o túnel."
                )

            details = {
                "local_host": "127.0.0.1",
                "local_port": local_port,
                "target_host": target_host,
                "target_port": int(
                    remote_port
                ),
                "pid": process.pid,
                "overlay": overlay,
                "ttl_minutes": ttl_minutes,
            }

            with self._lock:
                self._processes[
                    session["id"]
                ] = process

            current = self.repository.update_remote_session(
                session["id"],
                status="active",
                details=details,
            )

            Thread(
                target=self._expire,
                args=(
                    session["id"],
                    ttl_minutes * 60,
                ),
                daemon=True,
                name=(
                    f"remote-session-{session['id']}"
                ),
            ).start()

            return {
                **current,
                "access_url": (
                    f"http://127.0.0.1:{local_port}"
                ),
            }

        except Exception as error:
            self.repository.update_remote_session(
                session["id"],
                status="failed",
                details={
                    "error": str(error),
                },
                closed=True,
            )

            raise

    def close(
        self,
        session_id: int,
        *,
        reason: str = "manual",
    ) -> dict[str, Any]:
        with self._lock:
            process = self._processes.pop(
                session_id,
                None,
            )

        if process is not None:
            try:
                process.terminate()
                process.wait(
                    timeout=3
                )
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        result = self.repository.update_remote_session(
            session_id,
            status="closed",
            details={
                "reason": reason,
            },
            closed=True,
        )

        if result is None:
            raise ValueError(
                "Sessão remota não encontrada."
            )

        return result

    def sessions(self):
        return self.repository.list_remote_sessions()

    def _overlay_status(
        self,
        agent: dict[str, Any],
    ) -> dict[str, Any]:
        driver = str(
            agent.get(
                "vpn_driver"
            )
            or "none"
        ).lower()

        if driver == "zerotier":
            try:
                return self.run_gateway_command(
                    agent["id"],
                    "zerotier_status",
                    {},
                )
            except Exception as error:
                return {
                    "success": False,
                    "driver": driver,
                    "error": str(error),
                }

        if driver == "wireguard":
            try:
                return self.run_gateway_command(
                    agent["id"],
                    "wireguard_status",
                    {},
                )
            except Exception as error:
                return {
                    "success": False,
                    "driver": driver,
                    "error": str(error),
                }

        return {
            "success": True,
            "driver": driver,
            "message": "Sem overlay VPN obrigatório; usando o alcance do gateway.",
        }

    @staticmethod
    def _open_ssh_tunnel(
        agent,
        *,
        local_port,
        target_host,
        remote_port,
    ):
        ssh = shutil.which(
            "ssh"
        )

        if not ssh:
            raise RuntimeError(
                "OpenSSH client não encontrado no computador do atendente."
            )

        argv = [
            ssh,
            "-N",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=2",
            "-p",
            str(
                agent.get(
                    "ssh_port"
                )
                or 22
            ),
            "-L",
            (
                f"127.0.0.1:{local_port}:"
                f"{target_host}:{remote_port}"
            ),
        ]

        key_path = agent.get(
            "ssh_key_path"
        )

        if key_path:
            argv.extend([
                "-i",
                str(
                    Path(
                        key_path
                    ).expanduser()
                ),
            ])

        argv.append(
            (
                f"{agent['ssh_user']}@"
                f"{agent['host']}"
            )
        )

        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        if os.name == "nt":
            kwargs[
                "creationflags"
            ] = (
                subprocess.CREATE_NO_WINDOW
            )

        return subprocess.Popen(
            argv,
            **kwargs,
        )

    def _expire(
        self,
        session_id: int,
        seconds: int,
    ):
        time.sleep(
            seconds
        )

        with self._lock:
            active = (
                session_id
                in self._processes
            )

        if active:
            self.close(
                session_id,
                reason="ttl_expired",
            )

    def _agent(
        self,
        agent_id: int,
    ):
        agent = self.repository.get_agent(
            agent_id
        )

        if agent is None:
            raise ValueError(
                "Gateway/agent não encontrado."
            )

        if not agent.get(
            "enabled"
        ):
            raise RuntimeError(
                "Gateway/agent está desativado."
            )

        return agent

    @staticmethod
    def _parse_iperf(
        stdout: str | None,
    ) -> dict[str, Any] | None:
        if not stdout:
            return None

        try:
            data = json.loads(
                stdout
            )
        except ValueError:
            return None

        end = data.get(
            "end"
        ) or {}

        received = (
            end.get(
                "sum_received"
            )
            or end.get(
                "sum"
            )
            or {}
        )

        sent = (
            end.get(
                "sum_sent"
            )
            or {}
        )

        return {
            "download_mbps": (
                float(
                    received.get(
                        "bits_per_second"
                    )
                    or 0
                )
                / 1_000_000
            ),
            "upload_mbps": (
                float(
                    sent.get(
                        "bits_per_second"
                    )
                    or 0
                )
                / 1_000_000
            ),
            "retransmits": sent.get(
                "retransmits"
            ),
            "seconds": received.get(
                "seconds"
            ),
            "cpu": data.get(
                "end",
                {}
            ).get(
                "cpu_utilization_percent"
            ),
        }


remote_access_service = RemoteAccessService()
