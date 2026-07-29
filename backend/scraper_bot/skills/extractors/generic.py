import logging

from playwright.async_api import async_playwright

from scraper_bot.schemas import ExtractionContract
from scraper_bot.skills.auth_skill import get_storage_state
from scraper_bot.skills.extractors.base import SiteExtractor
from scraper_bot.skills.extractors.registry import register

logger = logging.getLogger(__name__)


@register
class GenericExtractor(SiteExtractor):
    site_type = 'generic'
    site_label = 'Genérico (Playwright)'
    site_domain = ''
    api_base = ''
    token_key = ''
    login_url = ''

    async def extract_via_playwright(
        self, url: str, fields: list[ExtractionContract]
    ) -> dict:
        extracted = {}
        storage = get_storage_state()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(storage_state=storage or None)
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until='networkidle', timeout=60000)

                for field in fields:
                    try:
                        if field.selector:
                            el = await page.query_selector(field.selector)
                            if el:
                                extracted[field.field_name] = await el.inner_text()
                            else:
                                extracted[field.field_name] = None
                        else:
                            extracted[field.field_name] = page.url
                    except Exception as e:
                        logger.warning(
                            'Falha ao extrair campo %s: %s', field.field_name, e
                        )
                        extracted[field.field_name] = None
            finally:
                await browser.close()

        from datetime import datetime
        return {
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'data': extracted,
        }
