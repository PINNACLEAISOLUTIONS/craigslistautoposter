import os
import sys
from pathlib import Path

# Auto-switch to script directory regardless of where terminal was opened from
_SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(_SCRIPT_DIR)
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
# -*- coding: utf-8 -*-
"""
Pinnacle AI Solutions - Florida Statewide Automated Poster (post_pinnacle_florida.py)
-----------------------------------------------------------------------------------
Automates posting for Pinnacle AI Solutions across all major Florida markets.
- Custom AI Agents, Web Scraping, AI Voice Receptionists, and Web Development.
- Attaches the enhanced pinnacle_ai_promo.png image with the TinyURL.
- Posts every 10 minutes (or custom interval) across Florida cities.
- Syncs every published post into Neon PostgreSQL.
"""

import os
import sys
import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Optional, List, Dict
from rich.console import Console
from rich.table import Table

from config.settings import load_config
from payload.models import PostPayload, PostAttributes, AccountCredentials
from payload.spintax import SpintaxParser
from workers.poster import CraigslistPosterWorker

console = Console()

PROMO_IMAGE_PATH = Path("data") / "images" / "pinnacle_ai_promo.png"
CAMPAIGN_TEMPLATE_PATH = Path("data") / "templates" / "campaign_pinnacle_florida.json"

def get_pinnacle_payload(target_index: int = 0) -> PostPayload:
    with open(CAMPAIGN_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        campaign = json.load(f)

    target = campaign["targets"][target_index]
    subdomain = target["subdomain"]
    category = target["categories"][0]
    postal_code = target.get("postal_code", "32202")
    neighborhood = target.get("neighborhood", "Downtown")

    if category == "computers":
        title_source = campaign["content"].get("computer_title_spintax", campaign["content"]["title_spintax"])
    else:
        title_source = campaign["content"]["title_spintax"]

    spun_title = SpintaxParser.spin(title_source)
    spun_body = SpintaxParser.spin(campaign["content"]["body_spintax"])

    sub_slug = re.sub(r"[^a-zA-Z0-9]+", "-", target["city"]).strip("-").lower()
    post_id = f"pinnacle-{subdomain}-{sub_slug}-01"

    img_path_resolved = str(PROMO_IMAGE_PATH.resolve()) if PROMO_IMAGE_PATH.exists() else None
    images = [img_path_resolved] if img_path_resolved else []

    post_type = target.get("type_of_post", "community")
    price_val = "0" if post_type == "for sale by owner" else None

    return PostPayload(
        id=post_id,
        subdomain=subdomain,
        type_of_post=post_type,
        sub_area=None,
        category=category,
        title_spintax=spun_title,
        body_spintax=spun_body,
        price=price_val,
        postal_code=postal_code,
        neighborhood=neighborhood,
        attributes=PostAttributes(),
        images=images,
        show_phone_ok=True,
        phone_number=campaign["default_contact"]["phone"]
    )

async def sleep_with_countdown(seconds: int, next_city: str):
    """Informative live countdown timer in the terminal."""
    total_mins = seconds // 60
    console.print(f"\n[bold yellow]⏱️ Pacing interval: waiting {total_mins} minutes ({seconds}s) before posting to {next_city}...[/bold yellow]")
    step = 15
    for remaining in range(seconds, 0, -step):
        mins = remaining // 60
        secs = remaining % 60
        console.print(f"  [dim]...time until next post ({next_city}): {mins:02d}m {secs:02d}s remaining[/dim]")
        await asyncio.sleep(min(step, remaining))

async def main():
    parser = argparse.ArgumentParser(description="Pinnacle AI Solutions Florida Statewide Automated Poster")
    parser.add_argument("--publish", action="store_true", help="Publish live (without this, runs safe dry-run preview)")
    parser.add_argument("--interval-mins", type=int, default=10, help="Minutes between consecutive Florida cities (default: 10 minutes)")
    parser.add_argument("--cooldown", type=int, default=None, help="Explicit cooldown in seconds (overrides --interval-mins)")
    parser.add_argument("--start-city", type=int, default=0, help="Starting city index (default: 0 = Jacksonville)")
    parser.add_argument("--cities", type=str, default=None, help="Comma-separated city indices to post (e.g. 0,1,2,3)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    cfg = load_config()
    cfg.browser.headless = args.headless

    cooldown_secs = args.cooldown if args.cooldown is not None else (args.interval_mins * 60)

    sess_dir = Path("data") / "sessions"
    default_sess = sess_dir / "default_state.json"
    sessions = [default_sess] if default_sess.exists() else [s for s in sess_dir.glob("*_state.json") if "guest" not in s.name]
    account_obj = None
    if sessions:
        account_name = sessions[0].stem.replace("_state", "")
        account_obj = AccountCredentials(account_id=account_name, email="pinnacleaisoulutions@gmail.com")
        console.print(f"[bold green]✓ Using authenticated session: {sessions[0].name} (pinnacleaisoulutions@gmail.com)[/bold green]")
    else:
        console.print("[yellow]Warning: No saved session found, running as guest[/yellow]")

    with open(CAMPAIGN_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        campaign = json.load(f)

    all_targets = campaign["targets"]

    if args.cities:
        target_indices = [int(x.strip()) for x in args.cities.split(",") if x.strip()]
    else:
        target_indices = list(range(args.start_city, len(all_targets)))

    queued_cities = [all_targets[i]["city"] for i in target_indices]

    console.print(f"\n[bold cyan]══════════════════════════════════════════════════════════════[/bold cyan]")
    console.print(f"[bold cyan]    PINNACLE AI SOLUTIONS - FLORIDA STATEWIDE AUTO-POSTER     [/bold cyan]")
    console.print(f"[bold cyan]══════════════════════════════════════════════════════════════[/bold cyan]")
    console.print(f"[*] Total Florida Cities Queued: {len(target_indices)}")
    console.print(f"[*] Posting Interval:           {cooldown_secs // 60} minutes ({cooldown_secs}s)")
    console.print(f"[*] Promotional Image Attached: {PROMO_IMAGE_PATH}")
    console.print(f"[*] Direct TinyURL:             https://tinyurl.com/pinnacle-ai-solutions")
    console.print(f"[*] Contact Phone:              904-686-6593")
    console.print(f"[*] Run Mode:                   {'LIVE PUBLISH' if args.publish else 'DRY RUN PREVIEW'}")
    console.print(f"[*] Neon Database Sync:         Enabled (craigslist_posts)")
    console.print(f"[bold cyan]──────────────────────────────────────────────────────────────[/bold cyan]")

    for idx, c_idx in enumerate(target_indices):
        t = all_targets[c_idx]
        console.print(f"  {idx + 1:02d}. {t['city']} ({t['subdomain']}.craigslist.org) - ZIP {t['postal_code']}")

    console.print(f"[bold cyan]══════════════════════════════════════════════════════════════[/bold cyan]\n")

    for step_num, c_idx in enumerate(target_indices):
        t = all_targets[c_idx]
        city_name = t["city"]
        subdomain = t["subdomain"]

        payload = get_pinnacle_payload(target_index=c_idx)
        dry_run = not args.publish

        console.print(f"\n[bold magenta]══════════════════════════════════════════════════════════════[/bold magenta]")
        console.print(f"[bold yellow]Posting [{step_num + 1}/{len(target_indices)}]: {city_name} (https://{subdomain}.craigslist.org)[/bold yellow]")
        console.print(f"[bold white]Title: {payload.title_spintax[:65]}...[/bold white]")
        console.print(f"[bold white]Category: {payload.category} | Postal Code: {payload.postal_code} | Hood: {payload.neighborhood}[/bold white]")
        console.print(f"[bold magenta]══════════════════════════════════════════════════════════════[/bold magenta]")

        worker = CraigslistPosterWorker(cfg)
        result = await worker.execute_post(payload, account=account_obj, dry_run=dry_run)

        table = Table(title=f"Result: {city_name} (Pinnacle AI)")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green" if result.success else "red")
        table.add_row("Success", str(result.success))
        table.add_row("Job ID", result.job_id)
        table.add_row("City", city_name)
        table.add_row("Title", result.generated_title or "N/A")
        table.add_row("URL / Status", result.post_url or "N/A")
        if result.error_message:
            table.add_row("Error", result.error_message)
        console.print(table)

        if result.success and args.publish:
            try:
                from core.db import log_post_to_neon
                log_post_to_neon(
                    job_id=result.job_id,
                    city=f"{city_name} (FL)",
                    subdomain=subdomain,
                    title=result.generated_title or payload.title_spintax,
                    post_url=result.post_url,
                    phone_used="904-686-6593",
                    status="published"
                )
            except Exception as e:
                console.print(f"[red]Database log error: {e}[/red]")

        # 10-minute cooldown break between Florida cities
        if step_num < len(target_indices) - 1:
            next_target = all_targets[target_indices[step_num + 1]]
            next_city = next_target["city"]
            console.print(f"\n[bold green]✓ Completed posting to {city_name}.[/bold green]")
            console.print(f"[bold cyan]Up next in queue: {next_city}[/bold cyan]")
            await sleep_with_countdown(cooldown_secs, next_city)

    console.print(f"\n[bold green]🎉 STATEWIDE ROTATION COMPLETE! All Florida cities processed successfully.[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
