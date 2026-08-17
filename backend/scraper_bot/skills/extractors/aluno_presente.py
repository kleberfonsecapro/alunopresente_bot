import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import httpx

from scraper_bot.schemas import ExtractionContract
from scraper_bot.skills.extractors.base import SiteExtractor
from scraper_bot.skills.extractors.registry import register

logger = logging.getLogger(__name__)

STORAGE_PATH = Path('/app/playwright_state/storage_state.json')
API_BASE = 'https://cba.alunopresente.srv.br'


@register
class AlunoPresenteExtractor(SiteExtractor):
    site_type = 'aluno_presente'
    site_label = 'Aluno Presente'
    site_domain = 'alunopresente'
    api_base = API_BASE
    token_key = 'aluno-presente-token'
    login_url = 'https://cba.alunopresente.srv.br/login'

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

    async def list_school_units(self, token: str) -> list[dict]:
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            r = await client.get(
                API_BASE + '/api/dashboard-secretario/unidades/todas',
                headers=headers,
            )
            r.raise_for_status()
            return r.json()

    async def extract_single_unit(
        self, url: str, fields: list[ExtractionContract], token: str, unit_id: int
    ) -> dict:
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        today = datetime.now().strftime('%Y-%m-%d')
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            r = await client.get(
                API_BASE + f'/api/dashboard-secretario/buscar-lista-unidades-escolares?data={today}&condicao=ATIVO&page=0&size=1000',
                headers=headers,
            )
            r.raise_for_status()
            unit_list = r.json().get('content', [])

        unit = next((u for u in unit_list if u['unidade_id'] == unit_id), None)
        if not unit:
            raise ValueError(f'Unidade escolar com ID {unit_id} não encontrada ou inativa')

        def fmt_int(n: int) -> str:
            return f'{n:,}'.replace(',', '.')

        def fmt_pct(n: float) -> str:
            return f'{n:.1f}'.replace('.', ',')

        ausentes = unit['expectativaPresenca'] - unit['alunos_presentes']
        nao_alimentados = unit['alunos_presentes'] - unit['alunos_alimentados']

        data = {
            'unidade_id': str(unit['unidade_id']),
            'unidade_nome': unit['unidade_nome'],
            'regiao': unit.get('regiao', ''),
            'inep': unit.get('inep', ''),
            'total_alunos': fmt_int(unit['total_alunos']),
            'presentes': fmt_int(unit['alunos_presentes']),
            'ausentes': fmt_int(ausentes),
            'presentes_pct': fmt_pct(unit['percentual_presenca']),
            'ausentes_pct': fmt_pct(100 - unit['percentual_presenca']) if unit['expectativaPresenca'] else '0,0',
            'alimentados': fmt_int(unit['alunos_alimentados']),
            'nao_alimentados': fmt_int(nao_alimentados),
            'alimentados_pct': fmt_pct(unit['percentual_alimentados']),
            'nao_alimentados_pct': fmt_pct(100 - unit['percentual_alimentados']) if unit['alunos_presentes'] else '0,0',
            'com_foto': fmt_int(unit['alunos_com_foto']),
            'sem_foto': fmt_int(unit['alunos_sem_foto']),
            'com_foto_pct': fmt_pct(unit['alunos_com_foto'] / unit['total_alunos'] * 100) if unit['total_alunos'] else '0,0',
            'sem_foto_pct': fmt_pct(unit['alunos_sem_foto'] / unit['total_alunos'] * 100) if unit['total_alunos'] else '0,0',
        }

        meta_fields = {'unidade_id', 'unidade_nome', 'inep', 'regiao'}
        extracted = {}
        for field in fields:
            val = data.get(field.field_name)
            extracted[field.field_name] = str(val) if val is not None else None
        for meta in meta_fields:
            if meta not in extracted:
                val = data.get(meta)
                extracted[meta] = str(val) if val is not None else None

        return {
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'data': extracted,
        }

    async def extract_via_api(
        self, url: str, fields: list[ExtractionContract], token: str,
        unit_ids: list[int] | None = None,
        period: str | None = None,
    ) -> dict:
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        data = await self._fetch_api_data(headers, unit_ids=unit_ids, period=period)

        extracted = {}
        for field in fields:
            val = data.get(field.field_name)
            extracted[field.field_name] = str(val) if val is not None else None

        return {
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'data': extracted,
        }

    async def _fetch_api_data(self, headers: dict, unit_ids: list[int] | None = None, period: str | None = None) -> dict:
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

        if unit_ids:
            unit_list = [u for u in unit_list if u['unidade_id'] in unit_ids]

        if period:
            from scraper_bot.models import UnitPeriod
            period_unit_ids = set(
                UnitPeriod.objects.filter(period=period).values_list('unit_id', flat=True)
            )
            unit_list = [u for u in unit_list if u['unidade_id'] in period_unit_ids]

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
            return f'{n:.1f}'.replace('.', ',')

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
        }

        if not unit_ids:
            data['total_unidades'] = fmt_int(cards['totalUnidadesEscolares']) if cards.get('totalUnidadesEscolares') else None
            data['total_turmas'] = fmt_int(cards['totalTurmas']) if cards.get('totalTurmas') else None
            data['alunos_com_foto'] = fmt_int(cards['totalAlunosComFoto']) if cards.get('totalAlunosComFoto') else None
            data['alunos_especiais'] = fmt_int(cards['totalAlunosEspeciais']) if cards.get('totalAlunosEspeciais') else None
            data['unidades_ativas'] = fmt_int(subcards['unidadesAtivas']) if subcards.get('unidadesAtivas') else None
            data['alunos_matutinos'] = fmt_int(subcards['totalAlunosMatutinos']) if subcards.get('totalAlunosMatutinos') else None
            data['alunos_vespertinos'] = fmt_int(subcards['totalAlunosVespertinos']) if subcards.get('totalAlunosVespertinos') else None
            data['alunos_integral'] = fmt_int(subcards['totalAlunosIntegral']) if subcards.get('totalAlunosIntegral') else None

            sorted_units = sorted(
                unit_list, key=lambda u: u.get('alunos_presentes', 0), reverse=True
            )[:10]
            for i, u in enumerate(sorted_units, 1):
                data[f'top{i}_nome'] = u['unidade_nome']
                data[f'top{i}_presentes'] = fmt_int(u['alunos_presentes'])
                data[f'top{i}_pct'] = fmt_pct(u['percentual_presenca'])

        return data

    async def relogin(self) -> None:
        from scraper_bot.skills.auth import AuthenticationSkill
        from scraper_bot.skills.auth_skill import clear_storage_state
        import os
        clear_storage_state()
        result = await AuthenticationSkill(headless=True).login(
            self.login_url,
            os.environ.get('TARGET_SITE_USER', ''),
            os.environ.get('TARGET_SITE_PASSWORD', ''),
        )
        if not result['success']:
            raise RuntimeError(f'Re-login automático falhou: {result["message"]}')

    async def extract_via_playwright(
        self, url: str, fields: list[ExtractionContract]
    ) -> dict:
        extracted = {}
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await self._ensure_authenticated_page(browser, url)
                try:
                    for field in fields:
                        extracted[field.field_name] = await self._extract_dom_value(
                            page, field
                        )
                finally:
                    await page.context.close()
            finally:
                await browser.close()

        return {
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'data': extracted,
        }
