"""
Guardian Hub Gateway
====================
Exposes an auth-gated, WireGuard-compatible remote API for client devices (PWA/mobile).
Features:
- Zero vendor lock-in (agnostic network interface binding; no Tailscale SDK calls)
- Cryptographically audited one-time device pairing flow
- Identical choke point (Guardrails -> SecurityGateway -> PolicyEngine -> ToolExecutor)
- Full-duplex WebSocket event/voice streaming & REST endpoints
"""

from .network import get_bind_address, find_wireguard_interfaces
from .pairing import DeviceRegistry, get_device_registry
from .server import create_gateway_app, run_gateway

__all__ = [
    "get_bind_address",
    "find_wireguard_interfaces",
    "DeviceRegistry",
    "get_device_registry",
    "create_gateway_app",
    "run_gateway",
]
