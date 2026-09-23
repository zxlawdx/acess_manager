import json
from copy import deepcopy
from pathlib import Path
from threading import RLock


class ProfileRepository:
    """
    Repository Pattern.

    A camada de serviço não precisa saber se os perfis estão em JSON, banco ou
    API externa. Por enquanto o JSON local é suficiente e facilita levar o app
    para os computadores do suporte.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = RLock()

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.path.exists():
            self._write({})

    # =========================================================
    # IO
    # =========================================================

    def _read(self):
        with self._lock:
            try:
                with self.path.open(
                    "r",
                    encoding="utf-8"
                ) as arquivo:
                    dados = json.load(
                        arquivo
                    )

                if isinstance(dados, dict):
                    return dados

            except (
                json.JSONDecodeError,
                OSError
            ):
                pass

            return {}

    def _write(self, dados):
        with self._lock:
            with self.path.open(
                "w",
                encoding="utf-8"
            ) as arquivo:
                json.dump(
                    dados,
                    arquivo,
                    ensure_ascii=False,
                    indent=4
                )

    # =========================================================
    # CRUD
    # =========================================================

    def list(self):
        return sorted(
            self._read().keys()
        )

    def get(self, attendant: str):
        dados = self._read()

        perfil = dados.get(
            attendant
        )

        if perfil is None:
            return None

        return deepcopy(
            perfil
        )

    def save(
        self,
        attendant: str,
        profile: dict
    ):
        attendant = attendant.strip()

        if not attendant:
            raise ValueError(
                "Informe o nome do atendente."
            )

        dados = self._read()

        dados[attendant] = deepcopy(
            profile
        )

        self._write(
            dados
        )

        return deepcopy(
            dados[attendant]
        )

    def delete(self, attendant: str):
        dados = self._read()

        if attendant not in dados:
            return False

        del dados[attendant]

        self._write(
            dados
        )

        return True
