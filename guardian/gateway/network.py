"""
Guardian Gateway Network Interface Utilities
============================================
Vendor-agnostic interface discovery and binding security.

Zero Vendor Lock-In Design:
- Guardian only relies on standard OS networking (sockets and psutil).
- It NEVER imports or calls any Tailscale, Headscale, or proprietary SDK.
- Any WireGuard-based interface (Tailscale, Headscale, or native Linux wg0)
  presents as a standard network interface.

Safety Constraints:
- Binding to 0.0.0.0 is strictly prohibited unless GUARDIAN_ALLOW_INSECURE_BIND=1
  is explicitly configured for isolated testing environments.
- By default, binds to the designated WireGuard interface IP or 127.0.0.1.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Dict, List, Optional
import psutil

from guardian.logging.logger import get_logger

log = get_logger(__name__)

# Standard WireGuard / VPN interface name prefixes across OSes
WG_INTERFACE_PREFIXES = (
    "wg",          # Linux native WireGuard
    "wireguard",   # Custom named WireGuard interfaces
    "tailscale",   # Tailscale WireGuard virtual adapter
    "utun",        # macOS WireGuard / TUN interface
    "tun",         # Generic TUN interface
)

# Common VPN / Overlay subnet ranges (e.g. CGNAT 100.64.0.0/10 used by Tailscale/Headscale)
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def find_wireguard_interfaces() -> List[Dict[str, str]]:
    """
    Discovers active WireGuard / VPN network interfaces on the local system.
    Returns a list of dicts with 'name', 'ip', and 'type'.
    Uses standard OS network enumeration via psutil — zero vendor API dependencies.
    """
    results: List[Dict[str, str]] = []
    try:
        addrs = psutil.net_if_addrs()
    except Exception as e:
        log.warning(f"Failed to enumerate network interfaces: {e}")
        return results

    for iface_name, addr_list in addrs.items():
        name_lower = iface_name.lower()
        is_wg_name = any(name_lower.startswith(prefix) for prefix in WG_INTERFACE_PREFIXES)

        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ip_str = addr.address
                try:
                    ip_obj = ipaddress.ip_address(ip_str)
                except ValueError:
                    continue

                if ip_obj.is_loopback:
                    continue

                is_cgnat = ip_obj in CGNAT_NETWORK
                if is_wg_name or is_cgnat:
                    results.append({
                        "name": iface_name,
                        "ip": ip_str,
                        "detected_via": "name" if is_wg_name else "cgnat_range",
                    })

    return results


def get_bind_address(preferred_ip: Optional[str] = None, allow_insecure: bool = False) -> str:
    """
    Determines and validates the exact IP address to bind the Gateway server to.
    
    Order of precedence:
    1. Explicit preferred_ip argument.
    2. Environment variable GUARDIAN_GATEWAY_HOST or GUARDIAN_BIND_IP.
    3. Auto-detected WireGuard / Overlay interface IP.
    4. Fallback: 127.0.0.1 (safe local loopback).

    Safety Rules:
    - Binding to 0.0.0.0 is explicitly prohibited unless allow_insecure is True
      or GUARDIAN_ALLOW_INSECURE_BIND="1".
    """
    env_insecure = os.getenv("GUARDIAN_ALLOW_INSECURE_BIND", "0").lower() in ("1", "true", "yes")
    effective_allow_insecure = allow_insecure or env_insecure

    # Check candidates
    candidate = preferred_ip or os.getenv("GUARDIAN_GATEWAY_HOST") or os.getenv("GUARDIAN_BIND_IP")

    if candidate:
        candidate = candidate.strip()
        if candidate == "0.0.0.0" and not effective_allow_insecure:
            raise ValueError(
                "CRITICAL SECURITY GATE: Binding to 0.0.0.0 is prohibited by Guardian safety policy. "
                "The remote gateway must bind strictly to a WireGuard/VPN interface IP or 127.0.0.1. "
                "To override in isolated container testing, set GUARDIAN_ALLOW_INSECURE_BIND=1."
            )
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError as err:
            raise ValueError(f"Invalid IP address specified for Gateway bind: '{candidate}'") from err

    # Auto-detect WireGuard / VPN interfaces
    wg_ifaces = find_wireguard_interfaces()
    if wg_ifaces:
        chosen = wg_ifaces[0]["ip"]
        log.info(f"Auto-detected WireGuard interface '{wg_ifaces[0]['name']}' with IP: {chosen}")
        return chosen

    # Default to safe localhost
    log.info("No WireGuard interface detected; defaulting Gateway bind to localhost (127.0.0.1)")
    return "127.0.0.1"
