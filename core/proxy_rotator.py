import time
import random
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class ProxyNode:
    server: str
    username: Optional[str] = None
    password: Optional[str] = None
    failure_count: int = 0
    cooldown_until: float = 0.0
    last_used: float = 0.0

    @property
    def is_available(self) -> bool:
        return time.time() >= self.cooldown_until

    def to_playwright_dict(self) -> Dict[str, str]:
        cfg = {"server": self.server}
        if self.username:
            cfg["username"] = self.username
        if self.password:
            cfg["password"] = self.password
        return cfg

class ProxyRotator:
    """
    Manages proxy pools with health scoring, cooldowns, and sticky account binding.
    """
    def __init__(self, proxy_list: List[Dict[str, str]], failure_threshold: int = 3, cooldown_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.pool: List[ProxyNode] = [
            ProxyNode(
                server=p["server"],
                username=p.get("username"),
                password=p.get("password")
            )
            for p in proxy_list
        ]
        self.account_bindings: Dict[str, ProxyNode] = {}

    def get_proxy_for_account(self, account_id: str) -> Optional[Dict[str, str]]:
        """
        Retrieves a sticky proxy for a given account. If the assigned proxy is
        on cooldown or not yet assigned, binds the healthiest available node.
        """
        if not self.pool:
            return None

        # 1. Check existing binding
        if account_id in self.account_bindings:
            bound = self.account_bindings[account_id]
            if bound.is_available:
                bound.last_used = time.time()
                return bound.to_playwright_dict()

        # 2. Select least-recently-used available proxy
        available_nodes = [p for p in self.pool if p.is_available]
        if not available_nodes:
            return None

        selected = sorted(available_nodes, key=lambda x: (x.failure_count, x.last_used))[0]
        selected.last_used = time.time()
        self.account_bindings[account_id] = selected
        return selected.to_playwright_dict()

    def record_failure(self, server_url: str):
        """Flags connection or navigation failure for a proxy node."""
        for node in self.pool:
            if node.server == server_url:
                node.failure_count += 1
                if node.failure_count >= self.failure_threshold:
                    node.cooldown_until = time.time() + self.cooldown_seconds
                    print(f"[ProxyRotator] Node {server_url} exceeded failure limit. Cooldown for {self.cooldown_seconds}s.")
                break

    def record_success(self, server_url: str):
        """Resets error counters on successful workflow step."""
        for node in self.pool:
            if node.server == server_url:
                node.failure_count = max(0, node.failure_count - 1)
                break
