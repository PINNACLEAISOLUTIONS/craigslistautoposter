import os
from pathlib import Path
from pydantic import BaseModel, Field
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent

class RateLimitConfig(BaseModel):
    min_post_interval_seconds: int = 180
    max_post_interval_seconds: int = 420
    max_posts_per_day: int = 10
    jitter_factor: float = 0.25

class BrowserConfig(BaseModel):
    headless: bool = False
    slow_mo_ms: int = 65
    timeout_ms: int = 30000
    human_typing_min_delay_ms: int = 45
    human_typing_max_delay_ms: int = 140
    enable_cursor_jitter: bool = True
    user_agent: str | None = None
    viewport_width: int = 1280
    viewport_height: int = 800

class ProxyConfig(BaseModel):
    enabled: bool = False
    server: str = ""
    username: str = ""
    password: str = ""
    sticky_session: bool = True

class AppConfig(BaseModel):
    sessions_dir: Path = BASE_DIR / "data" / "sessions"
    templates_dir: Path = BASE_DIR / "data" / "templates"
    images_dir: Path = BASE_DIR / "data" / "images"
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)

def load_config(config_path: Path | str | None = None) -> AppConfig:
    if config_path is None:
        config_path = BASE_DIR / "config" / "default_config.yaml"
    
    path = Path(config_path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return AppConfig(**data)
    
    return AppConfig()
