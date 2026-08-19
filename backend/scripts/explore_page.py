import asyncio
from playwright.async_api import async_playwright
from aluno_presente_sme.skills.auth_skill import get_storage_state

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=get_storage_state())
        page = await context.new_page()
        
        await page.goto('https://cba.alunopresente.srv.br/alunopresente/dashboard-secretario', timeout=30000)
        await page.wait_for_timeout(10000)
        
        # Get all card-like elements
        cards = await page.query_selector_all('[class*="card"], [class*="Card"], .stat, [class*="stat"], [class*="Stat"], [class*="box"], [class*="Box"], [class*="kpi"], [class*="KPI"]')
        print(f"Cards found: {len(cards)}")
        
        for i, card in enumerate(cards):
            html = await card.inner_html()
            text = await card.inner_text()
            print(f"\n--- Card {i} ---")
            print(f"HTML: {html[:200]}")
            print(f"TEXT: {text.strip()[:100]}")
        
        if not cards:
            # Try to find elements with numbers and labels
            print("\nNo cards found. Looking for elements with numbers...")
            all_els = await page.query_selector_all('*')
            for el in all_els:
                tag = await el.evaluate('el => el.tagName')
                text = await el.inner_text()
                text = text.strip()
                if text and any(c.isdigit() for c in text) and len(text) < 200:
                    # Check parent for card-like class
                    parent_classes = await el.evaluate('el => el.parentElement ? el.parentElement.className : ""')
                    if 'card' in parent_classes.lower() or 'stat' in parent_classes.lower() or 'box' in parent_classes.lower() or 'kpi' in parent_classes.lower():
                        print(f"  {tag}: {text[:80]} [parent: {parent_classes[:60]}]")
        
        await browser.close()

asyncio.run(main())
