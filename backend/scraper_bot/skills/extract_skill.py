import logging

import httpx

from scraper_bot.schemas import ExtractionContract
from scraper_bot.skills.extractors import get_extractor
from scraper_bot.skills.extractors.registry import list_site_types

logger = logging.getLogger(__name__)


class ExtractionSkill:

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def extract(
        self,
        url: str,
        fields: list[ExtractionContract],
        site_type: str | None = None,
    ) -> dict:
        site_type = site_type or self._detect_site_type(url)
        extractor_cls = get_extractor(site_type)
        extractor = extractor_cls()

        token = extractor.get_token()

        if token:
            try:
                result = await extractor.extract_via_api(url, fields, token)
                if result:
                    return result
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.info('Token expirado para %s, relogando...', site_type)
                    try:
                        await extractor.relogin()
                        token = extractor.get_token()
                        if token:
                            result = await extractor.extract_via_api(url, fields, token)
                            if result:
                                return result
                    except Exception as relogin_error:
                        logger.warning('Relogin falhou para %s: %s', site_type, relogin_error)
                else:
                    logger.warning('Erro HTTP na extração via API: %s', e)
            except Exception as e:
                logger.warning('Erro inesperado na extração via API: %s', e)

        return await extractor.extract_via_playwright(url, fields)

    def _detect_site_type(self, url: str) -> str:
        if 'alunopresente' in url:
            return 'aluno_presente'
        return 'generic'