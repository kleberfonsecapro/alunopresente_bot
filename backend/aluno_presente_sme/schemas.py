from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ExtractionContract(BaseModel):
    field_name: str
    value: Any = None
    selector: str | None = None


class ExtractionInput(BaseModel):
    url: str
    site_type: str | None = Field(
        default=None,
        description="Tipo do site alvo. Auto-detectado se não informado."
    )
    fields: list[ExtractionContract] = Field(
        default_factory=list,
        description="Campos a serem extraídos da página alvo"
    )


class ExtractionOutput(BaseModel):
    url: str
    extracted_at: datetime = Field(default_factory=datetime.now)
    data: dict[str, Any]


class AuthenticationInput(BaseModel):
    url: str
    username: str
    password: str


class AuthenticationOutput(BaseModel):
    success: bool
    message: str = ""


class NavigationInput(BaseModel):
    url: str
    wait_selector: str | None = None
    scroll_to_bottom: bool = False


class NavigationOutput(BaseModel):
    title: str
    current_url: str
    page_source_snippet: str = ""


class MessageInput(BaseModel):
    template_body: str
    extracted_data: dict[str, Any]
    recipients: list[dict] = Field(
        description='Lista de destinatários: [{"platform": "telegram", "identifier": "12345"}]'
    )


class MessageOutput(BaseModel):
    sent_count: int
    failed_count: int
    details: list[str] = Field(default_factory=list)


class BotExecutionInput(BaseModel):
    config_id: int
    template_id: int | None = None
    recipient_ids: list[int] = Field(default_factory=list)
    skip_time_check: bool = False
    preview: bool = False
    trigger: str = 'manual'
    unit_id: int | None = Field(
        default=None,
        description="ID de uma unidade escolar específica para consulta avulsa"
    )
    period: str | None = Field(
        default=None,
        description="Filtro de período (MATUTINO, VESPERTINO, INTEGRAL, NOTURNO)"
    )


class BotConfigInput(BaseModel):
    name: str
    site_type: str = 'aluno_presente'
    target_url: str
    extraction_fields: list = Field(
        default_factory=list,
        description='Campos a extrair. Ex: ["titulo"] ou [{"field_name":"titulo","selector":".css"}]'
    )
    send_times: list[str] = Field(
        default_factory=list,
        description='Horários de disparo. Ex: ["08:00", "14:00", "20:00"]'
    )
    send_days_of_week: list[int] = Field(
        default_factory=list,
        description="Dias da semana. 0=segunda, 6=domingo. Vazio = todos."
    )
    send_duration_days: int | None = Field(
        default=None,
        description="Duração em dias. Null = indeterminado."
    )
    template_id: int | None = Field(
        default=None,
        description="ID do template usado no disparo automático"
    )
    school_unit_ids: list[int] = Field(
        default_factory=list,
        description="IDs das unidades escolares para filtrar. Vazio = todas."
    )


class BotConfigUpdate(BaseModel):
    name: str | None = None
    site_type: str | None = None
    target_url: str | None = None
    extraction_fields: list | None = None
    send_times: list[str] | None = None
    send_days_of_week: list[int] | None = None
    send_duration_days: int | None = None
    is_active: bool | None = None
    template_id: int | None = None
    school_unit_ids: list[int] | None = None


class BotConfigOutput(BaseModel):
    id: int
    name: str
    site_type: str
    target_url: str
    extraction_fields: list[str]
    send_times: list[str]
    send_days_of_week: list[int]
    send_duration_days: int | None
    is_active: bool
    school_unit_ids: list[int]
    created_at: datetime
    updated_at: datetime


class MessageTemplateInput(BaseModel):
    name: str
    body: str


class MessageTemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None


class RecipientInput(BaseModel):
    name: str
    identifier: str
    platform: str


class RecipientUpdate(BaseModel):
    name: str | None = None
    identifier: str | None = None
    platform: str | None = None
    is_active: bool | None = None


class MessageTemplateOutput(BaseModel):
    id: int
    name: str
    body: str
    created_at: datetime
    updated_at: datetime

 
class RecipientOutput(BaseModel):
    id: int
    name: str
    identifier: str
    platform: str
    is_active: bool
    created_at: datetime


class BotExecutionOutput(BaseModel):
    success: bool
    extraction: ExtractionOutput | None = None
    messaging: MessageOutput | None = None
    error: str | None = None
    log_id: int | None = None


class ExecutionLogOut(BaseModel):
    id: int
    config_id: int | None = None
    config_name: str = ""
    template_name: str = ""
    trigger: str
    started_at: datetime
    finished_at: datetime | None = None
    success: bool
    error: str | None = None
    sent_count: int
    failed_count: int
    duration_sec: float | None = None


class DayStats(BaseModel):
    date: str
    total: int
    success: int
    sent: int


class StatsOutput(BaseModel):
    total_executions: int
    total_success: int
    total_failed: int
    success_rate: float
    total_sent: int
    total_failed_msgs: int
    avg_duration_sec: float | None = None
    by_trigger: dict[str, int]
    last_7_days: list[DayStats]


class SchoolUnitOutput(BaseModel):
    id: int
    nome: str
