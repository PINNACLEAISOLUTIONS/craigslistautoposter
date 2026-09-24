from typing import Optional, Dict
from config.settings import ProxyConfig

class ProxyManager:
    """
    Manages residential/mobile proxy settings with sticky sessions per account.
    """
    def __init__(self, config: Optional[ProxyConfig] = None):
        self.config = config or ProxyConfig()

    def get_playwright_proxy(self, session_key: Optional[str] = None) -> Optional[Dict[str, str]]:
        if not self.config.enabled or not self.config.server:
            return None

        username = self.config.username
        if self.config.sticky_session and session_key and username:
            # Many residential proxy providers (Oxylabs, Bright Data, Smartproxy)
            # allow session-id appending to username: e.g. user-session-xxxx
            if "-session-" not in username:
                username = f"{username}-session-{session_key}"

        proxy_dict = {"server": self.config.server}
        if username:
            proxy_dict["username"] = username
        if self.config.password:
            proxy_dict["password"] = self.config.password

        return proxy_dict
