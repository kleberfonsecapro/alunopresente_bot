import asyncio
import json
import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from aluno_presente_sme.models import UnitPeriod
from aluno_presente_sme.skills.auth_skill import get_storage_state

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sincroniza períodos das unidades escolares via API (POST /api/turmas/filtrar)'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando sincronização de períodos...')
        try:
            mapping = asyncio.run(self._fetch_periods())
            result = self._save_periods(mapping)
            self.stdout.write(self.style.SUCCESS(
                f'Sincronização concluída: {result["created"]} registros criados, '
                f'{result["updated"]} atualizados, {result["units"]} unidades'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro na sincronização: {e}'))
            raise

    async def _fetch_periods(self) -> list:
        from playwright.async_api import async_playwright

        storage = get_storage_state()
        if not storage:
            raise RuntimeError('Sessão do Playwright não encontrada. Faça login primeiro.')

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(storage_state=storage)
                page = await ctx.new_page()

                await page.goto(
                    'https://cba.alunopresente.srv.br/',
                    wait_until='networkidle', timeout=30000,
                )
                await asyncio.sleep(1)

                mapping = await page.evaluate('''async () => {
                    const token = localStorage.getItem('aluno-presente-token');
                    const headers = {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    };

                    const firstResp = await fetch('/api/turmas/filtrar?pagina=0', {
                        method: 'POST', headers: headers, body: JSON.stringify({})
                    });
                    const firstData = await firstResp.json();
                    const totalPages = firstData.totalPaginas || 1;

                    const unitPeriods = {};

                    for (const t of (firstData.registros || [])) {
                        const uid = t.matriz?.unidadeEscolar?.id;
                        const uname = t.matriz?.unidadeEscolar?.nome || '?';
                        const pname = t.periodo?.nome || '';
                        if (uid && pname) {
                            const key = uid + '|' + pname;
                            if (!unitPeriods[key]) unitPeriods[key] = [uid, uname, pname];
                        }
                    }

                    for (let start = 1; start < totalPages; start += 5) {
                        const batch = [];
                        for (let i = start; i < Math.min(start + 5, totalPages); i++) {
                            batch.push(fetch('/api/turmas/filtrar?pagina=' + i, {
                                method: 'POST', headers: headers, body: JSON.stringify({})
                            }));
                        }
                        const responses = await Promise.all(batch);
                        for (const resp of responses) {
                            if (!resp.ok) continue;
                            const data = await resp.json();
                            for (const t of (data.registros || [])) {
                                const uid = t.matriz?.unidadeEscolar?.id;
                                const uname = t.matriz?.unidadeEscolar?.nome || '?';
                                const pname = t.periodo?.nome || '';
                                if (uid && pname) {
                                    const key = uid + '|' + pname;
                                    if (!unitPeriods[key]) unitPeriods[key] = [uid, uname, pname];
                                }
                            }
                        }
                    }

                    return Object.values(unitPeriods);
                }''')

                await ctx.close()
            finally:
                await browser.close()

        return mapping

    def _save_periods(self, mapping: list) -> dict:
        created = 0
        updated = 0
        unit_ids = set()

        with transaction.atomic():
            UnitPeriod.objects.all().delete()

            for unit_id, unit_name, period in mapping:
                _, was_created = UnitPeriod.objects.update_or_create(
                    unit_id=unit_id,
                    period=period,
                    defaults={'unit_name': unit_name},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
                unit_ids.add(unit_id)

        return {
            'created': created,
            'updated': updated,
            'units': len(unit_ids),
        }
