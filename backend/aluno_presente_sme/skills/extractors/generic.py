import logging
from datetime import datetime

from playwright.async_api import async_playwright

from aluno_presente_sme.schemas import ExtractionContract
from aluno_presente_sme.skills.extractors.base import SiteExtractor
from aluno_presente_sme.skills.extractors.registry import register

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
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await self._ensure_authenticated_page(browser, url)
                try:
                    for field in fields:
                        try:
                            extracted[field.field_name] = await self._extract_dom_value(
                                page, field
                            )
                        except Exception as e:
                            logger.warning(
                                'Falha ao extrair campo %s: %s', field.field_name, e
                            )
                            extracted[field.field_name] = None
                finally:
                    await page.context.close()
            finally:
                await browser.close()

        return {
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'data': extracted,
        }
