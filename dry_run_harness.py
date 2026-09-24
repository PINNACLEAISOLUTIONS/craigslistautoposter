import asyncio
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

from config.settings import load_config
from payload.models import PostPayload, PostAttributes
from payload.spintax import SpintaxParser
from workers.poster import CraigslistPosterWorker

console = Console()

def generate_payload_from_campaign(campaign_file: Path, target_index: int = 0) -> PostPayload:
    with open(campaign_file, "r", encoding="utf-8") as f:
        campaign = json.load(f)

    target = campaign["targets"][target_index]
    sub_area = target["sub_areas"][0] if target["sub_areas"] else None
    category = target["categories"][0]

    spun_title = SpintaxParser.spin(campaign["content"]["title_spintax"])
    spun_body = SpintaxParser.spin(campaign["content"]["body_spintax"])

    return PostPayload(
        id=f"dryrun-{target['subdomain']}-01",
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

async def run_dry_run_test(headless: bool = False):
    campaign_file = Path("data") / "templates" / "campaign_multicity.json"
    if not campaign_file.exists():
        console.print(f"[bold red]Campaign file not found at {campaign_file}[/bold red]")
        return

    payload = generate_payload_from_campaign(campaign_file)
    cfg = load_config()
    cfg.browser.headless = headless

    console.print("\n[bold cyan]==================================================[/bold cyan]")
    console.print("[bold cyan]       CRAIGSLIST POSTER DRY-RUN TEST HARNESS     [/bold cyan]")
    console.print("[bold cyan]==================================================[/bold cyan]\n")
    console.print("[yellow]Safety Policy: Halts on Preview Screen. Will NOT click Publish.[/yellow]\n")

    summary_table = Table(title="Queued Test Payload (Dry-Run)")
    summary_table.add_column("Field", style="cyan")
    summary_table.add_column("Value", style="magenta")

    summary_table.add_row("City / Subdomain", payload.subdomain)
    summary_table.add_row("Sub-Area", payload.sub_area or "N/A")
    summary_table.add_row("Category", payload.category)
    summary_table.add_row("Postal Code", payload.postal_code)
    summary_table.add_row("Title", payload.title_spintax[:60] + "...")
    summary_table.add_row("Phone", payload.phone_number or "None")

    console.print(summary_table)

    worker = CraigslistPosterWorker(cfg)
    console.print("\n[bold green]Launching browser and executing form navigation...[/bold green]")
    
    result = await worker.execute_post(payload, dry_run=True)

    result_table = Table(title="Dry-Run Execution Outcome")
    result_table.add_column("Property", style="cyan")
    result_table.add_column("Status", style="green" if result.success else "red")

    result_table.add_row("Success", str(result.success))
    result_table.add_row("Job ID", result.job_id)
    result_table.add_row("Generated Title", result.generated_title or "N/A")
    if result.error_message:
        result_table.add_row("Error", result.error_message)

    preview_path = Path("data") / f"dry_run_{payload.id}.png"
    if preview_path.exists():
        result_table.add_row("Preview Snapshot", str(preview_path.resolve()))

    console.print(result_table)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dry-run posting test harness")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    asyncio.run(run_dry_run_test(headless=args.headless))
