import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from django.test import SimpleTestCase

from aluno_presente_sme.skills.messaging_skill import MessagingSkill


def _ok_response():
    resp = MagicMock()
    resp.is_success = True
    return resp


def _bad_response(status_code: int, description: str):
    resp = MagicMock()
    resp.is_success = False
    resp.status_code = status_code
    resp.json.return_value = {'description': description}
    return resp


class SendTelegramRetryTest(SimpleTestCase):
    def _skill_with_client(self, responses):
        skill = MessagingSkill(bot_token='token-teste')
        client = MagicMock()
        client.is_closed = False
        client.post = AsyncMock(side_effect=responses)
        skill._client = client
        return skill, client

    @patch('aluno_presente_sme.skills.messaging_skill.asyncio.sleep', new=AsyncMock())
    def test_retries_em_erro_de_rede(self):
        skill, client = self._skill_with_client([
            httpx.ConnectError('network down'),
            httpx.ConnectError('network down'),
            _ok_response(),
        ])
        result = asyncio.run(skill.send_telegram('123', 'oi'))
        self.assertTrue(result)
        self.assertEqual(client.post.call_count, 3)

    @patch('aluno_presente_sme.skills.messaging_skill.asyncio.sleep', new=AsyncMock())
    def test_sem_retry_em_400_nao_relacionado_a_parse(self):
        skill, client = self._skill_with_client([
            _bad_response(400, 'chat not found'),
        ])
        result = asyncio.run(skill.send_telegram('123', 'oi'))
        self.assertFalse(result)
        self.assertEqual(client.post.call_count, 1)

    @patch('aluno_presente_sme.skills.messaging_skill.asyncio.sleep', new=AsyncMock())
    def test_fallback_sem_markdown_em_400_de_parse(self):
        skill, client = self._skill_with_client([
            _bad_response(400, "can't parse entities"),
            _ok_response(),
        ])
        result = asyncio.run(skill.send_telegram('123', 'oi'))
        self.assertTrue(result)
        self.assertEqual(client.post.call_count, 2)
        payloads = [call.kwargs['json'] for call in client.post.call_args_list]
        self.assertIn('parse_mode', payloads[0])
        self.assertNotIn('parse_mode', payloads[1])

    def test_sem_token_retorna_falso(self):
        skill = MessagingSkill(bot_token=None)
        result = asyncio.run(skill.send_telegram('123', 'oi'))
        self.assertFalse(result)
