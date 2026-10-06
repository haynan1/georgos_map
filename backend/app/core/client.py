"""What the API knows about the caller's device, for sessions and audit records."""

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, ip_address

from starlette.requests import Request

_USER_AGENT_MAX = 512


@dataclass(frozen=True, slots=True)
class ClientInfo:
    ip: IPv4Address | IPv6Address | None
    user_agent: str | None

    @property
    def ip_key(self) -> str:
        return str(self.ip) if self.ip is not None else "unknown"


def client_info(request: Request) -> ClientInfo:
    # ``request.client`` already reflects X-Forwarded-For when (and only when) uvicorn is
    # told to trust the proxy via FORWARDED_ALLOW_IPS, so clients cannot spoof it.
    host = request.client.host if request.client else None
    try:
        ip = ip_address(host) if host else None
    except ValueError:
        ip = None
    user_agent = request.headers.get("user-agent")
    return ClientInfo(ip=ip, user_agent=user_agent[:_USER_AGENT_MAX] if user_agent else None)
