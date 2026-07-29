import json
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx

from scraper_bot.schemas import ExtractionContract
from scraper_bot.skills.extractors.base import SiteExtractor
from scraper_bot.skills.extractors.registry import register

logger = logging.getLogger(__name__)

STORAGE_PATH = Path('/app/playwright_state/storage_state.json')
API_BASE = os.environ.get(
    'ESCOLA_SEGURA_API_BASE',
    'https://api.escolasegura.srv.br',
)
TOKEN_KEY = os.environ.get(
    'ESCOLA_SEGURA_TOKEN_KEY',
    'escola-segura-token',
)
LOGIN_URL = os.environ.get(
    'ESCOLA_SEGURA_LOGIN_URL',
    'https://escolasegura.srv.br/login',
)


@register
class EscolaSeguraExtractor(SiteExtractor):
    site_type = 'escola_segura'
    site_label = 'Escola Segura'
    site_domain = 'escolasegura'
    api_base = API_BASE
    token_key = TOKEN_KEY
    login_url = LOGIN_URL

    def get_token(self) -> str | None:
        try:
            state = json.loads(STORAGE_PATH.read_text())
            for origin in state.get('origins', []):
                for ls in origin.get('localStorage', []):
                    if ls['name'] == self.token_key:
                        return ls['value']
        except Exception:
            return None
        return None

    async def extract_via_api(
        self, url: str, fields: list[ExtractionContract], token: str
    ) -> dict:
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        data = await self._fetch_api_data(headers)

        extracted = {}
        for field in fields:
            val = self._safe_get(data, field.field_name)
            extracted[field.field_name] = str(val) if val is not None else None

        return {
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'data': extracted,
        }

    async def _fetch_api_data(self, headers: dict) -> dict:
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            dashboard = await client.get(
                f'{self.api_base}/api/dashboard',
                headers=headers,
            )
            dashboard.raise_for_status()
            raw = dashboard.json()

        return self._normalize_response(raw)

    def _normalize_response(self, raw: dict) -> dict:
        norm = {}
        for key, value in raw.items():
            if isinstance(value, (int, float)):
                norm[key] = self._fmt_int(int(value))
            elif isinstance(value, str):
                norm[key] = value
            elif isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    if isinstance(sub_val, (int, float)):
                        norm[f'{key}_{sub_key}'] = self._fmt_int(int(sub_val))
                    else:
                        norm[f'{key}_{sub_key}'] = str(sub_val) if sub_val is not None else None
            elif isinstance(value, list):
                norm[key] = str(len(value))
            else:
                norm[key] = str(value) if value is not None else None
        return norm

    def _safe_get(self, data: dict, key: str, default=None) -> str | None:
        try:
            val = data[key]
            return str(val) if val is not None else default
        except (KeyError, TypeError):
            return default

    def _fmt_int(self, n: int) -> str:
        return f'{n:,}'.replace(',', '.')

    async def relogin(self) -> None:
        from scraper_bot.skills.auth import AuthenticationSkill
        from scraper_bot.skills.auth_skill import clear_storage_state
        clear_storage_state()
        result = await AuthenticationSkill(headless=True).login(
            self.login_url,
            os.environ.get('ESCOLA_SEGURA_USER', ''),
            os.environ.get('ESCOLA_SEGURA_PASSWORD', ''),
        )
        if not result['success']:
            raise RuntimeError(
                f'Re-login automático Escola Segura falhou: {result["message"]}'
            )
