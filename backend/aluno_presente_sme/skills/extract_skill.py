import logging

import httpx

from aluno_presente_sme.schemas import ExtractionContract
from aluno_presente_sme.skills.extractors import get_extractor
from aluno_presente_sme.skills.extractors.registry import list_site_types

logger = logging.getLogger(__name__)


class ExtractionSkill:

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def extract(
        self,
        url: str,
        fields: list[ExtractionContract],
        site_type: str | None = None,
        unit_id: int | None = None,
        unit_ids: list[int] | None = None,
        period: str | None = None,
    ) -> dict:
        site_type = site_type or self._detect_site_type(url)
        extractor_cls = get_extractor(site_type)
        extractor = extractor_cls()

        token = extractor.get_token()
        if not token and extractor.login_url:
            try:
                await extractor.relogin()
                token = extractor.get_token()
            except Exception as e:
                logger.warning('Relogin inicial falhou para %s: %s', site_type, e)

        if unit_id and hasattr(extractor, 'extract_single_unit'):
            if token:
                try:
                    return await extractor.extract_single_unit(url, fields, token, unit_id)
                except Exception as e:
                    logger.warning('Extração unitária via API falhou para %s: %s', site_type, e)
            return await extractor.extract_via_playwright(url, fields)

        if token:
            try:
                result = await extractor.extract_via_api(url, fields, token, unit_ids=unit_ids, period=period)
                if result:
                    return result
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.info('Token expirado para %s, relogando...', site_type)
                    try:
                        await extractor.relogin()
                        token = extractor.get_token()
                        if token:
                            result = await extractor.extract_via_api(url, fields, token, unit_ids=unit_ids, period=period)
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