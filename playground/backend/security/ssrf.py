"""
SSRF (Server-Side Request Forgery) protection.

Blocks requests to private IPs, loopback addresses, link-local ranges,
and cloud metadata endpoints to prevent the LLM from accessing internal
services or leaking cloud credentials.
"""

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Tuple


BLOCKED_HOSTS = frozenset({
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
})

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local + cloud metadata (169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),          # IPv6 private
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]


def is_ssrf_target(url: str) -> Tuple[bool, str]:
    """
    Check if a URL targets a private/internal address.

    Returns:
        (is_blocked, reason) — True if the URL should be blocked.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return True, "Invalid URL"

    hostname = parsed.hostname
    if not hostname:
        return True, "No hostname in URL"

    # Block known metadata hostnames
    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTS:
        return True, f"Blocked host: {hostname}"

    # Resolve hostname to IP and check against private ranges
    try:
        resolved_ip = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved_ip)
        for network in PRIVATE_NETWORKS:
            if ip in network:
                return True, f"Private/internal IP: {resolved_ip}"
    except socket.gaierror:
        # DNS resolution failed — allow it to fail naturally during fetch
        return False, ""
    except ValueError:
        return True, f"Invalid IP address: {hostname}"

    return False, ""
