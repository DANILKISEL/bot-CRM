import requests
from requests.exceptions import RequestException
import socket


def get_ip():
    """
    Get external IP address with multiple fallback services
    Returns the IP as string or None if all services fail
    """
    services = [
        'https://api.ipify.org',
        'https://ident.me',
        'https://checkip.amazonaws.com',
        'https://ipinfo.io/ip',
        'https://ifconfig.me/ip'
    ]

    for service in services:
        try:
            response = requests.get(service, timeout=5)
            if response.status_code == 200:
                ip = response.text.strip()
                # Basic IP validation
                if ip and ('.' in ip or ':' in ip):  # Support for IPv4 and IPv6
                    return ip
        except RequestException:
            continue

    return None


def get_local_ip():
    """Get local IP address"""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"