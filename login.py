import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    b = await p.chromium.launch(headless=False)
    ctx = await b.new_context()
    page = await ctx.new_page()
    await page.goto("https://accounts.craigslist.org/login")
    print("\n" + "="*50)
    print(">>> BROWSER OPENED: Please log in to your Craigslist account <<<")
    print("="*50 + "\n")
    input("Press [ENTER] here in PowerShell once you are logged in to save session...")
    
    sessions_dir = Path("data/sessions")
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / "default_state.json"
    await ctx.storage_state(path=str(session_file))
    print(f"\n[SUCCESS] Session saved to {session_file}!\n")
    await b.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(main())
