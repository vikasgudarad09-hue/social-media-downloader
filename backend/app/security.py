import ipaddress
import socket
from urllib.parse import urlparse

# Set of forbidden hostnames (local, loopback, cloud instance metadata services)
FORBIDDEN_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "169.254.169.254",
    "0.0.0.0",
    "::1",
    "ip6-localhost",
    "ip6-loopback",
}


def is_safe_proxy_url(url: str) -> bool:
    """
    Validates whether a URL is safe to fetch from server-side proxying.
    Prevents Server-Side Request Forgery (SSRF) by verifying:
    - HTTP or HTTPS protocol only.
    - Non-empty valid hostname.
    - Not matching loopback, link-local, multicast, cloud metadata, or private IP ranges.
    - Protection against DNS rebinding by inspecting all resolved IP addresses.
    """
    if not url or not isinstance(url, str):
        return False

    url_clean = url.strip()
    try:
        parsed = urlparse(url_clean)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname_lower = hostname.lower()

        # Block local names, mDNS, internal suffixes, and cloud metadata
        if (
            hostname_lower in FORBIDDEN_HOSTS
            or hostname_lower.endswith(".local")
            or hostname_lower.endswith(".internal")
            or hostname_lower.endswith(".localhost")
        ):
            return False

        # If hostname is directly an IP address literal
        try:
            ip_obj = ipaddress.ip_address(hostname_lower)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_reserved
                or ip_obj.is_multicast
                or ip_obj.is_unspecified
            ):
                return False
            return True
        except ValueError:
            # Not an IP literal, will resolve via DNS below
            pass

        # Resolve hostname to all associated IPs to prevent DNS rebinding attacks
        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except (socket.gaierror, socket.herror, OSError):
            return False

        if not addr_info:
            return False

        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_reserved
                    or ip_obj.is_multicast
                    or ip_obj.is_unspecified
                ):
                    return False
            except ValueError:
                return False

        return True
    except Exception:
        return False
