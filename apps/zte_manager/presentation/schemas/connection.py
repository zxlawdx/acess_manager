from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    ip: str
    model_hint: str | None = None
    username: str
    password: str
    https: bool = False
    attendant: str | None = None


class AdminPasswordRequest(BaseModel):
    new_password: str = Field(
        min_length=1,
        max_length=256,
    )
