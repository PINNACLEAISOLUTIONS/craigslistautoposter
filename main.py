import argparse
import asyncio
import json
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

from config.settings import load_config
from payload.models import PostPayload, PostAttributes, AccountCredentials
from payload.spintax import SpintaxParser
from payload.exif_scrubber import ExifScrubber
from workers.poster import CraigslistPosterWorker

console = Console()

def get_sample_payload() -> PostPayload:
    return PostPayload(
        id="demo-post-001",
        subdomain="sfbay",
        type_of_post="for sale by owner",
        sub_area="city of san francisco",
        category="electronics - by owner",
        title_spintax="{Brand New|Factory Sealed|Unopened} Apple iPhone 15 Pro - {128GB|256GB} {Blue Titanium|Natural Titanium}",
        body_spintax=(
            "{Hi all|Hello|Greetings},\n\n"
            "Selling a {completely new|pristine condition|sealed} iPhone 15 Pro.\n"
            "{Includes original box and all accessories|Comes with charging cable and box}.\n\n"
            "{Pickup in SOMA / Financial District|Local cash deal only|Can meet anywhere in the city}.\n"
            "Serious buyers only, {please text or email|send a message}.\n\n"
            "Thank you!"
        ),
        price="850",
        postal_code="94103",
        neighborhood="SOMA / Mission",
        attributes=PostAttributes(
            condition="new",
            make_manufacturer="Apple",
            model_name_number="iPhone 15 Pro"
        ),
        images=[]
    )

async def run_post(payload: PostPayload, dry_run: bool = True, config_path: str = None):
    cfg = load_config(config_path)
    worker = CraigslistPosterWorker(cfg)
    
    console.print(f"[bold cyan]Initiating Craigslist Posting Worker (dry_run={dry_run})...[/bold cyan]")
    result = await worker.execute_post(payload, dry_run=dry_run)
    
    table = Table(title="Execution Report")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green" if result.success else "red")
    
    table.add_row("Job ID", result.job_id)
    table.add_row("Success", str(result.success))
    table.add_row("Generated Title", result.generated_title or "N/A")
    table.add_row("Post / Result URL", result.post_url or "N/A")
    if result.error_message:
        table.add_row("Error", result.error_message)
    table.add_row("Timestamp", result.timestamp)
    
    console.print(table)

def main():
    parser = argparse.ArgumentParser(description="Scalable Automated Craigslist Poster")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # test-spin command
    spin_parser = subparsers.add_parser("spin", help="Preview Spintax generation")
    spin_parser.add_argument("--text", type=str, required=True, help="Spintax string to test")
    spin_parser.add_argument("--count", type=int, default=5, help="Number of variations")

    # dry-run command
    dry_parser = subparsers.add_parser("dry-run", help="Simulate posting flow without publishing")
    dry_parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    dry_parser.add_argument("--payload", type=str, default=None, help="Path to JSON payload file")

    # live post command
    post_parser = subparsers.add_parser("post", help="Execute live Craigslist post")
    post_parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    post_parser.add_argument("--payload", type=str, default=None, help="Path to JSON payload file")

    # clean-images command
    img_parser = subparsers.add_parser("clean-images", help="Scrub EXIF and metadata from images")
    img_parser.add_argument("--images", nargs="+", required=True, help="List of image files to scrub")

    args = parser.parse_args()

    if args.command == "spin":
        variations = SpintaxParser.generate_variations(args.text, count=args.count)
        console.print(f"[bold yellow]Generated {len(variations)} Spintax Variations:[/bold yellow]")
        for i, var in enumerate(variations, 1):
            console.print(f"{i}. {var}")

    elif args.command in ("dry-run", "post"):
        if args.payload and Path(args.payload).exists():
            with open(args.payload, "r", encoding="utf-8") as f:
                data = json.load(f)
                payload = PostPayload(**data)
        else:
            payload = get_sample_payload()

        is_dry_run = (args.command == "dry-run")
        asyncio.run(run_post(payload, dry_run=is_dry_run, config_path=args.config))

    elif args.command == "clean-images":
        cleaned = ExifScrubber.clean_batch(args.images)
        console.print(f"[bold green]Cleaned {len(cleaned)} images without EXIF metadata:[/bold green]")
        for path in cleaned:
            console.print(f" -> {path}")

if __name__ == "__main__":
    main()
