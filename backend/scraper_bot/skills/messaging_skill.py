import os

import httpx
from jinja2 import Template

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class MessagingSkill:

    def __init__(self, bot_token: str | None = None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')

    def apply_template(self, template_body: str, extracted_data: dict) -> str:
        template = Template(template_body)
        return template.render(**extracted_data)

    async def send_telegram(self, chat_id: str, text: str) -> bool:
        if not self.bot_token:
            return False
        url = TELEGRAM_API_URL.format(token=self.bot_token)
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown',
            })
            return response.is_success

    async def send_message(self, platform: str, identifier: str, message_body: str) -> str | None:
        if platform == 'telegram':
            success = await self.send_telegram(identifier, message_body)
            return None if success else f"Falha ao enviar Telegram para {identifier}"
        return f"Plataforma não suportada: {platform}"

    async def send_bulk(
        self,
        template_body: str,
        extracted_data: dict,
        recipients: list[dict],
    ) -> dict:
        message_body = self.apply_template(template_body, extracted_data)
        sent = 0
        failed = 0
        details = []

        for recipient in recipients:
            platform = recipient['platform']
            identifier = recipient['identifier']
            error = await self.send_message(platform, identifier, message_body)
            if error is None:
                sent += 1
                details.append(f"✓ Enviado para {identifier} via {platform}")
            else:
                failed += 1
                details.append(f"✗ {error}")

        return {
            'sent_count': sent,
            'failed_count': failed,
            'details': details,
        }
