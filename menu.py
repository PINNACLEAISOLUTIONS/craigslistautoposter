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
            "[bold cyan]SILVER ROSE MANAGEMENT — CRAIGSLIST AUTOMATION[/bold cyan]\n"
            "[italic white]Campaign: Recruiting Women & Trans Women Creators[/italic white]",
            border_style="cyan"
        ))

        check_session_status()

        console.print("[bold yellow]Available Actions:[/bold yellow]")
        console.print("  [1] [bold green]Test Dry-Run Preview[/bold green] (Fills form, stops at preview snapshot)")
        console.print("  [2] [bold red]PUBLISH LIVE POST[/bold red] (Publishes ad live to Craigslist)")
        console.print("  [3] [bold cyan]Test Spintax Variations[/bold cyan] (Preview title/body variations)")
        console.print("  [4] [bold yellow]Re-login / Refresh Session[/bold yellow]")
        console.print("  [5] Exit\n")

        choice = input("Enter choice (1-5): ").strip()

        if choice == "1":
            subprocess.run([sys.executable, "post_silver_rose.py"])
            input("\nPress ENTER to return to menu...")
        elif choice == "2":
            confirm = input("\nAre you sure you want to PUBLISH LIVE to Craigslist? (y/n): ").strip().lower()
            if confirm == "y":
                subprocess.run([sys.executable, "post_silver_rose.py", "--publish"])
            input("\nPress ENTER to return to menu...")
        elif choice == "3":
            subprocess.run([sys.executable, "main.py", "spin", "--text", "{Silver Rose Management — Recruiting Women & Trans Women OnlyFans Creators|Silver Rose Management: Seeking Women & Trans Women OnlyFans Creators|Creator Management Agency — Recruiting Women & Trans Women (OnlyFans)}", "--count", "4"])
            input("\nPress ENTER to return to menu...")
        elif choice == "4":
            subprocess.run([sys.executable, "login.py"])
            input("\nPress ENTER to return to menu...")
        elif choice == "5":
            console.print("[green]Goodbye![/green]")
            break

if __name__ == "__main__":
    main()
