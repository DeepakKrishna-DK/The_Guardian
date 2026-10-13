#!/usr/bin/env python3
"""
Guardian WireGuard & Hub Network Configuration
===============================================
Agnostic Network Setup & Diagnostic Utility for Guardian Hub Gateway.

Architecture & Zero Vendor Lock-In Principle:
---------------------------------------------
Guardian's remote gateway binds directly to an IP on a network interface.
It NEVER imports or calls any Tailscale, Headscale, or third-party proprietary SDK.

Network Transport Options (Zero Code Difference):
1. Tailscale (Recommended convenience today):
   - Fast setup, automated NAT traversal and key exchange.
   - Creates a virtual WireGuard adapter with an IP in 100.64.0.0/10 (CGNAT).
   - Guardian detects this interface and binds directly to its IP.

2. Headscale (Self-hosted open-source control plane):
   - 100% open-source, self-hosted implementation of the coordination server.
   - Same WireGuard protocol and clients; completely independent of Tailscale Inc.
   - Swapping Tailscale for Headscale requires changing the client login server URL only;
     ZERO code change in Guardian.

3. Raw / Native WireGuard (Manual wg-quick / kernel WireGuard):
   - Linux kernel WireGuard interface (`wg0`).
   - Private subnet (e.g. 10.0.0.1/24).
   - Point-to-point cryptographic keys.
   - Guardian binds directly to the assigned interface IP; ZERO code change.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from guardian.gateway.network import find_wireguard_interfaces, get_bind_address


def main():
    print("=" * 70)
    print("  GUARDIAN HUB — WIREGUARD NETWORK DIAGNOSTIC & CONFIGURATION")
    print("=" * 70)
    print()

    print("[*] Inspecting network interfaces for WireGuard / VPN adapters...")
    interfaces = find_wireguard_interfaces()

    if interfaces:
        print(f"\n[+] Found {len(interfaces)} active WireGuard/VPN interface(s):")
        for idx, iface in enumerate(interfaces, 1):
            print(f"    {idx}. Name: {iface['name']}")
            print(f"       IP Address: {iface['ip']}")
            print(f"       Detected Via: {iface['detected_via']}")
        default_ip = interfaces[0]["ip"]
    else:
        print("\n[-] No active WireGuard or CGNAT interface detected on this machine.")
        print("    The gateway will safely bind to localhost (127.0.0.1) for local testing.")
        default_ip = "127.0.0.1"

    print("\n" + "-" * 70)
    print("  CONFIGURATION GUIDELINES FOR REMOTE CLIENT ACCESS (PWA / MOBILE)")
    print("-" * 70)
    print("""
Option A: Tailscale (Fastest Setup)
  1. Install Tailscale on the Hub machine: https://tailscale.com/download
  2. Run: tailscale up
  3. Note your Hub's Tailscale IP (e.g., 100.x.y.z)
  4. Launch Gateway:
       python -m guardian gateway start --bind-ip 100.x.y.z
     Or set environment variable:
       GUARDIAN_GATEWAY_HOST=100.x.y.z

Option B: Headscale (Self-Hosted Open Source Control Server)
  1. Run Headscale on your server / VPS: https://github.com/juanfont/headscale
  2. Point client to your Headscale server: tailscale up --login-server https://your-headscale.example.com
  3. Launch Gateway using the assigned interface IP (same as above).
  4. Cost: $0, 100% self-hosted, ZERO code change in Guardian.

Option C: Native WireGuard (Kernel wg0)
  1. Configure /etc/wireguard/wg0.conf on Hub (e.g. Address = 10.100.0.1/24)
  2. Start interface: wg-quick up wg0
  3. Launch Gateway:
       python -m guardian gateway start --bind-ip 10.100.0.1

Safety Rule:
  Guardian strictly prohibits binding to 0.0.0.0 to prevent unintended exposure
  to public networks or LAN. All traffic must arrive over an authenticated VPN.
""")
    print("=" * 70)


if __name__ == "__main__":
    main()
