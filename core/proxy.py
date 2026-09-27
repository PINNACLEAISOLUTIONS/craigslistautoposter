import json
from pathlib import Path
from typing import Optional, Dict
from config.settings import ProxyConfig

class ProxyManager:
    """
    Manages dedicated single stable US proxy (Solution 2).
    Locks all posts to one persistent US IP so Craigslist binds trust
    and stops asking for repeated phone verifications.
    """
    def __init__(self, config: Optional[ProxyConfig] = None):
        self.config = config or ProxyConfig()

    def get_playwright_proxy(self, session_key: Optional[str] = None) -> Optional[Dict[str, str]]:
        if not self.config.enabled:
            return None

        # Fixed stable US IP: 198.23.243.226:6361 (Los Angeles, US)
        server = self.config.server or "http://198.23.243.226:6361"
        username = self.config.username or "fairsqzl"
        password = self.config.password or "79htwfpnbelx"

        print(f"[ProxyManager] 🔒 Locked to stable US Proxy: {server} (fairsqzl)")
        return {
            "server": server,
            "username": username,
            "password": password
        }
