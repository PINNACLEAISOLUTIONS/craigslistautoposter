import os
import sys
from pathlib import Path

# Auto-switch to script directory regardless of where terminal was opened from
_SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(_SCRIPT_DIR)
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
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

SUB_AREA_DETAILS: Dict[str, Dict[str, Dict[str, str]]] = {
    "losangeles": {
        "westside-southbay-310": {"postal_code": "90291", "neighborhood": "Westside / South Bay", "clean_name": "Westside & South Bay"},
        "san fernando valley": {"postal_code": "91401", "neighborhood": "San Fernando Valley", "clean_name": "San Fernando Valley"},
        "central LA 213/323": {"postal_code": "90012", "neighborhood": "Central LA", "clean_name": "Central LA"},
        "san gabriel valley": {"postal_code": "91776", "neighborhood": "San Gabriel Valley", "clean_name": "San Gabriel Valley"},
        "long beach / 562": {"postal_code": "90802", "neighborhood": "Long Beach", "clean_name": "Long Beach"},
        "antelope valley": {"postal_code": "93534", "neighborhood": "Antelope Valley", "clean_name": "Antelope Valley"}
    },
    "miami": {
        "miami / dade": {"postal_code": "33101", "neighborhood": "Miami / Dade", "clean_name": "Miami / Dade"},
        "broward county": {"postal_code": "33301", "neighborhood": "Fort Lauderdale", "clean_name": "Broward County"},
        "palm beach county": {"postal_code": "33401", "neighborhood": "West Palm Beach", "clean_name": "Palm Beach County"}
    },
    "newyork": {
        "manhattan": {"postal_code": "10001", "neighborhood": "Manhattan", "clean_name": "Manhattan"},
        "brooklyn": {"postal_code": "11201", "neighborhood": "Brooklyn", "clean_name": "Brooklyn"},
        "queens": {"postal_code": "11101", "neighborhood": "Queens", "clean_name": "Queens"},
        "bronx": {"postal_code": "10451", "neighborhood": "The Bronx", "clean_name": "The Bronx"},
        "staten island": {"postal_code": "10301", "neighborhood": "Staten Island", "clean_name": "Staten Island"}
    },
    "chicago": {
        "city of chicago": {"postal_code": "60601", "neighborhood": "Downtown Chicago", "clean_name": "City of Chicago"},
        "north chicagoland": {"postal_code": "60201", "neighborhood": "North Chicagoland", "clean_name": "North Chicagoland"},
        "south chicagoland": {"postal_code": "60402", "neighborhood": "South Chicagoland", "clean_name": "South Chicagoland"},
        "west chicagoland": {"postal_code": "60153", "neighborhood": "West Chicagoland", "clean_name": "West Chicagoland"}
    },
    "atlanta": {
        "city of atlanta": {"postal_code": "30303", "neighborhood": "Downtown Atlanta", "clean_name": "City of Atlanta"},
        "fulton county": {"postal_code": "30305", "neighborhood": "North Fulton", "clean_name": "Fulton County"},
        "cobb county": {"postal_code": "30060", "neighborhood": "Marietta", "clean_name": "Cobb County"},
        "dekalb county": {"postal_code": "30030", "neighborhood": "Decatur", "clean_name": "DeKalb County"},
        "gwinnett county": {"postal_code": "30044", "neighborhood": "Lawrenceville", "clean_name": "Gwinnett County"}
    },
    "dallas": {
        "dallas": {"postal_code": "75201", "neighborhood": "Downtown Dallas", "clean_name": "Dallas"},
        "fort worth": {"postal_code": "76102", "neighborhood": "Downtown Fort Worth", "clean_name": "Fort Worth"},
        "mid-cities": {"postal_code": "76006", "neighborhood": "Arlington / Mid-Cities", "clean_name": "Mid-Cities"}
    },
    "phoenix": {
        "central / south phx": {"postal_code": "85001", "neighborhood": "Central Phoenix", "clean_name": "Central Phoenix"},
        "east valley": {"postal_code": "85201", "neighborhood": "East Valley / Mesa", "clean_name": "East Valley"},
        "west valley": {"postal_code": "85301", "neighborhood": "West Valley / Glendale", "clean_name": "West Valley"},
        "scottsdale": {"postal_code": "85251", "neighborhood": "Scottsdale", "clean_name": "Scottsdale"}
    }
}

def get_campaign_payload(target_index: int = 0, sub_area_name: Optional[str] = None) -> PostPayload:
    campaign_file = Path("data") / "templates" / "campaign_multicity.json"
    with open(campaign_file, "r", encoding="utf-8") as f:
        campaign = json.load(f)

    target = campaign["targets"][target_index]
    subdomain = target["subdomain"]
    sub_area = sub_area_name or (target["sub_areas"][0] if target.get("sub_areas") else None)
    category = target["categories"][0]

    postal_code = target.get("postal_code", "90012")
    neighborhood = target.get("neighborhood", "Downtown")

    if subdomain in SUB_AREA_DETAILS and sub_area in SUB_AREA_DETAILS[subdomain]:
        details = SUB_AREA_DETAILS[subdomain][sub_area]
        postal_code = details["postal_code"]
        neighborhood = details["neighborhood"]

    spun_title = SpintaxParser.spin(campaign["content"]["title_spintax"])
    spun_body = SpintaxParser.spin(campaign["content"]["body_spintax"])

    sub_slug = re.sub(r"[^a-zA-Z0-9]+", "-", (sub_area or "main")).strip("-").lower()
    post_id = f"silverrose-{subdomain}-{sub_slug}-01"

    return PostPayload(
        id=post_id,
        subdomain=subdomain,
        type_of_post="community",
        sub_area=sub_area,
        category=category,
        title_spintax=spun_title,
        body_spintax=spun_body,
        price=None,
        postal_code=postal_code,
        neighborhood=neighborhood,
        attributes=PostAttributes(),
        images=[str((Path("data") / "images" / "silver_rose_promo.png").resolve())] if (Path("data") / "images" / "silver_rose_promo.png").exists() else [],
        show_phone_ok=True,
        phone_number=campaign["default_contact"]["phone"]
    )

async def sleep_with_countdown(seconds: int):
    """Sleeps with an informative countdown timer in the terminal."""
    total_mins = seconds // 60
    console.print(f"\n[bold yellow]Pacing delay: waiting {total_mins} minutes ({seconds}s) before next post...[/bold yellow]")
    step = 30
    for remaining in range(seconds, 0, -step):
        mins = remaining // 60
        secs = remaining % 60
        console.print(f"  [dim]...time remaining until next post: {mins:02d}m {secs:02d}s[/dim]")
        await asyncio.sleep(min(step, remaining))

async def main():
    parser = argparse.ArgumentParser(description="Silver Rose Management Multi-City & Sub-City Craigslist Poster")
    parser.add_argument("--publish", action="store_true", help="Publish live (otherwise runs dry-run preview)")
    parser.add_argument("--continuous", action="store_true", help="Continuously rotate through all sub-cities in order, then next city")
    parser.add_argument("--interval-mins", type=int, default=35, help="Minutes between consecutive posts (default: 35 minutes)")
    parser.add_argument("--cooldown", type=int, default=None, help="Explicit cooldown in seconds (overrides --interval-mins)")
    parser.add_argument("--start-city", type=int, default=0, help="Starting city index (0=LA, 1=Miami, 2=NYC, etc.)")
    parser.add_argument("--la-subcities", action="store_true", help="Post only to LA sub-cities")
    parser.add_argument("--max-posts", type=int, default=None, help="Maximum number of sub-cities to post")
    parser.add_argument("--city-index", type=int, default=None, help="Target single city index")
    parser.add_argument("--cities", type=str, default=None, help="Comma-separated city indices to post")
    parser.add_argument("--all", action="store_true", help="Post across all targets")
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
        account_obj = AccountCredentials(account_id=account_name, email="user@cl")
        console.print(f"[bold green]Using authenticated session: {sessions[0].name}[/bold green]")
    else:
        console.print("[yellow]Warning: No saved session found, running as guest[/yellow]")

    campaign_file = Path("data") / "templates" / "campaign_multicity.json"
    with open(campaign_file, "r", encoding="utf-8") as f:
        campaign = json.load(f)

    # Build the full posting queue: list of (city_index, city_name, sub_area_name)
    queue: List[dict] = []

    if args.continuous or args.all:
        start_idx = args.start_city
        for c_idx in range(start_idx, len(campaign["targets"])):
            target = campaign["targets"][c_idx]
            sub_areas = target.get("sub_areas") or []
            if sub_areas:
                for sub in sub_areas:
                    queue.append({
                        "target_index": c_idx,
                        "city_name": target["city"],
                        "subdomain": target["subdomain"],
                        "sub_area": sub
                    })
            else:
                queue.append({
                    "target_index": c_idx,
                    "city_name": target["city"],
                    "subdomain": target["subdomain"],
                    "sub_area": None
                })
    elif args.la_subcities:
        la_target = campaign["targets"][0]
        sub_areas = la_target.get("sub_areas", [])
        if args.max_posts:
            sub_areas = sub_areas[:args.max_posts]
        for sub in sub_areas:
            queue.append({
                "target_index": 0,
                "city_name": la_target["city"],
                "subdomain": la_target["subdomain"],
                "sub_area": sub
            })
    elif args.cities:
        target_indices = [int(x.strip()) for x in args.cities.split(",") if x.strip()]
        for c_idx in target_indices:
            target = campaign["targets"][c_idx]
            queue.append({
                "target_index": c_idx,
                "city_name": target["city"],
                "subdomain": target["subdomain"],
                "sub_area": None
            })
    elif args.city_index is not None:
        target = campaign["targets"][args.city_index]
        queue.append({
            "target_index": args.city_index,
            "city_name": target["city"],
            "subdomain": target["subdomain"],
            "sub_area": None
        })
    else:
        # Default to continuous rotation starting from LA
        for c_idx in range(len(campaign["targets"])):
            target = campaign["targets"][c_idx]
            sub_areas = target.get("sub_areas") or []
            if sub_areas:
                for sub in sub_areas:
                    queue.append({
                        "target_index": c_idx,
                        "city_name": target["city"],
                        "subdomain": target["subdomain"],
                        "sub_area": sub
                    })
            else:
                queue.append({
                    "target_index": c_idx,
                    "city_name": target["city"],
                    "subdomain": target["subdomain"],
                    "sub_area": None
                })

    console.print(f"\n[bold cyan]══════════════════════════════════════════════════════════════[/bold cyan]")
    console.print(f"[bold cyan]    CRAIGSLIST CONTINUOUS MULTI-SUBSECTION ROTATION QUEUE    [/bold cyan]")
    console.print(f"[bold cyan]══════════════════════════════════════════════════════════════[/bold cyan]")
    console.print(f"[*] Total Posts in Queue: {len(queue)}")
    console.print(f"[*] Cooldown Between Posts: {cooldown_secs // 60} minutes ({cooldown_secs}s)")
    console.print(f"[*] Mode: {'LIVE PUBLISH' if args.publish else 'DRY RUN PREVIEW'}")
    console.print(f"[*] Neon Database Sync: Enabled")
    console.print(f"[bold cyan]──────────────────────────────────────────────────────────────[/bold cyan]")

    for pos, item in enumerate(queue):
        clean_sub = item["sub_area"] or "Main City"
        sub_info = SUB_AREA_DETAILS.get(item["subdomain"], {}).get(item["sub_area"], {})
        clean_sub = sub_info.get("clean_name", clean_sub)
        console.print(f"  {pos + 1:02d}. {item['city_name']} -> {clean_sub}")

    console.print(f"[bold cyan]══════════════════════════════════════════════════════════════[/bold cyan]\n")

    for idx, item in enumerate(queue):
        c_idx = item["target_index"]
        sub_area = item["sub_area"]
        city_name = item["city_name"]
        subdomain = item["subdomain"]

        sub_info = SUB_AREA_DETAILS.get(subdomain, {}).get(sub_area, {})
        clean_sub = sub_info.get("clean_name", sub_area or "Main City")

        payload = get_campaign_payload(target_index=c_idx, sub_area_name=sub_area)
        dry_run = not args.publish

        console.print(f"\n[bold magenta]══════════════════════════════════════════════════════════════[/bold magenta]")
        console.print(f"[bold yellow]Executing Post [{idx + 1}/{len(queue)}]: {city_name} -> {clean_sub}[/bold yellow]")
        console.print(f"[bold white]Subdomain: {subdomain} | Postal Code: {payload.postal_code} | Hood: {payload.neighborhood}[/bold white]")
        console.print(f"[bold magenta]══════════════════════════════════════════════════════════════[/bold magenta]")

        worker = CraigslistPosterWorker(cfg)
        result = await worker.execute_post(payload, account=account_obj, dry_run=dry_run)

        table = Table(title=f"Result: {city_name} ({clean_sub})")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green" if result.success else "red")
        table.add_row("Success", str(result.success))
        table.add_row("Job ID", result.job_id)
        table.add_row("Location", f"{city_name} - {clean_sub}")
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
                    city=f"{city_name} ({clean_sub})",
                    subdomain=subdomain,
                    title=result.generated_title or payload.title_spintax,
                    post_url=result.post_url,
                    phone_used="904-686-6593",
                    status="published"
                )
            except Exception as e:
                console.print(f"[red]Database log error: {e}[/red]")

        # After each post (sub-city or city), pause for the exact specified interval (35 minutes)
        if idx < len(queue) - 1:
            next_item = queue[idx + 1]
            next_sub = next_item["sub_area"] or "Main City"
            console.print(f"\n[bold green]✓ Completed post {idx + 1}/{len(queue)}.[/bold green]")
            console.print(f"[bold cyan]Up next: {next_item['city_name']} -> {next_sub}[/bold cyan]")
            await sleep_with_countdown(cooldown_secs)

    console.print(f"\n[bold green]🎉 FULL ROTATION COMPLETE! All sub-cities and cities processed successfully.[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
