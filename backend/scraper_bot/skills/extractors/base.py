from abc import ABC, abstractmethod

from scraper_bot.schemas import ExtractionContract


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
