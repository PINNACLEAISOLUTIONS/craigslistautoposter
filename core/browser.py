import asyncio
import math
import random
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, ElementHandle
from config.settings import BrowserConfig

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

COMMON_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

COMMON_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

class BrowserFactory:
    """
    Spawns stealth-configured Playwright browsers with human-like interaction heuristics.
    """
    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def initialize(self):
        if self._playwright is None:
            self._playwright = await async_playwright().start()

    async def create_context(
        self,
        storage_state_path: Optional[str] = None,
        proxy: Optional[Dict[str, str]] = None
    ) -> tuple[BrowserContext, Page]:
        await self.initialize()

        viewport = random.choice(COMMON_VIEWPORTS)
        user_agent = self.config.user_agent or random.choice(COMMON_USER_AGENTS)

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo_ms,
            args=launch_args
        )

        context_kwargs = {
            "viewport": viewport,
            "user_agent": user_agent,
            "locale": "en-US",
            "timezone_id": "America/Los_Angeles",
            "geolocation": {"longitude": -122.4194, "latitude": 37.7749},
            "permissions": ["geolocation"],
        }

        if proxy:
            context_kwargs["proxy"] = proxy

        if storage_state_path:
            context_kwargs["storage_state"] = storage_state_path

        context = await self._browser.new_context(**context_kwargs)
        page = await context.new_page()

        # Apply stealth scripts
        if stealth_async:
            await stealth_async(page)
        else:
            # Fallback inline anti-detect evasions
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

        return context, page

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


class HumanActions:
    """
    Simulates organic human interaction: typing with jitter, bezier curve mouse movement.
    """
    @staticmethod
    async def human_type(page: Page, selector: str, text: str, min_delay: int = 40, max_delay: int = 120):
        """Types string character by character with randomized inter-key pauses."""
        element = await page.wait_for_selector(selector, state="visible", timeout=10000)
        await element.click()
        await asyncio.sleep(random.uniform(0.1, 0.3))

        for char in text:
            await page.keyboard.type(char)
            delay = random.uniform(min_delay / 1000.0, max_delay / 1000.0)
            # Occasional pause representing thinking / hesitation
            if char in (" ", ",", "."):
                delay += random.uniform(0.08, 0.25)
            await asyncio.sleep(delay)

    @staticmethod
    async def organic_mouse_move(page: Page, target_x: float, target_y: float, steps: int = 15):
        """Moves mouse across an organic curved path with jitter to simulate human hand."""
        start_x = random.randint(100, 300)
        start_y = random.randint(100, 300)

        for i in range(steps + 1):
            t = i / steps
            # Quadratic bezier interpolation with randomized control point
            ctrl_x = (start_x + target_x) / 2 + random.uniform(-40, 40)
            ctrl_y = (start_y + target_y) / 2 + random.uniform(-40, 40)

            cur_x = (1 - t)**2 * start_x + 2 * (1 - t) * t * ctrl_x + t**2 * target_x
            cur_y = (1 - t)**2 * start_y + 2 * (1 - t) * t * ctrl_y + t**2 * target_y

            # Micro-jitter
            cur_x += random.uniform(-1.5, 1.5)
            cur_y += random.uniform(-1.5, 1.5)

            await page.mouse.move(cur_x, cur_y)
            await asyncio.sleep(random.uniform(0.008, 0.025))

    @classmethod
    async def human_click(cls, page: Page, selector: str):
        """Moves cursor organically to selector and clicks with brief hold."""
        el = await page.wait_for_selector(selector, state="visible", timeout=12000)
        box = await el.bounding_box()
        if box:
            target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            await cls.organic_mouse_move(page, target_x, target_y)
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await el.click(delay=random.randint(60, 150))
        else:
            await el.click()
        await asyncio.sleep(random.uniform(0.2, 0.5))
