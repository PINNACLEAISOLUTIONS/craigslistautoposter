import asyncio
import os
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from dotenv import load_dotenv
from playwright.async_api import async_playwright

console = Console()

async def record_login_session(account_id: str = "primary_account", email_choice: str = None):
    """
    Opens an interactive browser window to Craigslist login, pre-fills your email,
    waits for you to authenticate, and automatically saves session cookies for all future runs.
    """
    load_dotenv()
    sessions_dir = Path("data") / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / f"{account_id}_state.json"

    # Resolve email from .env if not specified
    if not email_choice:
        email_1 = os.getenv("CL_ACCOUNT_1_EMAIL", "christopher.concannon94@gmail.com")
        email_2 = os.getenv("CL_ACCOUNT_2_EMAIL", "chrisconcannon@protonmail.com")
        
        console.print("\n[bold cyan]Select email for Craigslist login session:[/bold cyan]")
        console.print(f"  [1] ProtonMail: [yellow]{email_2}[/yellow]")
        console.print(f"  [2] Gmail:      [yellow]{email_1}[/yellow]")
        choice = Prompt.ask("Choose option", choices=["1", "2"], default="1")
        target_email = email_2 if choice == "1" else email_1
    else:
        target_email = email_choice

    console.print(f"\n[bold green]Launching browser for:[/bold green] [cyan]{target_email}[/cyan]")
    console.print("[yellow]1. The browser window will open and pre-fill your email address.[/yellow]")
    console.print("[yellow]2. Enter your password and complete any verification code that appears.[/yellow]")
    console.print("[yellow]3. The script will automatically detect when you are logged in, or you can press ENTER here.[/yellow]\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 820},
            locale="en-US"
        )
        page = await context.new_page()

        await page.goto("https://accounts.craigslist.org/login", wait_until="domcontentloaded")
        await asyncio.sleep(1.0)

        # Pre-fill email address if the input is present
        email_input = await page.query_selector("input#inputEmailHandle, input[name='inputEmailHandle']")
        if email_input:
            await email_input.fill(target_email)
            # Focus on password field for immediate convenience
            pw_input = await page.query_selector("input#inputPassword, input[name='inputPassword']")
            if pw_input:
                await pw_input.focus()

        # Monitor login URL progression concurrently with terminal input
        async def wait_for_dashboard():
            while True:
                url = page.url
                if "/login/home" in url or "/cpo" in url or "postings" in url.lower():
                    # Double-check page has logged in content
                    content = (await page.content()).lower()
                    if "log out" in content or "account" in content or "active postings" in content:
                        return True
                await asyncio.sleep(1.5)

        wait_task = asyncio.create_task(wait_for_dashboard())
        input_task = asyncio.create_task(asyncio.to_thread(input, ">> Press ENTER once you are logged into your account dashboard: "))

        done, pending = await asyncio.wait(
            [wait_task, input_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()

        await asyncio.sleep(1.0)

        # Save authenticated storage state
        await context.storage_state(path=str(session_file))
        console.print(f"\n[bold green]SUCCESS: Authenticated session saved to {session_file}![/bold green]")
        console.print("[cyan]The system will now automatically run as this logged-in account on every run.[/cyan]\n")

        await browser.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Save authenticated Craigslist session state")
    parser.add_argument("--account", type=str, default="primary_account", help="Account identifier label")
    parser.add_argument("--email", type=str, default=None, help="Email address to pre-fill")
    args = parser.parse_args()

    asyncio.run(record_login_session(account_id=args.account, email_choice=args.email))
