from ninja import Router
from ninja.security import SessionAuth

from aluno_presente_sme.models import BotConfig, ExecutionLog, MessageTemplate, Recipient
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate

from aluno_presente_sme.schemas import (
    AuthenticationInput,
    AuthenticationOutput,
    BotConfigInput,
    BotConfigOutput,
    BotConfigUpdate,
    BotExecutionInput,
    BotExecutionOutput,
    ExtractionInput,
    ExtractionOutput,
    MessageInput,
    MessageOutput,
    ExecutionLogOut,
    MessageTemplateInput,
    MessageTemplateOutput,
    MessageTemplateUpdate,
    NavigationInput,
    RecipientInput,
    RecipientOutput,
    RecipientUpdate,
    SchoolUnitOutput,
    StatsOutput,
    DayStats,
)
from aluno_presente_sme.services import BotOrchestrator
from aluno_presente_sme.skills.auth import AuthenticationSkill
from aluno_presente_sme.skills.extract_skill import ExtractionSkill
from aluno_presente_sme.skills.messaging_skill import MessagingSkill
from aluno_presente_sme.skills.navigation_skill import NavigationSkill

router = Router(auth=SessionAuth())


def _model_to_dict(instance, fields: list[str]) -> dict:
    return {f: getattr(instance, f) for f in fields}


@router.get('/site-types/', response=list[dict])
def list_site_types(request):
    from aluno_presente_sme.skills.extractors.registry import list_site_choices
    return [
        {'site_type': st, 'label': label}
        for st, label in list_site_choices()
    ]


@router.get('/school-unities/', response=list[SchoolUnitOutput])
async def list_school_units(request):
    from aluno_presente_sme.skills.extractors.aluno_presente import AlunoPresenteExtractor
    extractor = AlunoPresenteExtractor()
    token = extractor.get_token()
    if not token:
        return []
    try:
        units = await extractor.list_school_units(token)
        return [SchoolUnitOutput(id=u['id'], nome=u['nome']) for u in units]
    except Exception:
        return []


@router.get('/configs/', response=list[dict])
def list_configs(request):
    qs = BotConfig.objects.all().select_related('template')
    return [{
        'id': c.id, 'name': c.name, 'site_type': c.site_type, 'target_url': c.target_url,
        'extraction_fields': c.extraction_fields,
        'send_times': c.send_times, 'send_days_of_week': c.send_days_of_week,
        'send_duration_days': c.send_duration_days,
        'is_active': c.is_active,
        'school_unit_ids': c.school_unit_ids or [],
        'template_id': c.template_id,
        'template_name': c.template.name if c.template else None,
        'created_at': c.created_at.isoformat(),
        'updated_at': c.updated_at.isoformat(),
    } for c in qs]


@router.post('/configs/', response=dict)
def create_config(request, payload: BotConfigInput):
    config = BotConfig.objects.create(**payload.model_dump())
    return _config_to_dict(config)


@router.patch('/configs/{config_id}/', response=dict)
def update_config(request, config_id: int, payload: BotConfigUpdate):
    config = BotConfig.objects.get(id=config_id)
    for attr, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, attr, value)
    config.save()
    config.refresh_from_db()
    return _config_to_dict(config)


def _config_to_dict(config: BotConfig) -> dict:
    return {
        'id': config.id, 'name': config.name, 'site_type': config.site_type, 'target_url': config.target_url,
        'extraction_fields': config.extraction_fields,
        'send_times': config.send_times, 'send_days_of_week': config.send_days_of_week,
        'send_duration_days': config.send_duration_days,
        'is_active': config.is_active,
        'school_unit_ids': config.school_unit_ids or [],
        'template_id': config.template_id,
        'template_name': config.template.name if config.template else None,
        'created_at': config.created_at.isoformat(),
        'updated_at': config.updated_at.isoformat(),
    }


@router.delete('/configs/{config_id}/', response=dict)
def delete_config(request, config_id: int):
    config = BotConfig.objects.get(id=config_id)
    config.delete()
    return {'success': True}


@router.get('/logs/', response=list[ExecutionLogOut])
def list_logs(request):
    qs = ExecutionLog.objects.select_related('config', 'template').all()[:50]
    return [{
        'id': log.id,
        'config_id': log.config_id,
        'config_name': log.config.name if log.config else '—',
        'template_name': log.template.name if log.template else '—',
        'trigger': log.trigger,
        'started_at': log.started_at,
        'finished_at': log.finished_at,
        'success': log.success,
        'error': log.error,
        'sent_count': log.sent_count,
        'failed_count': log.failed_count,
        'duration_sec': round((log.finished_at - log.started_at).total_seconds(), 1) if log.finished_at and log.started_at else None,
    } for log in qs]


@router.get('/stats/', response=StatsOutput)
def get_stats(request):
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Q

    qs = ExecutionLog.objects.filter(started_at__isnull=False)

    total = qs.count()
    success_count = qs.filter(success=True).count()
    failed_count = qs.filter(success=False).count()
    aggr = qs.aggregate(
        total_sent=Sum('sent_count'),
        total_failed_msgs=Sum('failed_count'),
    )

    by_trigger = dict(
        qs.values('trigger').annotate(count=Count('id')).values_list('trigger', 'count')
    )

    start = timezone.localtime(timezone.now()).date() - timedelta(days=6)
    last_7 = []
    for i in range(7):
        day = start + timedelta(days=i)
        day_qs = qs.filter(started_at__date=day)
        last_7.append(DayStats(
            date=day.strftime('%d/%m'),
            total=day_qs.count(),
            success=day_qs.filter(success=True).count(),
            sent=day_qs.aggregate(s=Sum('sent_count'))['s'] or 0,
        ))

    avg_dur = None
    if total:
        dur_total = 0
        dur_count = 0
        for log in qs.filter(finished_at__isnull=False).iterator():
            delta = (log.finished_at - log.started_at).total_seconds()
            if delta >= 0:
                dur_total += delta
                dur_count += 1
        if dur_count:
            avg_dur = round(dur_total / dur_count, 1)

    success_rate = round(success_count / total * 100, 1) if total else 0.0

    return StatsOutput(
        total_executions=total,
        total_success=success_count,
        total_failed=failed_count,
        success_rate=success_rate,
        total_sent=aggr['total_sent'] or 0,
        total_failed_msgs=aggr['total_failed_msgs'] or 0,
        avg_duration_sec=avg_dur,
        by_trigger=by_trigger,
        last_7_days=last_7,
    )


@router.get('/templates/', response=list[dict])
def list_templates(request):
    return list(MessageTemplate.objects.all().values())


@router.post('/templates/', response=dict)
def create_template(request, payload: MessageTemplateInput):
    template = MessageTemplate.objects.create(**payload.model_dump())
    return _model_to_dict(template, [
        'id', 'name', 'body', 'created_at', 'updated_at'
    ])


@router.patch('/templates/{template_id}/', response=dict)
def update_template(request, template_id: int, payload: MessageTemplateUpdate):
    template = MessageTemplate.objects.get(id=template_id)
    for attr, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, attr, value)
    template.save()
    return _model_to_dict(template, [
        'id', 'name', 'body', 'created_at', 'updated_at'
    ])


@router.delete('/templates/{template_id}/', response=dict)
def delete_template(request, template_id: int):
    template = MessageTemplate.objects.get(id=template_id)
    template.delete()
    return {'success': True}


@router.get('/recipients/', response=list[dict])
def list_recipients(request):
    return list(Recipient.objects.all().values())


@router.post('/recipients/', response=dict)
def create_recipient(request, payload: RecipientInput):
    recipient = Recipient.objects.create(**payload.model_dump())
    return _model_to_dict(recipient, [
        'id', 'name', 'identifier', 'platform',
        'is_active', 'created_at'
    ])


@router.patch('/recipients/{recipient_id}/', response=dict)
def update_recipient(request, recipient_id: int, payload: RecipientUpdate):
    recipient = Recipient.objects.get(id=recipient_id)
    for attr, value in payload.model_dump(exclude_unset=True).items():
        setattr(recipient, attr, value)
    recipient.save()
    return _model_to_dict(recipient, [
        'id', 'name', 'identifier', 'platform',
        'is_active', 'created_at'
    ])


@router.delete('/recipients/{recipient_id}/', response=dict)
def delete_recipient(request, recipient_id: int):
    recipient = Recipient.objects.get(id=recipient_id)
    recipient.delete()
    return {'success': True}


@router.post('/execute/', response=BotExecutionOutput)
async def execute_bot(request, payload: BotExecutionInput):
    orchestrator = BotOrchestrator()
    result = await orchestrator.execute(payload)
    return result


@router.post('/auth/login-site/', response=AuthenticationOutput)
async def login_site(request, payload: AuthenticationInput):
    skill = AuthenticationSkill()
    result = await skill.login(
        url=payload.url,
        username=payload.username,
        password=payload.password
    )
    return result


@router.post('/auth/relogin/', response=AuthenticationOutput)
async def relogin_site(request):
    import os
    skill = AuthenticationSkill()
    result = await skill.login(
        url=os.environ.get('TARGET_SITE_URL', 'https://cba.alunopresente.srv.br/login'),
        username=os.environ.get('TARGET_SITE_USER', ''),
        password=os.environ.get('TARGET_SITE_PASSWORD', ''),
    )
    return result


@router.post('/extract/', response=ExtractionOutput)
async def extract_data(request, payload: ExtractionInput):
    skill = ExtractionSkill()
    result = await skill.extract(
        url=payload.url,
        fields=payload.fields,
        site_type=payload.site_type,
    )
    return result


@router.post('/navigate/', response=dict)
async def navigate(request, payload: NavigationInput):
    skill = NavigationSkill()
    result = await skill.navigate(
        url=payload.url,
        wait_selector=payload.wait_selector,
        scroll_to_bottom=payload.scroll_to_bottom
    )
    return result


@router.post('/send/', response=MessageOutput)
async def send_message(request, payload: MessageInput):
    skill = MessagingSkill()
    result = await skill.send_bulk(
        template_body=payload.template_body,
        extracted_data=payload.extracted_data,
        recipients=payload.recipients
    )
    return result
