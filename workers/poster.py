import re
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
    def __init__(self, config: AppConfig):
        self.config = config
        self.browser_factory = BrowserFactory(config.browser)
        self.session_manager = SessionManager(config.sessions_dir)
        self.proxy_manager = ProxyManager(config.proxy)
        self.rate_limiter = RateLimiter(config.rate_limits)

    async def _safe_fill_input(self, page: Page, selectors: List[str], text: str, description: str = "") -> bool:
        """Finds, focuses, and reliably fills an input, triggering input/change events."""
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    await loc.wait_for(state="visible", timeout=3000)
                    await loc.scroll_into_view_if_needed()
                    await loc.click()
                    await loc.fill(text)
                    await loc.dispatch_event("input")
                    await loc.dispatch_event("change")
                    val = await loc.input_value()
                    if val.strip():
                        print(f"[{description}] Populated '{sel}' with: {val}")
                        return True
            except Exception:
                continue

        # DOM evaluation fallback
        js_ok = await page.evaluate("""([sels, val]) => {
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el) {
                    el.focus();
                    el.value = val;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
            }
            const allInputs = Array.from(document.querySelectorAll('input, textarea'));
            for (const inp of allInputs) {
                const name = (inp.name || '').toLowerCase();
                const id = (inp.id || '').toLowerCase();
                const parent = inp.closest('label') || inp.parentElement;
                const pText = parent ? parent.textContent.toLowerCase() : '';
                if (name.includes('postal') || name.includes('zip') || id.includes('postal') || id.includes('zip') || pText.includes('zip')) {
                    inp.focus();
                    inp.value = val;
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
            }
            return false;
        }""", [selectors, text])

        if js_ok:
            print(f"[{description}] Populated via DOM fallback with: {text}")
            return True

        print(f"[{description}] WARNING: Could not populate {selectors}")
        return False

    async def _click_continue(self, page: Page) -> bool:
        selectors = [
            "button.submit-button",
            "button[name='go']",
            "form.pe-flow-continue button",
            "button:has-text('continue')",
            "button.big-button",
            "button.bigbutton",
            "input[name='go']",
            "input[type='submit'][value*='continue' i]",
            "button.continue",
            "button[type='submit']",
            "input[type='submit']"
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click(delay=50)
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        pass
                    await asyncio.sleep(1.2)
                    return True
            except Exception:
                continue
        return False

    async def _select_radio_option(self, page: Page, option_label: str) -> bool:
        clean_label = option_label.strip().lower()

        # 1. Exact match on label text first (avoids outer wrapper label)
        try:
            exact_loc = page.locator("label").filter(has_text=re.compile(rf"^\s*{re.escape(clean_label)}\s*$", re.I))
            if await exact_loc.count() > 0:
                radio = exact_loc.first.locator("input[type='radio']")
                if await radio.count() > 0:
                    await radio.first.check(force=True)
                    await asyncio.sleep(0.3)
                    if await radio.first.is_checked():
                        return True
        except Exception:
            pass

        # 2. DOM evaluate with exact-match precedence
        checked = await page.evaluate("""(textToFind) => {
            const labels = Array.from(document.querySelectorAll('label'));
            // Exact match
            for (const lbl of labels) {
                if (lbl.textContent.trim().toLowerCase() === textToFind) {
                    const radio = lbl.querySelector('input[type="radio"]') || document.getElementById(lbl.getAttribute('for'));
                    if (radio) {
                        radio.checked = true;
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                        radio.dispatchEvent(new Event('click', { bubbles: true }));
                        return true;
                    }
                }
            }
            // Innermost substring match (exclude broad wrapper labels)
            for (const lbl of labels) {
                if (lbl.textContent.toLowerCase().includes(textToFind) && lbl.children.length <= 2) {
                    const radio = lbl.querySelector('input[type="radio"]') || document.getElementById(lbl.getAttribute('for'));
                    if (radio) {
                        radio.checked = true;
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                        radio.dispatchEvent(new Event('click', { bubbles: true }));
                        return true;
                    }
                }
            }
            return false;
        }""", clean_label)

        await asyncio.sleep(0.4)
        return checked

    async def execute_post(
        self,
        payload: PostPayload,
        account: Optional[AccountCredentials] = None,
        dry_run: bool = False
    ) -> JobResult:
        can_proceed, reason = self.rate_limiter.can_post()
        if not can_proceed:
            return JobResult(
                job_id=payload.id,
                success=False,
                error_message=f"Rate limit triggered: {reason}",
                timestamp=datetime.datetime.utcnow().isoformat()
            )

        await self.rate_limiter.wait_cooldown()

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
            post_entry_url = f"https://post.craigslist.org/c/{payload.subdomain}"
            print(f"[{payload.id}] Navigating directly to {post_entry_url}...")
            await page.goto(post_entry_url, wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(1.5)

            city_area_map = {
                "losangeles": "los angeles",
                "miami": "south florida",
                "newyork": "new york city",
                "houston": "houston",
                "chicago": "chicago",
                "atlanta": "atlanta",
                "lasvegas": "las vegas",
                "dallas": "dallas / ft worth",
                "austin": "austin",
                "phoenix": "phoenix"
            }
            target_city_name = city_area_map.get(payload.subdomain.lower(), payload.subdomain.lower())

            max_nav_steps = 15
            nav_step = 0
            while nav_step < max_nav_steps:
                nav_step += 1
                await asyncio.sleep(1.0)
                cur_title = (await page.title()).lower()

                if await page.locator("#PostingTitle, input[name='PostingTitle']").count() > 0:
                    print(f"[{payload.id}] Reached main posting form!")
                    break

                # 0. Skip "copy from previous" if prompted
                if "copy from previous" in cur_title or await page.locator("button[name='brand_new_post']").count() > 0:
                    print(f"[{payload.id}] Skipping copy-from-previous to start fresh {payload.subdomain} post...")
                    await page.locator("button[name='brand_new_post'], button:has-text('skip')").first.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(1.0)
                    continue

                # 1. Area Dropdown (e.g. choose area on losangeles -> los angeles; on miami -> south florida)
                if "choose area" in cur_title or "?s=area" in page.url or await page.locator("#ui-id-1-button, select#ui-id-1, select[name='n'], select[name='areaId']").count() > 0:
                    print(f"[{payload.id}] Selecting area '{target_city_name}' from dropdown...")
                    try:
                        sel_result = await page.evaluate("""(targetCity) => {
                            const sel = document.querySelector("#ui-id-1, select[name='n'], select[name='areaId']");
                            if (!sel) return {success: false, reason: "No select found"};
                            const target = targetCity.toLowerCase().trim();
                            for (const opt of sel.options) {
                                const text = opt.text.toLowerCase().trim();
                                if (text === target || text.startsWith(target + ',') || text.includes(target)) {
                                    sel.value = opt.value;
                                    sel.dispatchEvent(new Event('input', { bubbles: true }));
                                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                                    return {success: true, text: opt.text.trim(), val: opt.value};
                                }
                            }
                            return {success: false, reason: "No match for " + targetCity};
                        }""", target_city_name)
                        print(f"[{payload.id}] Area selection result: {sel_result}")

                        if await page.locator("#ui-id-1-button").count() > 0 and sel_result.get("success"):
                            await page.evaluate("""(txt) => {
                                const btn = document.querySelector("#ui-id-1-button");
                                if (btn) btn.textContent = txt;
                            }""", sel_result.get("text", target_city_name))

                        await self._click_continue(page)
                        await page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(1.5)
                        continue
                    except Exception as e:
                        print(f"[{payload.id}] Area dropdown notice: {e}")
                page_html = (await page.content()).lower()

                # 2. Sub-area (e.g. central LA, Manhattan)
                if ("which of these areas" in page_html or "sub-area" in page_html or "nearest" in page_html or "nearest area" in cur_title or "?s=subarea" in page.url) and payload.sub_area:
                    print(f"[{payload.id}] Selecting sub-area: {payload.sub_area}")
                    selected = await self._select_radio_option(page, payload.sub_area)
                    if selected:
                        await self._click_continue(page)
                    continue

                # 2b. Neighborhood / Hood (e.g. NYC has choose neighborhood: Midtown, Downtown, or bypass)
                if "choose neighborhood" in cur_title or "choose the location that fits best" in page_html or "?s=hood" in page.url:
                    target_hood = payload.neighborhood or "Midtown"
                    print(f"[{payload.id}] Selecting neighborhood: {target_hood}")
                    selected = await self._select_radio_option(page, target_hood)
                    if not selected:
                        selected = await self._select_radio_option(page, "bypass this step")
                    if selected:
                        await self._click_continue(page)
                    continue

                # 3. Post Type (e.g. community)
                if "what type of posting is this" in page_html or "?s=type" in page.url or "choose type" in cur_title:
                    print(f"[{payload.id}] Selecting post type: {payload.type_of_post}")
                    selected = await self._select_radio_option(page, payload.type_of_post)
                    if selected:
                        await self._click_continue(page)
                    continue

                # 4. Category (e.g. activity partners)
                if "choose a category" in page_html or "select a category" in page_html or "?s=cat" in page.url or "choose category" in cur_title:
                    print(f"[{payload.id}] Selecting category: {payload.category}")
                    selected = await self._select_radio_option(page, payload.category)
                    if selected:
                        await self._click_continue(page)
                    continue

                # Generic continue if available
                if await page.locator("button.submit-button, button[name='go'], button:has-text('continue')").count() > 0:
                    print(f"[{payload.id}] Advancing through intermediate step...")
                    await self._click_continue(page)
                else:
                    break

            print(f"[{payload.id}] Filling post payload using fast copy-paste style...")
            await page.wait_for_selector("#PostingTitle, input[name='PostingTitle']", state="visible", timeout=20000)

            # 1. Posting Title (instant copy-paste fill, truncated to 70 chars max for Craigslist)
            clean_title = spun_title[:70]
            await page.fill("#PostingTitle", clean_title)
            print(f"[{payload.id}] Title pasted: {clean_title}")

            # 2. Neighborhood
            neighborhood_val = payload.neighborhood or "Central LA"
            if await page.locator("#geographic_area").count() > 0:
                await page.fill("#geographic_area", neighborhood_val)
                print(f"[{payload.id}] Neighborhood pasted: {neighborhood_val}")

            # 3. Postal / ZIP code (GUARANTEED FAST FILL & VERIFY)
            postal_to_use = str(payload.postal_code or "90012").strip()
            zip_loc = page.locator("#postal_code, input[name='postal']").first
            if await zip_loc.count() > 0:
                await zip_loc.click()
                await zip_loc.fill(postal_to_use)
                await page.evaluate("""(val) => {
                    const el = document.querySelector('#postal_code') || document.querySelector('input[name="postal"]');
                    if (el) {
                        el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""", postal_to_use)
                actual_zip = await zip_loc.input_value()
                print(f"[{payload.id}] Verified ZIP code entered: {actual_zip}")

            # 4. Description Body (instant copy-paste fill)
            await page.fill("#PostingBody", spun_body)
            print(f"[{payload.id}] Description body pasted ({len(spun_body)} chars)")

            # 5. Price (if present)
            if payload.price and await page.locator("#price").count() > 0:
                await page.fill("#price", str(payload.price))

            # 6. Phone / Text contact options
            if payload.phone_number:
                try:
                    chk = page.locator("input[name='show_phone_ok']")
                    if await chk.count() > 0:
                        await chk.first.check(force=True)
                    await asyncio.sleep(0.15)
                    txt_chk = page.locator("input[name='contact_text_ok']")
                    if await txt_chk.count() > 0:
                        await txt_chk.first.check(force=True)
                    await asyncio.sleep(0.15)
                    phone_input = page.locator("input[name='contact_phone']")
                    if await phone_input.count() > 0:
                        await phone_input.first.fill(payload.phone_number)
                        print(f"[{payload.id}] Phone number filled: {payload.phone_number}")
                except Exception as ex:
                    print(f"[{payload.id}] Phone options note: {ex}")

            # Advance from the main form
            print(f"[{payload.id}] Submitting main post form...")
            await page.locator("button.submit-button, button[name='go']").first.click()
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2.0)

            # Check for validation error on form submission (e.g. missing postal code)
            err_box = page.locator(".error, .err, font[color='red'], p:has-text('Please supply a postal')")
            if await err_box.count() > 0 and await err_box.first.is_visible():
                print(f"[{payload.id}] [FORM RE-TRY] Postal code validation error detected! Refilling {postal_to_use}...")
                zip_loc = page.locator("#postal_code, input[name='postal']").first
                if await zip_loc.count() > 0:
                    await zip_loc.click()
                    await zip_loc.fill(postal_to_use)
                    await page.evaluate("""(val) => {
                        const el = document.querySelector('#postal_code') || document.querySelector('input[name="postal"]');
                        if (el) {
                            el.value = val;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }""", postal_to_use)
                    await asyncio.sleep(0.5)
                    await page.locator("button.submit-button, button[name='go']").first.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2.0)

            # Loop through subsequent steps (Missing price, Map, Images, Preview)
            for step_i in range(8):
                page_html = (await page.content()).lower()

                # Step: Missing price
                if "missing price" in page_html or "the item is free" in page_html:
                    print(f"[{payload.id}] Handling missing price screen: selecting 'The item is free'...")
                    await self._select_radio_option(page, "The item is free")
                    await self._click_continue(page)
                    continue
                cur_title = (await page.title()).lower()
                cur_url = page.url

                # Check if reached Preview screen
                publish_btn = page.locator("button:has-text('publish'), input[type='submit'][value*='publish' i], button.publish")
                if "preview" in cur_title or "?s=preview" in cur_url or (await publish_btn.count() > 0 and await publish_btn.first.is_visible()):
                    print(f"[{payload.id}] Reached Preview screen!")
                    break

                # Step: Map / geoverify
                if "map" in cur_title or "geoverify" in cur_url or "add map" in cur_title:
                    print(f"[{payload.id}] Advancing past location map...")
                    map_continue = page.locator("button.continue, button.bigbutton, button:has-text('continue'), button[name='go'], form.pe-flow-continue button, button.submit-button").first
                    if await map_continue.count() > 0:
                        await map_continue.scroll_into_view_if_needed()
                        await map_continue.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(2.0)
                        continue

                # Step: Images
                done_imgs = page.locator("button:has-text('done with images'), input[value*='done with images' i]")
                if await done_imgs.count() > 0 and await done_imgs.first.is_visible():
                    if payload.images:
                        file_input = page.locator("input[type='file']")
                        if await file_input.count() > 0:
                            valid_imgs = [str(Path(img).resolve()) for img in payload.images if Path(img).exists()]
                            if valid_imgs:
                                print(f"[{payload.id}] Uploading {len(valid_imgs)} promotional image(s): {valid_imgs}...")
                                try:
                                    await file_input.first.set_input_files(valid_imgs)
                                    print(f"[{payload.id}] Waiting for image upload processing...")
                                    await asyncio.sleep(5.0)
                                except Exception as img_err:
                                    print(f"[{payload.id}] Warning: Image upload error: {img_err}")
                    print(f"[{payload.id}] Advancing past image upload screen...")
                    await done_imgs.first.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2.0)
                    continue

                # Generic continue (never click publish buttons on preview)
                if not ("preview" in cur_title or "?s=preview" in cur_url):
                    cont_btn = page.locator("button.submit-button, form.pe-flow-continue button, button:has-text('continue')")
                    if await cont_btn.count() > 0 and await cont_btn.first.is_visible():
                        print(f"[{payload.id}] Advancing through step {step_i + 1}...")
                        await cont_btn.first.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(2.0)
                        continue

                await asyncio.sleep(1.0)

            # Preview & Verification Stage
            print(f"[{payload.id}] Post preview generated.")
            await asyncio.sleep(1.0)

            if dry_run:
                screenshot_path = Path("data") / f"dry_run_{payload.id}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path))
                print(f"[{payload.id}] [DRY-RUN] Saved preview snapshot to {screenshot_path}")

                return JobResult(
                    job_id=payload.id,
                    success=True,
                    post_url=page.url,
                    generated_title=clean_title,
                    timestamp=datetime.datetime.utcnow().isoformat()
                )

            # Final Publication
            print(f"[{payload.id}] Clicking Publish button...")
            publish_btn = page.locator("button.bigbutton[name='go'], button.button[name='go'], button:has-text('publish'), input[type='submit'][value*='publish' i]").first
            if await publish_btn.count() > 0:
                await publish_btn.scroll_into_view_if_needed()
                await publish_btn.click()
            else:
                await page.evaluate("""() => {
                    const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim().toLowerCase() === 'publish');
                    if (btn) btn.click();
                }""")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=12000)
            except Exception:
                pass
            await asyncio.sleep(3.0)

            # Check if phone verification is requested
            page_text = (await page.content()).lower()
            cur_url = page.url
            if "?s=pn" in cur_url or "phone verification" in page_text or "verification code on your mobile phone" in page_text:
                verify_phone = "9046866593"
                print("\n" + "="*65)
                print(f"[{payload.id}] [PHONE VERIFICATION REQUIRED] Submitting {verify_phone} via SMS in English...")
                print("="*65)

                phone_input = page.locator("input[name='pn_number'], input#inputPhone, input[name*='phone' i], input[type='tel']").first
                if await phone_input.count() > 0:
                    await phone_input.scroll_into_view_if_needed()
                    await phone_input.click()
                    await phone_input.fill("")
                    await phone_input.fill(verify_phone)
                    print(f"[{payload.id}] Phone number set to: {verify_phone}")

                    # Select Method: SMS & Language: English
                    await page.evaluate("""() => {
                        const s = document.querySelector("input[name='callType'][value='sms']");
                        if (s) { s.checked = true; s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); }
                        const l = document.querySelector("input[name='callLang'][value='en']");
                        if (l) { l.checked = true; l.dispatchEvent(new Event('input', {bubbles: true})); l.dispatchEvent(new Event('change', {bubbles: true})); }
                    }""")
                    sms_loc = page.locator("input[name='callType'][value='sms'], label:has-text('via text message')").first
                    if await sms_loc.count() > 0:
                        try:
                            await sms_loc.click()
                        except Exception:
                            pass
                    await asyncio.sleep(0.5)

                    # Click continue / send the code
                    continue_btn = page.locator("button[type='submit'][name='go'], button:has-text('continue')").first
                    if await continue_btn.count() > 0:
                        await continue_btn.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(2.5)

                # Check if Craigslist showed the 5-minute rate limit warning on this number
                page_text_now = (await page.content()).lower()
                if "too rapidly" in page_text_now or "wait 5 minutes" in page_text_now:
                    print("\n" + "!"*65)
                    print("⚠️  [NOTICE] Craigslist requires waiting 5 minutes before resending to 904-686-6593.")
                    print("    You can either enter an alternate mobile number to receive the SMS,")
                    print("    or press ENTER to wait and re-check.")
                    print("!"*65 + "\n")

                    import concurrent.futures
                    loop = asyncio.get_event_loop()
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    alt_phone = await loop.run_in_executor(executor, input, "[PROMPT] Enter alternate 10-digit number (or press ENTER to keep 904-686-6593): ")
                    if alt_phone and alt_phone.strip():
                        clean_alt = "".join(c for c in alt_phone.strip() if c.isdigit())
                        if len(clean_alt) >= 10:
                            p_inp = page.locator("input[name='pn_number'], input[type='tel']").first
                            await p_inp.click()
                            await p_inp.fill(clean_alt)
                            c_btn = page.locator("button[type='submit'][name='go'], button:has-text('continue')").first
                            await c_btn.click()
                            await page.wait_for_load_state("domcontentloaded")
                            await asyncio.sleep(2.5)

                # Capture SMS verification code entry snapshot
                sms_sent_shot = Path("data") / f"phone_verify_code_{payload.id}.png"
                await page.screenshot(path=str(sms_sent_shot))

                print("\n" + "*"*65)
                print("📲 *** SMS VERIFICATION CODE DISPATCHED ***")
                print("📲 Please check your mobile phone for the Craigslist code.")
                print("*"*65 + "\n")

                import concurrent.futures
                loop = asyncio.get_event_loop()
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

                prompt_str = "\n[PROMPT] Enter the 5 or 6-digit Craigslist code from your phone and press ENTER: "
                user_code = await loop.run_in_executor(executor, input, prompt_str)

                if user_code and user_code.strip():
                    clean_code = "".join(c for c in user_code.strip() if c.isdigit())
                    print(f"[{payload.id}] Entering verification code {clean_code} into Craigslist...")

                    code_inp = page.locator("input#inputCode, input[name*='code' i], input[type='text'], input[name='verification_code']").first
                    if await code_inp.count() > 0:
                        await code_inp.click()
                        await code_inp.fill("")
                        await code_inp.fill(clean_code)
                        await asyncio.sleep(0.5)

                    sub_btn = page.locator("button:has-text('continue'), button:has-text('submit'), button:has-text('verify'), input[type='submit']").first
                    if await sub_btn.count() > 0:
                        await sub_btn.click()
                        try:
                            await page.wait_for_load_state("networkidle", timeout=15000)
                        except Exception:
                            await page.wait_for_load_state("domcontentloaded", timeout=10000)
                        await asyncio.sleep(3.0)

                    print(f"[{payload.id}] ✓ Verification code submitted! Continuing posting cycle...")

            # Capture confirmation snapshot
            conf_shot = Path("data") / f"published_{payload.id}.png"
            await page.screenshot(path=str(conf_shot))
            print(f"[{payload.id}] Confirmation snapshot saved to {conf_shot}")

            if account:
                await self.session_manager.save_session(context, account.account_id)

            self.rate_limiter.record_post()

            current_url = page.url
            return JobResult(
                job_id=payload.id,
                success=True,
                post_url=current_url,
                generated_title=clean_title,
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