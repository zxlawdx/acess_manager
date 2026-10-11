from __future__ import annotations

from apps.zte_manager.infrastructure.huawei.affinity_client import (
    HuaweiAffinityNegotiatingWebClient,
)
from apps.zte_manager.services.huawei_unified_provider import HuaweiUnifiedProvider


class HuaweiAffinityUnifiedProvider(HuaweiUnifiedProvider):
    """Production composition that adds Phase-4 transport affinity support.

    The provider does not enable affinity by model name. It merely supplies the
    affinity-aware negotiating client; that client stays on the ordinary
    requests.Session path unless an EndpointProfile, TransportPolicy, or strict
    pre-auth fingerprint requires same-TCP challenge/login.
    """

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("client_factory", HuaweiAffinityNegotiatingWebClient)
        super().__init__(**kwargs)
