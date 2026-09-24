import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def check_session_status():
    sessions = list((Path("data") / "sessions").glob("*_state.json"))
    table = Table(title="Local Authentication Status")
    table.add_column("Account Label", style="cyan")
    table.add_column("Session File", style="magenta")
    table.add_column("Status", style="green" if sessions else "yellow")

    if sessions:
        for s in sessions:
            table.add_row(s.stem.replace("_state", ""), s.name, "Active & Ready")
    else:
        table.add_row("None", "No saved sessions found", "Needs 1-time Login")

    console.print(table)
    console.print()

def main():
    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]CRAIGSLIST AUTOMATION CONTROL PANEL[/bold cyan]\n"
            "[italic white]Safe local testing, session management, and preview verification[/italic white]",
            border_style="cyan"
        ))

        check_session_status()

        console.print("[bold yellow]Available Actions:[/bold yellow]")
        console.print("  [1] [bold green]Save / Refresh Login Session[/bold green] (One-time browser login)")
        console.print("  [2] [bold cyan]Run Dry-Run Preview Test[/bold cyan] (Fills form & captures snapshot)")
        console.print("  [3] [bold magenta]Test Spintax Generation[/bold magenta] (Preview dynamic title & body variations)")
        console.print("  [4] [bold red]Exit[/bold red]\n")

        choice = input("Enter choice (1-4): ").strip()

        if choice == "1":
            subprocess.run([sys.executable, "save_session.py"])
            input("\nPress ENTER to return to menu...")
        elif choice == "2":
            subprocess.run([sys.executable, "dry_run_harness.py"])
            input("\nPress ENTER to return to menu...")
        elif choice == "3":
            subprocess.run([sys.executable, "main.py", "spin", "--text", "{Silver Rose Management — Recruiting Creators|Creator Management Agency — Seeking Creators}", "--count", "4"])
            input("\nPress ENTER to return to menu...")
        elif choice == "4":
            console.print("[green]Goodbye![/green]")
            break

if __name__ == "__main__":
    main()
