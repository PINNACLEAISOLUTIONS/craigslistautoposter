import argparse
import asyncio
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

from config.settings import load_config
from payload.models import PostPayload, PostAttributes, AccountCredentials
from payload.spintax import SpintaxParser
from workers.poster import CraigslistPosterWorker

console = Console()

def get_campaign_payload(target_index: int = 0) -> PostPayload:
    campaign_file = Path("data") / "templates" / "campaign_multicity.json"
    with open(campaign_file, "r", encoding="utf-8") as f:
        campaign = json.load(f)

    target = campaign["targets"][target_index]
    sub_area = target["sub_areas"][0] if target["sub_areas"] else None
    category = target["categories"][0]

    spun_title = SpintaxParser.spin(campaign["content"]["title_spintax"])
    spun_body = SpintaxParser.spin(campaign["content"]["body_spintax"])

    return PostPayload(
        id=f"silverrose-{target['subdomain']}-01",
        subdomain=target["subdomain"],
        type_of_post="community",
        sub_area=sub_area,
        category=category,
        title_spintax=spun_title,
        body_spintax=spun_body,
        price=None,
        postal_code=target["postal_code"],
        neighborhood=target.get("neighborhood", "Downtown"),
        attributes=PostAttributes(),
        images=[],
        show_phone_ok=True,
        phone_number=campaign["default_contact"]["phone"]
    )

async def main():
    parser = argparse.ArgumentParser(description="Silver Rose Management Craigslist Poster")
    parser.add_argument("--publish", action="store_true", help="Publish live (otherwise runs dry-run preview)")
    parser.add_argument("--city-index", type=int, default=0, help="0=LA, 1=Miami, 2=NYC, 3=Houston, 4=Chicago")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    cfg = load_config()
    cfg.browser.headless = args.headless
    worker = CraigslistPosterWorker(cfg)

    sessions = list((Path("data") / "sessions").glob("*_state.json"))
    account_obj = None
    if sessions:
        account_name = sessions[0].stem.replace("_state", "")
        account_obj = AccountCredentials(account_id=account_name, email="user@cl")
        console.print(f"[bold green]Using session: {sessions[0].name}[/bold green]")
    else:
        console.print("[yellow]Warning: No saved session found, running as guest[/yellow]")

    payload = get_campaign_payload(target_index=args.city_index)
    dry_run = not args.publish

    console.print(f"\n[bold cyan]Starting Silver Rose Campaign for {payload.subdomain} (mode={'LIVE PUBLISH' if args.publish else 'DRY RUN PREVIEW'})...[/bold cyan]")
    result = await worker.execute_post(payload, account=account_obj, dry_run=dry_run)

    table = Table(title="Execution Result")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green" if result.success else "red")
    table.add_row("Success", str(result.success))
    table.add_row("Job ID", result.job_id)
    table.add_row("Title", result.generated_title or "N/A")
    table.add_row("URL / Status", result.post_url or "N/A")
    if result.error_message:
        table.add_row("Error", result.error_message)
    console.print(table)

if __name__ == "__main__":
    asyncio.run(main())
