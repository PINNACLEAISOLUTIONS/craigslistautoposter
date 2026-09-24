import json
from pathlib import Path
from typing import Optional
from playwright.async_api import BrowserContext

class SessionManager:
    """
    Manages Playwright session storage state (cookies, local storage)
    to reuse authenticated sessions without frequent logins.
    """
    def __init__(self, sessions_dir: str | Path):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def get_session_path(self, account_id: str) -> Path:
        safe_id = "".join(c for c in account_id if c.isalnum() or c in ("-", "_"))
        return self.sessions_dir / f"{safe_id}_state.json"

    def has_session(self, account_id: str) -> bool:
        session_file = self.get_session_path(account_id)
        return session_file.exists() and session_file.stat().st_size > 0

    async def save_session(self, context: BrowserContext, account_id: str):
        session_path = self.get_session_path(account_id)
        await context.storage_state(path=str(session_path))
        print(f"[Session] Saved authenticated state to {session_path}")

    def get_storage_state_arg(self, account_id: str) -> Optional[str]:
        if self.has_session(account_id):
            return str(self.get_session_path(account_id))
        return None
