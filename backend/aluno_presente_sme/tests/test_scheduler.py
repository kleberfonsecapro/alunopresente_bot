from unittest.mock import patch

from django.test import TestCase

from aluno_presente_sme import scheduler as sched_mod
from aluno_presente_sme.models import BotConfig, ExecutionLog, MessageTemplate
from aluno_presente_sme.schemas import BotExecutionOutput, MessageOutput


class SchedulerSyncTest(TestCase):
    def setUp(self):
        self.template = MessageTemplate.objects.create(name='tpl', body='{{presentes}}')
        self.active = BotConfig.objects.create(
            name='Ativa',
            target_url='https://example.com',
            site_type='generic',
            extraction_fields=['presentes'],
            send_times=['09:00'],
            template=self.template,
            is_active=True,
        )
        self.inactive = BotConfig.objects.create(
            name='Inativa',
            target_url='https://example.com',
            site_type='generic',
            extraction_fields=['presentes'],
            send_times=['10:00'],
            template=self.template,
            is_active=False,
        )

    def test_sync_cria_job_para_config_ativa(self):
        sched_mod._last_signature = None
        scheduler = sched_mod.get_scheduler()
        self.assertTrue(sched_mod.sync_jobs_from_db())
        job_ids = [j.id for j in scheduler.get_jobs()]
        self.assertIn(f'botconfig_{self.active.id}_0900', job_ids)

    def test_sync_nao_cria_job_para_config_inativa(self):
        sched_mod._last_signature = None
        scheduler = sched_mod.get_scheduler()
        sched_mod.sync_jobs_from_db()
        job_ids = [j.id for j in scheduler.get_jobs()]
        self.assertNotIn(f'botconfig_{self.inactive.id}_1000', job_ids)

    def test_sync_remove_job_de_horario_antigo(self):
        sched_mod._last_signature = None
        scheduler = sched_mod.get_scheduler()
        sched_mod.sync_jobs_from_db()

        self.active.send_times = ['15:00']
        self.active.save()

        self.assertTrue(sched_mod.sync_jobs_from_db())
        job_ids = [j.id for j in scheduler.get_jobs()]
        self.assertIn(f'botconfig_{self.active.id}_1500', job_ids)
        self.assertNotIn(f'botconfig_{self.active.id}_0900', job_ids)

    def test_sync_noop_quando_nada_muda(self):
        sched_mod._last_signature = None
        sched_mod.sync_jobs_from_db()
        self.assertFalse(sched_mod.sync_jobs_from_db())

    def test_remove_jobs_de_config_desativada(self):
        sched_mod._last_signature = None
        scheduler = sched_mod.get_scheduler()
        sched_mod.sync_jobs_from_db()

        self.active.is_active = False
        self.active.save()

        self.assertTrue(sched_mod.sync_jobs_from_db())
        job_ids = [j.id for j in scheduler.get_jobs()]
        self.assertNotIn(f'botconfig_{self.active.id}_0900', job_ids)


class SchedulerFailureTest(TestCase):
    def setUp(self):
        self.template = MessageTemplate.objects.create(name='tpl', body='{{presentes}}')
        self.config = BotConfig.objects.create(
            name='Config',
            target_url='https://example.com',
            site_type='generic',
            extraction_fields=['presentes'],
            send_times=['09:00'],
            template=self.template,
            is_active=True,
        )

    def test_execute_sem_template_registra_falha_e_notifica(self):
        no_template = BotConfig.objects.create(
            name='SemTemplate',
            target_url='https://example.com',
            site_type='generic',
            extraction_fields=['presentes'],
            send_times=['09:00'],
            template=None,
            is_active=True,
        )
        with patch('aluno_presente_sme.scheduler._notify_failure') as mock_notify:
            sched_mod.execute_scheduled_job(no_template.id)
        mock_notify.assert_called_once()
        log = ExecutionLog.objects.filter(
            config_id=no_template.id, success=False
        ).order_by('-started_at').first()
        self.assertIsNotNone(log)
        self.assertIn('template', log.error.lower())

    @patch('aluno_presente_sme.scheduler._notify_failure')
    @patch('aluno_presente_sme.scheduler.BotOrchestrator')
    def test_execute_falha_notifica(self, mock_orch_cls, mock_notify):
        async def fake_execute(input_data):
            return BotExecutionOutput(success=False, error='erro simulado')

        mock_orch_cls.return_value.execute = fake_execute

        sched_mod.execute_scheduled_job(self.config.id)
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        self.assertEqual(args[0], self.config.id)
        self.assertEqual(args[1], 'erro simulado')

    def test_record_failure_cria_log(self):
        sched_mod._record_scheduler_failure(self.config.id, 'algum erro')
        log = ExecutionLog.objects.filter(
            config_id=self.config.id, success=False
        ).order_by('-started_at').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.error, 'algum erro')

    @patch('aluno_presente_sme.scheduler._notify_failure')
    @patch('aluno_presente_sme.scheduler.BotOrchestrator')
    def test_execute_envio_zerado_notifica(self, mock_orch_cls, mock_notify):
        async def fake_execute(input_data):
            return BotExecutionOutput(
                success=True,
                messaging=MessageOutput(sent_count=0, failed_count=4),
            )

        mock_orch_cls.return_value.execute = fake_execute

        sched_mod.execute_scheduled_job(self.config.id)
        mock_notify.assert_called_once()
        args, _ = mock_notify.call_args
        self.assertEqual(args[0], self.config.id)
        self.assertIn('Nenhuma mensagem', args[1])
