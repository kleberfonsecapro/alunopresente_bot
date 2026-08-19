import os
import asyncio

import httpx
from jinja2 import Template

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_CONCURRENT_SENDS = 10
MAX_TELEGRAM_ATTEMPTS = 3


class MessagingSkill:

    def __init__(self, bot_token: str | None = None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=TELEGRAM_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def apply_template(self, template_body: str, extracted_data: dict) -> str:
        template = Template(template_body)
        return template.render(**extracted_data)

    async def send_telegram(self, chat_id: str, text: str) -> bool:
        if not self.bot_token:
            return False
        url = TELEGRAM_API_URL.format(token=self.bot_token)
        client = await self._get_client()
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
        }
        for attempt in range(1, MAX_TELEGRAM_ATTEMPTS + 1):
            try:
                response = await client.post(url, json=payload)
                if response.is_success:
                    return True

                description = ''
                try:
                    body = response.json()
                    description = str(body.get('description', ''))
                except Exception:
                    pass

                if (
                    response.status_code == 400
                    and 'parse' in description.lower()
                    and payload.get('parse_mode')
                ):
                    payload = {k: v for k, v in payload.items() if k != 'parse_mode'}
                    continue

                if 400 <= response.status_code < 500:
                    return False
            except httpx.HTTPError:
                pass
            if attempt < MAX_TELEGRAM_ATTEMPTS:
                await asyncio.sleep(2 * attempt)
        return False

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
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SENDS)

        async def _send_one(recipient: dict) -> tuple[bool, str]:
            platform = recipient['platform']
            identifier = recipient['identifier']
            async with semaphore:
                error = await self.send_message(platform, identifier, message_body)
                if error is None:
                    return True, f"✓ Enviado para {identifier} via {platform}"
                return False, f"✗ {error}"

        results = await asyncio.gather(
            *[_send_one(r) for r in recipients],
            return_exceptions=True
        )

        sent = 0
        failed = 0
        details = []

        for result in results:
            if isinstance(result, Exception):
                failed += 1
                details.append(f"✗ Erro inesperado: {result}")
            else:
                success, detail = result
                if success:
                    sent += 1
                else:
                    failed += 1
                details.append(detail)

        return {
            'sent_count': sent,
            'failed_count': failed,
            'details': details,
        }