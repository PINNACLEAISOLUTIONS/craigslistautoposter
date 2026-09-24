import asyncio
from pathlib import Path
from rich.console import Console
from playwright.async_api import async_playwright

console = Console()

async def record_login_session(account_id: str = "primary_account"):
    """
    Opens a visible browser for the user to log in manually,
    then captures and saves cookies and storage state to disk.
    """
    sessions_dir = Path("data") / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / f"{account_id}_state.json"

    console.print(f"\n[bold cyan]Starting session capture for account: {account_id}[/bold cyan]")
    console.print("[yellow]A browser window will open to the Craigslist login page.[/yellow]")
    console.print("[yellow]Log in manually. Once you see your account dashboard/homepage, return here and press ENTER.[/yellow]\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US"
        )
        page = await context.new_page()

        await page.goto("https://accounts.craigslist.org/login", wait_until="domcontentloaded")

        # Wait for user confirmation in terminal
        await asyncio.to_thread(input, ">> Press ENTER once you have logged in and reached the account dashboard: ")

        # Save session state (cookies, auth tokens, localStorage)
        await context.storage_state(path=str(session_file))
        console.print(f"\n[bold green]Success! Authenticated session saved to {session_file}[/bold green]")
        console.print("[cyan]Future runs will now launch already authenticated as this user.[/cyan]\n")

        await browser.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Save authenticated Craigslist session state")
    parser.add_argument("--account", type=str, default="primary_account", help="Account identifier label")
    args = parser.parse_args()

    asyncio.run(record_login_session(account_id=args.account))
