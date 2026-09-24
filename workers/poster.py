import asyncio
import datetime
from pathlib import Path
from typing import Optional, List
from playwright.async_api import Page, BrowserContext, TimeoutError as PlaywrightTimeoutError

from config.settings import AppConfig
from core.browser import BrowserFactory, HumanActions
from core.rate_limiter import RateLimiter
from core.session import SessionManager
from core.proxy import ProxyManager
from payload.models import PostPayload, JobResult, AccountCredentials
from payload.spintax import SpintaxParser
from payload.exif_scrubber import ExifScrubber

class CraigslistPosterWorker:
    """
    Primary posting worker handling end-to-end Craigslist workflows:
    stealth navigation, category selection, spintax rendering, form inputs,
    image sanitization/uploading, and submission.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.browser_factory = BrowserFactory(config.browser)
        self.session_manager = SessionManager(config.sessions_dir)
        self.proxy_manager = ProxyManager(config.proxy)
        self.rate_limiter = RateLimiter(config.rate_limits)

    async def _click_continue(self, page: Page):
        """Click the standard continuation button with multi-selector fallback."""
        selectors = [
            "button:has-text('continue')",
            "button[name='go']",
            "input[type='submit'][value*='continue' i]",
            "button.continue",
            "input[name='go']",
            "button[type='submit']"
        ]
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, state="visible", timeout=2500)
                if el:
                    await HumanActions.human_click(page, sel)
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return True
            except Exception:
                continue
        return False

    async def _select_radio_option(self, page: Page, option_label: str) -> bool:
        """Selects radio input based on text content with fuzzy XPath and CSS fallbacks."""
        clean_label = option_label.strip().lower()
        
        # Candidate selector strategies
        candidates = [
            f"label:has-text('{option_label}')",
            f"xpath=//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{clean_label}')]",
            f"xpath=//li[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{clean_label}')]//input[@type='radio']",
            f"xpath=//label[contains(., '{option_label}')]/input[@type='radio']",
            f"input[type='radio'][value*='{clean_label[:3]}']"
        ]

        for sel in candidates:
            try:
                el = await page.wait_for_selector(sel, state="visible", timeout=2000)
                if el:
                    await el.click()
                    await asyncio.sleep(0.3)
                    return True
            except Exception:
                continue

        # If radio button didn't click directly, try evaluating in DOM
        clicked = await page.evaluate("""(textToFind) => {
            const labels = Array.from(document.querySelectorAll('label, li'));
            for (const el of labels) {
                if (el.textContent.toLowerCase().includes(textToFind)) {
                    const radio = el.querySelector('input[type="radio"]') || el;
                    radio.click();
                    return true;
                }
            }
            return false;
        }""", clean_label)

        return clicked

    async def execute_post(
        self,
        payload: PostPayload,
        account: Optional[AccountCredentials] = None,
        dry_run: bool = False
    ) -> JobResult:
        # Check rate limiter
        can_proceed, reason = self.rate_limiter.can_post()
        if not can_proceed:
            return JobResult(
                job_id=payload.id,
                success=False,
                error_message=f"Rate limit triggered: {reason}",
                timestamp=datetime.datetime.utcnow().isoformat()
            )

        # Enforce inter-post pacing
        await self.rate_limiter.wait_cooldown()

        # Resolve session & proxy
        account_id = account.account_id if account else "default_guest"
        storage_path = self.session_manager.get_storage_state_arg(account_id)
        proxy_dict = self.proxy_manager.get_playwright_proxy(session_key=account_id)

        context, page = await self.browser_factory.create_context(
            storage_state_path=storage_path,
            proxy=proxy_dict
        )

        spun_title = SpintaxParser.spin(payload.title_spintax)
        spun_body = SpintaxParser.spin(payload.body_spintax)

        try:
            # 1. Navigate to target Craigslist subdomain post entry
            post_entry_url = f"https://{payload.subdomain}.craigslist.org/"
            print(f"[{payload.id}] Navigating to {post_entry_url}...")
            await page.goto(post_entry_url, wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(1.0)

            # Look for 'create a posting' or 'post' link
            post_link_selectors = [
                "a#post",
                "a:has-text('create a posting')",
                "a:has-text('post to classifieds')",
                "a[href*='/cpo']",
                "a[href*='/d/post']"
            ]
            clicked_entry = False
            for sel in post_link_selectors:
                if await page.locator(sel).count() > 0:
                    await HumanActions.human_click(page, sel)
                    clicked_entry = True
                    break

            if not clicked_entry:
                # Direct fallback URL
                await page.goto(f"https://post.craigslist.org/c/{payload.subdomain}", wait_until="domcontentloaded")

            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(1.5)

            # 2. Select Post Type (e.g. 'for sale by owner')
            print(f"[{payload.id}] Selecting post type: {payload.type_of_post}")
            await self._select_radio_option(page, payload.type_of_post)
            await self._click_continue(page)

            # 3. Handle optional Sub-area navigation (if city has subareas like SF Bay Area or NYC)
            if payload.sub_area:
                print(f"[{payload.id}] Selecting sub-area: {payload.sub_area}")
                await asyncio.sleep(1.0)
                selected_sub = await self._select_radio_option(page, payload.sub_area)
                if selected_sub:
                    await self._click_continue(page)

            # 4. Select Category
            print(f"[{payload.id}] Selecting category: {payload.category}")
            await asyncio.sleep(1.0)
            await self._select_radio_option(page, payload.category)
            await self._click_continue(page)

            # 5. Populate Main Post Form
            print(f"[{payload.id}] Filling post payload...")
            await page.wait_for_selector("#PostingTitle, input[name='PostingTitle']", state="visible", timeout=15000)

            # Title
            await HumanActions.human_type(page, "#PostingTitle, input[name='PostingTitle']", spun_title)

            # Price
            if payload.price:
                price_sel = "input[name='price'], #price"
                if await page.locator(price_sel).count() > 0:
                    await HumanActions.human_type(page, price_sel, payload.price)

            # Postal code
            postal_sel = "input[name='postal'], #postal_code, input[name='postal_code']"
            if await page.locator(postal_sel).count() > 0:
                await HumanActions.human_type(page, postal_sel, payload.postal_code)

            # Neighborhood
            if payload.neighborhood:
                geo_sel = "input[name='geographic_area'], #geographic_area"
                if await page.locator(geo_sel).count() > 0:
                    await HumanActions.human_type(page, geo_sel, payload.neighborhood)

            # Body / Description
            body_sel = "textarea[name='PostingBody'], #PostingBody"
            await page.wait_for_selector(body_sel, state="visible")
            await HumanActions.human_type(page, body_sel, spun_body)

            # Optional Attributes (Condition, Delivery, etc.)
            if payload.attributes.condition:
                cond_sel = "select[name='condition']"
                if await page.locator(cond_sel).count() > 0:
                    await page.select_option(cond_sel, label=payload.attributes.condition)

            # Submit form to next step (Map / Location verification)
            await self._click_continue(page)
            await asyncio.sleep(1.5)

            # 6. Map / Location confirmation screen (if shown)
            map_continue = await self._click_continue(page)
            if map_continue:
                await asyncio.sleep(1.5)

            # 7. Image Uploading with EXIF Scrubbing
            if payload.images:
                print(f"[{payload.id}] Scrubbing {len(payload.images)} images...")
                cleaned_images = ExifScrubber.clean_batch(payload.images)
                
                # Check for file input
                file_input_sel = "input[type='file']"
                if await page.locator(file_input_sel).count() > 0:
                    print(f"[{payload.id}] Uploading sanitized images...")
                    await page.set_input_files(file_input_sel, cleaned_images)
                    # Allow time for upload completion
                    await asyncio.sleep(3.0)

                # Done with images button
                done_imgs_sel = "button:has-text('done with images'), input[value*='done with images' i]"
                if await page.locator(done_imgs_sel).count() > 0:
                    await HumanActions.human_click(page, done_imgs_sel)
                    await page.wait_for_load_state("domcontentloaded")

            # 8. Preview & Verification Stage
            print(f"[{payload.id}] Post preview generated.")
            await asyncio.sleep(1.5)

            publish_button_sel = "button:has-text('publish'), input[type='submit'][value*='publish' i], button.publish"

            if dry_run:
                screenshot_path = Path("data") / f"dry_run_{payload.id}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path))
                print(f"[{payload.id}] [DRY-RUN] Saved preview snapshot to {screenshot_path}")

                return JobResult(
                    job_id=payload.id,
                    success=True,
                    post_url="https://craigslist.org/preview-dry-run-mode",
                    generated_title=spun_title,
                    timestamp=datetime.datetime.utcnow().isoformat()
                )

            # 9. Final Publication
            print(f"[{payload.id}] Publishing post...")
            await HumanActions.human_click(page, publish_button_sel)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Save session state if account logged in
            if account:
                await self.session_manager.save_session(context, account.account_id)

            self.rate_limiter.record_post()

            current_url = page.url
            return JobResult(
                job_id=payload.id,
                success=True,
                post_url=current_url,
                generated_title=spun_title,
                timestamp=datetime.datetime.utcnow().isoformat()
            )

        except PlaywrightTimeoutError as te:
            error_shot = Path("data") / f"error_timeout_{payload.id}.png"
            error_shot.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(error_shot))
            return JobResult(
                job_id=payload.id,
                success=False,
                error_message=f"Timeout occurred during step navigation: {str(te)} (Saved debug screenshot to {error_shot})",
                timestamp=datetime.datetime.utcnow().isoformat()
            )
        except Exception as e:
            error_shot = Path("data") / f"error_{payload.id}.png"
            error_shot.parent.mkdir(parents=True, exist_ok=True)
            try:
                await page.screenshot(path=str(error_shot))
            except Exception:
                pass
            return JobResult(
                job_id=payload.id,
                success=False,
                error_message=str(e),
                timestamp=datetime.datetime.utcnow().isoformat()
            )
        finally:
            await context.close()
            await self.browser_factory.close()
