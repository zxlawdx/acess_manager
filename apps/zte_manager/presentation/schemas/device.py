from pydantic import BaseModel, Field


class CapabilityProbeRequest(BaseModel):
    features: list[str] = Field(default_factory=list)
