from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass, field
from typing import Protocol


WAP_PROMPT = re.compile(rb"(?:SU_)?WAP>\s*$", re.M)


@dataclass(frozen=True)
class HuaweiCliOptions:
    """Operator-supplied CLI configuration.

    CLI is disabled by default. Access Manager never enables SSH/Telnet on the
    device and never derives credentials from model/default-password tables.
    """

    enabled: bool = False
    transport: str = "auto"
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    port: int | None = None
    timeout: float = 3.0

    @classmethod
    def from_mapping(cls, value: object) -> "HuaweiCliOptions":
        if isinstance(value, cls):
            return value
        data = dict(value or {}) if isinstance(value, dict) else {}
        transport = str(data.get("transport") or "auto").strip().casefold()
        if transport not in {"auto", "ssh", "telnet"}:
            raise ValueError("Huawei CLI transport deve ser auto, ssh ou telnet.")
        timeout = float(data.get("timeout") or 3.0)
        if timeout <= 0 or timeout > 30:
            raise ValueError("Huawei CLI timeout deve estar entre 0 e 30 segundos.")
        port = data.get("port")
        if port is not None:
            port = int(port)
            if port < 1 or port > 65535:
                raise ValueError("Huawei CLI port inválida.")
        return cls(
            enabled=bool(data.get("enabled", False)),
            transport=transport,
            username=(str(data.get("username") or "").strip() or None),
            password=(str(data.get("password") or "") or None),
            port=port,
            timeout=timeout,
        )

    def public(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "transport": self.transport,
            "port": self.port,
            "timeout": self.timeout,
            "credentials_supplied": bool(self.username and self.password),
        }


class HuaweiCliTransport(Protocol):
    name: str

    def run(self, command: str) -> str: ...

    def close(self) -> None: ...


class HuaweiCliUnavailable(RuntimeError):
    pass


def probe_tcp_port(host: str, port: int, *, timeout: float = 1.5) -> bool:
    """Non-destructive transport probe; it never authenticates or configures."""

    try:
        with socket.create_connection((host, int(port)), timeout=float(timeout)):
            return True
    except OSError:
        return False


def _validate_read_command(command: str) -> str:
    normalized = " ".join(str(command or "").strip().split())
    allowed = (
        "display ",
        "ping ",
        "traceroute ",
    )
    if not normalized or not normalized.casefold().startswith(allowed):
        raise ValueError("Huawei CLI aceita somente comandos read-only permitidos.")
    forbidden = (
        "clear ",
        "set ",
        "save ",
        "reboot",
        "reset",
        "restore",
        "delete ",
        "add ",
        "config ",
    )
    if any(token in normalized.casefold() for token in forbidden):
        raise ValueError("Comando Huawei CLI potencialmente mutável foi bloqueado.")
    return normalized


class HuaweiTelnetCliTransport:
    name = "telnet"

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 23,
        timeout: float = 3.0,
    ) -> None:
        try:
            import telnetlib
        except ImportError as exc:  # pragma: no cover - Python >3.12 packaging
            raise HuaweiCliUnavailable(
                "Telnet não está disponível neste runtime Python."
            ) from exc

        self._telnetlib = telnetlib
        self._timeout = float(timeout)
        self._session = telnetlib.Telnet(host, int(port), self._timeout)
        if b"Login:" not in self._session.read_until(b"Login:", self._timeout):
            self.close()
            raise HuaweiCliUnavailable("Prompt Login: Huawei WAP não encontrado.")
        self._session.write(username.encode("utf-8") + b"\n")
        if b"Password:" not in self._session.read_until(b"Password:", self._timeout):
            self.close()
            raise HuaweiCliUnavailable("Prompt Password: Huawei WAP não encontrado.")
        self._session.write(password.encode("utf-8") + b"\n")
        index, _match, _data = self._session.expect([WAP_PROMPT], self._timeout)
        if index < 0:
            self.close()
            raise HuaweiCliUnavailable("Prompt WAP Huawei não confirmado após login.")

    def run(self, command: str) -> str:
        safe = _validate_read_command(command)
        self._session.write(safe.encode("ascii", errors="strict") + b"\n")
        index, _match, data = self._session.expect([WAP_PROMPT], self._timeout)
        if index < 0:
            raise HuaweiCliUnavailable("Timeout aguardando resposta do Huawei WAP.")
        return data.decode("utf-8", errors="replace")

    def close(self) -> None:
        session = getattr(self, "_session", None)
        if session is None:
            return
        try:
            session.write(b"quit\n")
        except Exception:
            pass
        try:
            session.close()
        except Exception:
            pass
        self._session = None


class HuaweiSshCliTransport:
    name = "ssh"

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 22,
        timeout: float = 3.0,
    ) -> None:
        try:
            import paramiko
        except ImportError as exc:  # pragma: no cover - dependency contract
            raise HuaweiCliUnavailable("Paramiko não está instalado.") from exc

        self._timeout = float(timeout)
        self._client = paramiko.SSHClient()
        # Do not persist unknown host keys. WarningPolicy accepts the device for
        # this ephemeral local session while making the trust limitation clear.
        self._client.set_missing_host_key_policy(paramiko.WarningPolicy())
        self._client.connect(
            hostname=host,
            port=int(port),
            username=username,
            password=password,
            timeout=self._timeout,
            auth_timeout=self._timeout,
            banner_timeout=self._timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        self._channel = self._client.invoke_shell()
        if not self._read_until_prompt():
            self.close()
            raise HuaweiCliUnavailable("Prompt WAP Huawei não confirmado via SSH.")

    def _read_until_prompt(self) -> str:
        deadline = time.monotonic() + self._timeout
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            if self._channel.recv_ready():
                chunks.append(self._channel.recv(65535))
                raw = b"".join(chunks)
                if WAP_PROMPT.search(raw):
                    return raw.decode("utf-8", errors="replace")
            else:
                time.sleep(0.03)
        return ""

    def run(self, command: str) -> str:
        safe = _validate_read_command(command)
        self._channel.send(safe + "\n")
        result = self._read_until_prompt()
        if not result:
            raise HuaweiCliUnavailable("Timeout aguardando resposta do Huawei WAP via SSH.")
        return result

    def close(self) -> None:
        channel = getattr(self, "_channel", None)
        if channel is not None:
            try:
                channel.send("quit\n")
            except Exception:
                pass
            try:
                channel.close()
            except Exception:
                pass
            self._channel = None
        client = getattr(self, "_client", None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
            self._client = None


def create_huawei_cli_transport(
    host: str,
    options: HuaweiCliOptions,
) -> HuaweiCliTransport:
    """Create exactly one explicitly enabled CLI transport.

    For ``auto`` the port probe is credential-free and chooses SSH before
    Telnet. Credentials are never tried against multiple transports blindly.
    """

    if not options.enabled:
        raise HuaweiCliUnavailable("Huawei CLI não foi habilitado pelo operador.")
    if not options.username or not options.password:
        raise HuaweiCliUnavailable(
            "Huawei CLI requer credenciais fornecidas explicitamente pelo operador."
        )

    selected = options.transport
    port = options.port
    if selected == "auto":
        if probe_tcp_port(host, port or 22, timeout=min(options.timeout, 1.5)):
            selected = "ssh"
            port = port or 22
        elif probe_tcp_port(host, port or 23, timeout=min(options.timeout, 1.5)):
            selected = "telnet"
            port = port or 23
        else:
            raise HuaweiCliUnavailable(
                "Nenhuma porta CLI Huawei já habilitada respondeu ao probe."
            )

    if selected == "ssh":
        port = port or 22
        if not probe_tcp_port(host, port, timeout=min(options.timeout, 1.5)):
            raise HuaweiCliUnavailable("SSH Huawei não está acessível.")
        return HuaweiSshCliTransport(
            host,
            options.username,
            options.password,
            port=port,
            timeout=options.timeout,
        )
    if selected == "telnet":
        port = port or 23
        if not probe_tcp_port(host, port, timeout=min(options.timeout, 1.5)):
            raise HuaweiCliUnavailable("Telnet Huawei não está acessível.")
        return HuaweiTelnetCliTransport(
            host,
            options.username,
            options.password,
            port=port,
            timeout=options.timeout,
        )
    raise HuaweiCliUnavailable("Transport Huawei CLI não reconhecido.")
