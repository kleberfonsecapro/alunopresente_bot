import logging
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from aluno_presente_sme.schemas import ExtractionContract

logger = logging.getLogger(__name__)


class SiteExtractor(ABC):

    site_type: str = ''
    site_label: str = ''
    site_domain: str = ''
    api_base: str = ''
    token_key: str = ''
    login_url: str = ''

    def get_token(self) -> str | None:
        return None

    async def extract_via_api(
        self, url: str, fields: list[ExtractionContract], token: str
    ) -> dict | None:
        return None

    async def extract_via_playwright(
        self, url: str, fields: list[ExtractionContract]
    ) -> dict:
        raise NotImplementedError

    async def relogin(self) -> None:
        raise NotImplementedError

    def matches_url(self, url: str) -> bool:
        if not self.site_domain:
            return False
        try:
            hostname = urlparse(url).hostname or ''
            parts = hostname.split('.')
            return self.site_domain in parts
        except Exception:
            return False

    def _is_login_page(self, url: str) -> bool:
        """Detecta se a URL atual é a tela de login (sessão não autenticada)."""
        if not self.login_url:
            return False
        try:
            login_path = urlparse(self.login_url).path or '/login'
            current_path = urlparse(url).path or '/'
            return 'login' in current_path.lower() or (
                current_path.rstrip('/') == login_path.rstrip('/')
            )
        except Exception:
            return False

    async def _new_page(self, browser, url: str):
        """Abre uma página com o storage_state atual, já navegada para `url`."""
        from aluno_presente_sme.skills.auth_skill import get_storage_state

        storage = get_storage_state()
        ctx = await browser.new_context(storage_state=storage or None)
        page = await ctx.new_page()
        await page.goto(url, wait_until='networkidle', timeout=60000)
        return page

    async def _ensure_authenticated_page(self, browser, url: str):
        """Garante uma página autenticada, relogando quando a sessão estiver ausente/expirada.

        Só tenta re-login quando o extrator define `login_url` (sites autenticados).
        Levanta RuntimeError com mensagem clara quando a autenticação falha.
        """
        from aluno_presente_sme.skills.auth_skill import get_storage_state

        if self.login_url and not get_storage_state():
            await self.relogin()

        page = await self._new_page(browser, url)
        if self._is_login_page(page.url):
            logger.warning('Sessão expirada para %s, relogando...', self.site_type)
            await page.context.close()
            await self.relogin()
            page = await self._new_page(browser, url)
            if self._is_login_page(page.url):
                await page.context.close()
                raise RuntimeError(
                    'Re-login automático falhou: a página de login não foi superada'
                )
        return page

    async def _extract_dom_value(self, page, field: ExtractionContract):
        """Extrai o valor de um campo via DOM. Falha de forma clara sem selector."""
        if not field.selector:
            raise RuntimeError(
                f"Campo '{field.field_name}' sem selector não pode ser extraído via "
                'Playwright. Defina um selector na config ou use a extração via API.'
            )
        el = await page.query_selector(field.selector)
        if not el:
            return None
        return await el.inner_text()
