import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from scraper_bot.schemas import ExtractionContract
from scraper_bot.skills.auth_skill import get_storage_state

STORAGE_PATH = Path('/app/playwright_state/storage_state.json')
API_BASE = 'https://cba.alunopresente.srv.br'


class ExtractionSkill:

    def __init__(self, headless: bool = True):
        self.headless = headless

    def _get_token(self) -> str | None:
        try:
            state = json.loads(STORAGE_PATH.read_text())
            for origin in state.get('origins', []):
                for ls in origin.get('localStorage', []):
                    if ls['name'] == 'aluno-presente-token':
                        return ls['value']
        except Exception:
            return None
        return None

    async def extract(
        self,
        url: str,
        fields: list[ExtractionContract]
    ) -> dict:
        token = self._get_token()

        if token and 'alunopresente' in url:
            try:
                return await self._extract_via_api(url, fields, token)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    await self._relogin()
                    token = self._get_token()
                    if token:
                        return await self._extract_via_api(url, fields, token)
                raise

        if 'alunopresente' in url:
            await self._relogin()
            token = self._get_token()
            if token:
                return await self._extract_via_api(url, fields, token)

        return await self._extract_via_playwright(url, fields)

    async def _relogin(self):
        from scraper_bot.skills.auth import AuthenticationSkill
        from scraper_bot.skills.auth_skill import clear_storage_state
        import os
        clear_storage_state()
        url = os.environ.get('TARGET_SITE_URL', 'https://cba.alunopresente.srv.br/login')
        username = os.environ.get('TARGET_SITE_USER', '')
        password = os.environ.get('TARGET_SITE_PASSWORD', '')
        result = await AuthenticationSkill(headless=True).login(url, username, password)
        if not result['success']:
            raise RuntimeError(f'Re-login automático falhou: {result["message"]}')

    async def _fetch_api_data(self, headers: dict) -> dict:
        today = datetime.now().strftime('%Y-%m-%d')
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            r1, r2, r3 = await asyncio.gather(
                client.get(
                    API_BASE + '/api/dashboard-secretario/buscar-dados-cards-principais',
                    headers=headers,
                ),
                client.get(
                    API_BASE + '/api/dashboard-secretario/buscar-dados-subcards',
                    headers=headers,
                ),
                client.get(
                    API_BASE + f'/api/dashboard-secretario/buscar-lista-unidades-escolares?data={today}&condicao=ATIVO&page=0&size=1000',
                    headers=headers,
                ),
            )
            for r in (r1, r2, r3):
                r.raise_for_status()
            cards = r1.json()
            subcards = r2.json()
            unit_list = r3.json().get('content', [])

        total_alunos = sum(u['total_alunos'] for u in unit_list) if unit_list else 0
        total_presentes = sum(u['alunos_presentes'] for u in unit_list) if unit_list else 0
        total_esperados = sum(u['expectativaPresenca'] for u in unit_list) if unit_list else 0
        total_alimentados = sum(u['alunos_alimentados'] for u in unit_list) if unit_list else 0
        total_com_foto = sum(u['alunos_com_foto'] for u in unit_list) if unit_list else 0

        ausentes = total_esperados - total_presentes
        nao_alimentados = total_presentes - total_alimentados
        sem_foto = total_alunos - total_com_foto

        def fmt_int(n: int) -> str:
            return f'{n:,}'.replace(',', '.')

        def fmt_pct(n: float) -> str:
            s = f'{n:.1f}'.replace('.', ',')
            return s

        data = {
            'presentes': fmt_int(total_presentes),
            'ausentes': fmt_int(ausentes),
            'presentes_pct': fmt_pct(total_presentes / total_esperados * 100) if total_esperados else '0,0',
            'ausentes_pct': fmt_pct(ausentes / total_esperados * 100) if total_esperados else '0,0',
            'alimentados': fmt_int(total_alimentados),
            'nao_alimentados': fmt_int(nao_alimentados),
            'alimentados_pct': fmt_pct(total_alimentados / total_presentes * 100) if total_presentes else '0,0',
            'nao_alimentados_pct': fmt_pct(nao_alimentados / total_presentes * 100) if total_presentes else '0,0',
            'com_foto': fmt_int(total_com_foto),
            'sem_foto': fmt_int(sem_foto),
            'com_foto_pct': fmt_pct(total_com_foto / total_alunos * 100) if total_alunos else '0,0',
            'sem_foto_pct': fmt_pct(sem_foto / total_alunos * 100) if total_alunos else '0,0',
            'total_unidades': fmt_int(cards['totalUnidadesEscolares']) if cards.get('totalUnidadesEscolares') else None,
            'total_turmas': fmt_int(cards['totalTurmas']) if cards.get('totalTurmas') else None,
            'alunos_com_foto': fmt_int(cards['totalAlunosComFoto']) if cards.get('totalAlunosComFoto') else None,
            'alunos_especiais': fmt_int(cards['totalAlunosEspeciais']) if cards.get('totalAlunosEspeciais') else None,
            'unidades_ativas': fmt_int(subcards['unidadesAtivas']) if subcards.get('unidadesAtivas') else None,
            'alunos_matutinos': fmt_int(subcards['totalAlunosMatutinos']) if subcards.get('totalAlunosMatutinos') else None,
            'alunos_vespertinos': fmt_int(subcards['totalAlunosVespertinos']) if subcards.get('totalAlunosVespertinos') else None,
            'alunos_integral': fmt_int(subcards['totalAlunosIntegral']) if subcards.get('totalAlunosIntegral') else None,
        }

        sorted_units = sorted(
            unit_list, key=lambda u: u.get('alunos_presentes', 0), reverse=True
        )[:10]
        for i, u in enumerate(sorted_units, 1):
            data[f'top{i}_nome'] = u['unidade_nome']
            data[f'top{i}_presentes'] = fmt_int(u['alunos_presentes'])
            data[f'top{i}_pct'] = fmt_pct(u['percentual_presenca'])

        return data

    async def _extract_via_api(
        self, url: str, fields: list[ExtractionContract], token: str
    ) -> dict:
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        data = await self._fetch_api_data(headers)

        extracted = {}
        for field in fields:
            val = data.get(field.field_name)
            extracted[field.field_name] = str(val) if val is not None else None

        return {
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'data': extracted,
        }

    async def _extract_via_playwright(
        self, url: str, fields: list[ExtractionContract], retries: int = 2
    ) -> dict:
        last_error = None
        for attempt in range(1 + retries):
            try:
                return await self._playwright_extract(url, fields)
            except Exception as e:
                last_error = e
                from scraper_bot.skills.auth_skill import clear_storage_state
                clear_storage_state()
                if attempt < retries and 'alunopresente' in url:
                    await self._relogin()
                else:
                    break
        raise last_error  # type: ignore

    async def _playwright_extract(
        self, url: str, fields: list[ExtractionContract]
    ) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                storage_state=get_storage_state()
            )
            page = await context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(8000)

            extracted = {}
            for field in fields:
                try:
                    if field.selector:
                        element = page.locator(field.selector).first
                        text = await element.text_content()
                        extracted[field.field_name] = text.strip() if text else None
                    else:
                        extracted[field.field_name] = field.value
                except Exception:
                    extracted[field.field_name] = None

            result = {
                'url': url,
                'extracted_at': datetime.now().isoformat(),
                'data': extracted
            }

            await browser.close()
            return result
