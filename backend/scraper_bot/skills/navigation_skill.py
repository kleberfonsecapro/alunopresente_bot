from playwright.async_api import async_playwright

from scraper_bot.skills.auth_skill import get_storage_state


class NavigationSkill:

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def navigate(
        self,
        url: str,
        wait_selector: str | None = None,
        scroll_to_bottom: bool = False
    ) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                storage_state=get_storage_state()
            )
            page = await context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)

            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=15000)

            if scroll_to_bottom:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(1000)

            result = {
                'title': await page.title(),
                'current_url': page.url,
                'page_source_snippet': await page.inner_html('body')[:2000]
            }

            await browser.close()
            return result
