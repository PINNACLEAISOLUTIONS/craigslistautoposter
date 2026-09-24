import asyncio
import random
import time
from typing import Optional
from config.settings import RateLimitConfig

class RateLimiter:
    """
    Controls posting velocity, inter-post cooldowns, and jittered delays
    to mimic human behavior and avoid trigger-based rate limiting.
    """
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.last_post_timestamp: float = 0.0
        self.daily_post_count: int = 0
        self.day_start_timestamp: float = time.time()

    def _reset_daily_if_needed(self):
        current = time.time()
        if current - self.day_start_timestamp >= 86400:
            self.daily_post_count = 0
            self.day_start_timestamp = current

    def can_post(self) -> tuple[bool, str]:
        self._reset_daily_if_needed()
        if self.daily_post_count >= self.config.max_posts_per_day:
            return False, f"Daily limit reached ({self.config.max_posts_per_day} posts/day)."
        return True, "Ready"

    async def wait_cooldown(self):
        """Waits if required interval has not passed since last post."""
        if self.last_post_timestamp == 0.0:
            return

        elapsed = time.time() - self.last_post_timestamp
        base_interval = random.uniform(
            self.config.min_post_interval_seconds,
            self.config.max_post_interval_seconds
        )
        # Add jitter
        jitter = base_interval * random.uniform(-self.config.jitter_factor, self.config.jitter_factor)
        target_interval = max(30.0, base_interval + jitter)

        if elapsed < target_interval:
            wait_time = target_interval - elapsed
            print(f"[Cooldown] Enforcing safety cooldown: sleeping for {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)

    def record_post(self):
        self.last_post_timestamp = time.time()
        self.daily_post_count += 1
