import asyncio

from django.test import TestCase

from aluno_presente_sme.models import BotConfig, MessageTemplate
from aluno_presente_sme.schemas import ExtractionContract
from aluno_presente_sme.services import BotOrchestrator


class ExtractWithRetryTest(TestCase):
    def setUp(self):
        self.template = MessageTemplate.objects.create(name='tpl', body='{{presentes}}')
        self.config = BotConfig.objects.create(
            name='cfg',
            target_url='https://example.com',
            site_type='generic',
            extraction_fields=['presentes'],
            send_times=['09:00'],
            template=self.template,
            is_active=True,
        )

    def test_retry_recupera_apos_falha_transitoria(self):
        calls = {'n': 0}

        async def flaky(url, fields, site_type, unit_id=None, unit_ids=None, period=None):
            calls['n'] += 1
            if calls['n'] == 1:
                raise TimeoutError('dns fail transitorio')
            return {'url': url, 'data': {'presentes': '100'}}

        orch = BotOrchestrator(max_retries=3, retry_backoff_sec=0)
        orch.extraction.extract = flaky

        result = asyncio.run(orch._extract_with_retry(
            self.config, [ExtractionContract(field_name='presentes')],
        ))

        self.assertEqual(result['data']['presentes'], '100')
        self.assertEqual(calls['n'], 2)

    def test_falha_total_apos_todas_as_tentativas(self):
        async def always_fails(url, fields, site_type, unit_id=None, unit_ids=None, period=None):
            raise TimeoutError('dns fail persistente')

        orch = BotOrchestrator(max_retries=2, retry_backoff_sec=0)
        orch.extraction.extract = always_fails

        with self.assertRaises(TimeoutError):
            asyncio.run(orch._extract_with_retry(
                self.config, [ExtractionContract(field_name='x')],
            ))

    def test_max_retries_nunca_menor_que_um(self):
        orch = BotOrchestrator(max_retries=0)
        self.assertEqual(orch.max_retries, 1)

    def test_sem_tentativas_levanta_erro_claro(self):
        async def flaky(url, fields, site_type, unit_id=None, unit_ids=None, period=None):
            raise TimeoutError('boom')

        orch = BotOrchestrator(max_retries=1, retry_backoff_sec=0)
        orch.extraction.extract = flaky

        with self.assertRaises(TimeoutError):
            asyncio.run(orch._extract_with_retry(
                self.config, [ExtractionContract(field_name='x')],
            ))
