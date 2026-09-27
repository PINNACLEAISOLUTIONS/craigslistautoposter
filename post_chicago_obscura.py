import os
import sys
from pathlib import Path

poster_dir = Path(__file__).resolve().parent
os.chdir(poster_dir)
if str(poster_dir) not in sys.path:
    sys.path.insert(0, str(poster_dir))

import asyncio
import json
import argparse
import datetime
from config.settings import load_config
from core.browser import BrowserFactory
from payload.spintax import SpintaxParser

CHICAGO_SUB_AREAS = [
    {"sub_area_key": "north chicagoland", "postal_code": "60201", "neighborhood": "North Chicagoland", "clean_name": "North Chicagoland"},
    {"sub_area_key": "west chicagoland", "postal_code": "60153", "neighborhood": "West Chicagoland", "clean_name": "West Chicagoland"},
    {"sub_area_key": "south chicagoland", "postal_code": "60402", "neighborhood": "South Chicagoland", "clean_name": "South Chicagoland"},
    {"sub_area_key": "city of chicago", "postal_code": "60601", "neighborhood": "Downtown Chicago", "clean_name": "City of Chicago"}
]

CHICAGO_SUB_AREAS_DICT = {item["sub_area_key"]: item for item in CHICAGO_SUB_AREAS}

CATEGORIES_TO_ROTATE = [
    "activity partners",
    "general community"
]

def build_rotation_plan():
    """
    Builds a continuous rotation plan where each subsequent post advances to the NEXT section 
    of the city, while continuously alternating between the 2 categories:
      Step 1: North Chicagoland  ──▶  Activity Partners
      Step 2: West Chicagoland   ──▶  General Community (with promo image)
      Step 3: South Chicagoland  ──▶  Activity Partners
      Step 4: City of Chicago    ──▶  General Community (with promo image)
      Step 5: North Chicagoland  ──▶  General Community (with promo image)
      Step 6: West Chicagoland   ──▶  Activity Partners
      Step 7: South Chicagoland  ──▶  General Community (with promo image)
      Step 8: City of Chicago    ──▶  Activity Partners
    """
    plan = []
    # Cycle 1: starts with category 0 (activity partners)
    for idx, sub in enumerate(CHICAGO_SUB_AREAS):
        cat = CATEGORIES_TO_ROTATE[idx % 2]
        plan.append({
            "sub_area_key": sub["sub_area_key"],
            "clean_name": sub["clean_name"],
            "postal_code": sub["postal_code"],
            "neighborhood": sub["neighborhood"],
            "category": cat
        })
    # Cycle 2: starts with category 1 (general community)
    for idx, sub in enumerate(CHICAGO_SUB_AREAS):
        cat = CATEGORIES_TO_ROTATE[(idx + 1) % 2]
        plan.append({
            "sub_area_key": sub["sub_area_key"],
            "clean_name": sub["clean_name"],
            "postal_code": sub["postal_code"],
            "neighborhood": sub["neighborhood"],
            "category": cat
        })
    return plan

async def select_radio_option(page, option_text: str) -> bool:
    """Reliably selects radio button by matching label text without strict mode collisions."""
    clean_target = option_text.strip().lower()
    selected = await page.evaluate("""(target) => {
        const labels = Array.from(document.querySelectorAll('label'));
        for (const lbl of labels) {
            const txt = lbl.innerText.trim().toLowerCase();
            const radios = lbl.querySelectorAll('input[type="radio"]');
            if (txt.includes(target) && radios.length === 1) {
                radios[0].checked = true;
                radios[0].dispatchEvent(new Event('change', { bubbles: true }));
                radios[0].dispatchEvent(new Event('click', { bubbles: true }));
                return true;
            }
        }
        const allRadios = Array.from(document.querySelectorAll('input[type="radio"]'));
        for (const r of allRadios) {
            const p = r.closest('label') || r.parentElement;
            if (p && p.innerText.trim().toLowerCase().includes(target)) {
                r.checked = true;
                r.dispatchEvent(new Event('change', { bubbles: true }));
                r.dispatchEvent(new Event('click', { bubbles: true }));
                return true;
            }
        }
        return false;
    }""", clean_target)
    await asyncio.sleep(0.4)
    return selected

async def click_continue_btn(page) -> bool:
    """Finds and clicks any continue or submit button."""
    selectors = [
        "button.submit-button",
        "button[name='go']",
        "form.pe-flow-continue button",
        "button:has-text('continue')",
        "button.bigbutton",
        "input[type='submit'][value*='continue' i]",
        "button[type='submit']"
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(1.5)
                return True
        except Exception:
            continue
    return False

async def upload_image_if_supported(context, page, image_path: Path) -> bool:
    """If the category accepts images (e.g. general community), attaches the Silver Rose promo image."""
    if not image_path.exists():
        return False
    try:
        img_btn = page.locator("button:has-text('edit images'), input[value*='edit images' i]").first
        if await img_btn.count() == 0 or not await img_btn.is_visible():
            print("[*] Category does not accept images (e.g. activity partners). Continuing without image.", flush=True)
            return False

        print(f"[*] Category accepts images! Attaching promo flyer: {image_path.name}...", flush=True)
        await img_btn.click()
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(1.5)

        cdp = await context.new_cdp_session(page)
        doc = await cdp.send("DOM.getDocument")
        node = await cdp.send("DOM.querySelector", {
            "nodeId": doc["root"]["nodeId"],
            "selector": "input[type='file']"
        })
        if node and node.get("nodeId"):
            await cdp.send("DOM.setFileInputFiles", {
                "files": [str(image_path.resolve())],
                "nodeId": node["nodeId"]
            })
            print(f"[✓] Promo image uploaded via CDP. Waiting for rendering...", flush=True)
            await asyncio.sleep(5)

            done_btn = page.locator("button#doneWithImages, button:has-text('done with images'), input[value*='done with images' i]").first
            if await done_btn.count() > 0:
                await done_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)
                print(f"[✓] Promo image successfully attached to live post!", flush=True)
                return True
    except Exception as e:
        print(f"[!] Image upload notice: {e}", flush=True)
    return False

async def countdown_timer(seconds: int, next_description: str):
    """Real-time terminal countdown timer updating every second."""
    print(f"\n{'='*65}", flush=True)
    print(f"⏳ [HOURLY PACING TIMER] Waiting {seconds // 60}m ({seconds}s) until next post...", flush=True)
    print(f"📍 [UP NEXT] {next_description}", flush=True)
    print(f"{'='*65}", flush=True)

    for remaining in range(seconds, 0, -1):
        mins = remaining // 60
        secs = remaining % 60
        sys.stdout.write(f"\r  ⏳ Next post in: {mins:02d}m {secs:02d}s | Target: {next_description}    ")
        sys.stdout.flush()
        await asyncio.sleep(1)

    sys.stdout.write("\r  🚀 Time's up! Launching next posting cycle now...                         \n\n")
    sys.stdout.flush()

async def post_to_chicago(sub_area_key: str = "city of chicago", category: str = "activity partners", publish: bool = False):
    cfg = load_config()
    cfg.browser.headless = False
    cfg.proxy.enabled = False  # Real IP, no proxies

    factory = BrowserFactory(cfg.browser)
    session_file = str(poster_dir / "data" / "sessions" / "default_state.json")

    campaign_file = poster_dir / "data" / "templates" / "campaign_multicity.json"
    with open(campaign_file, "r", encoding="utf-8") as f:
        campaign = json.load(f)

    sub_info = CHICAGO_SUB_AREAS_DICT.get(sub_area_key, CHICAGO_SUB_AREAS_DICT["city of chicago"])
    postal_code = sub_info["postal_code"]
    neighborhood = sub_info["neighborhood"]
    clean_name = sub_info["clean_name"]

    title = SpintaxParser.spin(campaign["content"]["title_spintax"])[:70]
    body = SpintaxParser.spin(campaign["content"]["body_spintax"])
    phone = campaign["default_contact"]["phone"]
    promo_img = poster_dir / "data" / "images" / "silver_rose_promo.png"

    job_id = f"silverrose-chicago-{sub_area_key.replace(' ', '-')}-{category.replace(' ', '-')}-01"

    print("\n" + "="*65, flush=True)
    print(f"[*] Posting Target: Chicago -> {clean_name}", flush=True)
    print(f"[*] Sub-Category:   {category.upper()}", flush=True)
    print(f"[*] Postal Code:    {postal_code} | Hood: {neighborhood}", flush=True)
    print(f"[*] Engine:         Obscura Stealth Engine (ws://127.0.0.1:9222)", flush=True)
    print(f"[*] Proxy:          DISABLED (Real IP)", flush=True)
    print(f"[*] Account:        chloecorazon2@gmail.com", flush=True)
    print(f"[*] Mode:           {'PUBLISH LIVE' if publish else 'DRY RUN PREVIEW'}", flush=True)
    print("="*65 + "\n", flush=True)

    context, page = await factory.create_context(storage_state_path=session_file)
    try:
        print("[1] Navigating to https://post.craigslist.org/c/chi ...", flush=True)
        await page.goto("https://post.craigslist.org/c/chi", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        for step in range(12):
            cur_url = page.url
            cur_title = (await page.title()).lower()
            print(f"Nav Step {step + 1}: {cur_title} ({cur_url})", flush=True)

            if "posting details" in cur_title or await page.locator("#PostingTitle").count() > 0:
                print(">>> REACHED POSTING DETAILS FORM! <<<", flush=True)
                break

            # 1. Copy from previous screen: uncheck all so we can set new location & category
            if "copy from previous" in cur_title or "copyfromanother" in cur_url:
                print("Handling copy screen: unchecking same_area, same_loc, same_category...", flush=True)
                await page.evaluate("""() => {
                    const a = document.querySelector('input[name="same_area"]'); if (a && a.checked) a.click();
                    const l = document.querySelector('input[name="same_loc"]'); if (l && l.checked) l.click();
                    const c = document.querySelector('input[name="same_category"]'); if (c && c.checked) c.click();
                }""")
                await asyncio.sleep(0.5)
                await page.locator("button[name='continue'], button:has-text('re-use')").first.click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)
                continue

            # 2. Area dropdown: select Chicago
            if "?s=area" in cur_url or "choose area" in cur_title:
                print("Selecting Chicago from dropdown...", flush=True)
                await page.evaluate("""() => {
                    const sel = document.querySelector("#ui-id-1, select[name='n'], select[name='areaId']");
                    if (sel) {
                        for (const opt of sel.options) {
                            if (opt.text.toLowerCase().trim() === 'chicago') {
                                sel.value = opt.value;
                                sel.dispatchEvent(new Event('input', { bubbles: true }));
                                sel.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    }
                }""")
                await asyncio.sleep(0.5)
                await click_continue_btn(page)
                continue

            # 3. Sub-area: select sub_area (e.g. city of chicago, north chicagoland, etc.)
            if "?s=subarea" in cur_url or "choose nearest area" in cur_title:
                print(f"Selecting subarea: {sub_area_key}...", flush=True)
                await select_radio_option(page, sub_area_key)
                await click_continue_btn(page)
                continue

            # 4. Type of post if prompted: community
            if "?s=type" in cur_url or "what type of posting" in cur_title or "choose type" in cur_title:
                print("Selecting community post type...", flush=True)
                await select_radio_option(page, "community")
                await click_continue_btn(page)
                continue

            # 5. Category if prompted: activity partners or general community
            if "?s=cat" in cur_url or "category" in cur_title or "choose category" in cur_title:
                print(f"Selecting category: {category}...", flush=True)
                await select_radio_option(page, category)
                await click_continue_btn(page)
                continue

            # Fallback continue
            await click_continue_btn(page)

        # FILLING POSTING DETAILS
        print(f"\n[2] Filling post details...", flush=True)
        print(f"Title: {title}", flush=True)
        print(f"ZIP: {postal_code} | Hood: {neighborhood}", flush=True)

        await page.wait_for_selector("#PostingTitle", state="visible", timeout=15000)
        await page.fill("#PostingTitle", title)

        if await page.locator("#geographic_area").count() > 0:
            await page.fill("#geographic_area", neighborhood)

        zip_el = page.locator("#postal_code, input[name='postal']").first
        if await zip_el.count() > 0:
            await zip_el.fill(postal_code)
            await page.evaluate(f"() => {{ const el = document.querySelector('#postal_code'); if (el) el.value = '{postal_code}'; }}")

        await page.fill("#PostingBody", body)

        # Phone contact
        chk = page.locator("input[name='show_phone_ok']")
        if await chk.count() > 0:
            await chk.first.check(force=True)
        txt_chk = page.locator("input[name='contact_text_ok']")
        if await txt_chk.count() > 0:
            await txt_chk.first.check(force=True)
        p_inp = page.locator("input[name='contact_phone']")
        if await p_inp.count() > 0:
            await p_inp.first.fill(phone)

        # Submit posting details form
        print("[3] Submitting posting details form...", flush=True)
        await page.locator("button.submit-button, button[name='go']").first.click()
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2.5)

        # Post-form steps (map, images, preview)
        for sub_step in range(6):
            cur_url = page.url
            cur_title = (await page.title()).lower()

            publish_btn = page.locator("button:has-text('publish'), input[value*='publish' i]")
            if "preview" in cur_title or "?s=preview" in cur_url or (await publish_btn.count() > 0 and await publish_btn.first.is_visible()):
                print("\n>>> PREVIEW SCREEN REACHED! <<<", flush=True)
                break

            # Map step
            if "map" in cur_title or "geoverify" in cur_url:
                print("Advancing past map...", flush=True)
                m_btn = page.locator("button.continue, button:has-text('continue'), button[name='go']").first
                if await m_btn.count() > 0:
                    await m_btn.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2)
                    continue

            # Images step
            done_imgs = page.locator("button:has-text('done with images'), input[value*='done with images' i]")
            if await done_imgs.count() > 0 and await done_imgs.first.is_visible():
                if promo_img.exists():
                    file_input = page.locator("input[type='file']")
                    if await file_input.count() > 0:
                        print(f"Uploading promo image: {promo_img.name}...", flush=True)
                        await file_input.first.set_input_files(str(promo_img.resolve()))
                        await asyncio.sleep(4)
                await done_imgs.first.click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)
                continue

            await click_continue_btn(page)

        # Attach promo image if category supports it (e.g. general community)
        if promo_img.exists():
            await upload_image_if_supported(context, page, promo_img)

        # Capture preview snapshot
        clean_sub_tag = sub_area_key.replace(' ', '_')
        clean_cat_tag = category.replace(' ', '_')
        shot_path = poster_dir / "data" / f"preview_chicago_{clean_sub_tag}_{clean_cat_tag}.png"
        await page.screenshot(path=str(shot_path))
        print(f"Saved preview screenshot to {shot_path}", flush=True)

        if not publish:
            print("\n[SUCCESS - DRY RUN] Verified! Halting safely at Preview screen.", flush=True)
            return True, page.url

        # Publish live
        print("\n[PUBLISH] Submitting live publication...", flush=True)
        pub_btn = page.locator("button.bigbutton[name='go'], button:has-text('publish')").first
        await pub_btn.click()
        try:
            await page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            await page.wait_for_load_state("domcontentloaded", timeout=8000)
        await asyncio.sleep(3)

        pub_shot = poster_dir / "data" / f"published_chicago_{clean_sub_tag}_{clean_cat_tag}.png"
        await page.screenshot(path=str(pub_shot))
        final_url = page.url

        # Log to Neon DB
        try:
            from core.db import log_post_to_neon
            log_post_to_neon(
                job_id=job_id,
                city=f"Chicago ({clean_name} - {category})",
                subdomain="chicago",
                title=title,
                post_url=final_url,
                phone_used=phone,
                status="published"
            )
        except Exception as e:
            print(f"[Neon DB Notice]: {e}")

        # Update saved session
        session_path = poster_dir / "data" / "sessions" / "default_state.json"
        await context.storage_state(path=str(session_path))

        print(f"\n[SUCCESS 🎉] Post published live: {final_url}", flush=True)
        return True, final_url

    finally:
        await factory.close()

async def run_rotation(interval_mins: int = 60, publish: bool = False, start_step: int = 0, loop: bool = True):
    plan = build_rotation_plan()
    cooldown_secs = interval_mins * 60

    print("\n" + "═"*65, flush=True)
    print("   CHICAGO CONTINUOUS HOURLY ROTATION QUEUE", flush=True)
    print("═"*65, flush=True)
    print(f"[*] Total Steps in Cycle: {len(plan)}", flush=True)
    print(f"[*] Hourly Cooldown:      {interval_mins} minutes ({cooldown_secs}s)", flush=True)
    print(f"[*] Mode:                 {'LIVE PUBLICATION' if publish else 'DRY RUN PREVIEW'}", flush=True)
    print(f"[*] Engine:               Obscura Stealth Browser (ws://127.0.0.1:9222)", flush=True)
    print(f"[*] Account:              chloecorazon2@gmail.com", flush=True)
    print("─"*65, flush=True)
    for idx, item in enumerate(plan):
        marker = "▶" if idx == start_step else " "
        img_note = " (+ Promo Image)" if item['category'] == "general community" else ""
        print(f" {marker} Step {idx + 1:02d}: {item['clean_name']}  ──▶  {item['category'].upper()}{img_note}", flush=True)
    print("═"*65 + "\n", flush=True)

    current_step = start_step
    while True:
        step_idx = current_step % len(plan)
        step_item = plan[step_idx]
        cycle_num = (current_step // len(plan)) + 1
        print(f"\n[RUNNING STEP {step_idx + 1}/{len(plan)} (Cycle {cycle_num})]: Chicago ({step_item['clean_name']}) -> {step_item['category']}", flush=True)

        try:
            success, url = await post_to_chicago(
                sub_area_key=step_item["sub_area_key"],
                category=step_item["category"],
                publish=publish
            )
        except Exception as err:
            print(f"\n[ERROR on Step {step_idx + 1}]: {err}", flush=True)
            print("Taking a short 2-minute safety pause before continuing rotation...", flush=True)
            await asyncio.sleep(120)
            current_step += 1
            continue

        current_step += 1
        if not loop and current_step >= len(plan):
            break

        next_idx = current_step % len(plan)
        next_item = plan[next_idx]
        next_desc = f"Chicago ({next_item['clean_name']}) -> {next_item['category']}"
        await countdown_timer(cooldown_secs, next_desc)

    print("\n[🎉 ROTATION COMPLETE] All Chicago sub-areas and categories processed successfully!", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chicago Silver Rose Hourly Continuous Auto-Poster")
    parser.add_argument("--publish", action="store_true", help="Publish live (default: preview dry-run)")
    parser.add_argument("--continuous", action="store_true", help="Run full continuous rotation across sub-categories and sections")
    parser.add_argument("--interval-mins", type=int, default=60, help="Interval between posts in minutes (default: 60)")
    parser.add_argument("--sub-area", default="city of chicago", choices=list(CHICAGO_SUB_AREAS.keys()), help="Single sub-area")
    parser.add_argument("--category", default="activity partners", choices=CATEGORIES_TO_ROTATE, help="Single category")
    parser.add_argument("--start-step", type=int, default=0, help="Step index to start rotation at (0-based)")
    args = parser.parse_args()

    if args.continuous:
        asyncio.run(run_rotation(interval_mins=args.interval_mins, publish=args.publish, start_step=args.start_step))
    else:
        asyncio.run(post_to_chicago(sub_area_key=args.sub_area, category=args.category, publish=args.publish))
