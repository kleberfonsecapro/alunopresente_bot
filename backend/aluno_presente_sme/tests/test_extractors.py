import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from django.test import SimpleTestCase, TestCase

from aluno_presente_sme.schemas import ExtractionContract
from aluno_presente_sme.skills.extractors import (
    get_extractor,
    list_site_choices,
    list_site_types,
)
from aluno_presente_sme.skills.extractors.aluno_presente import AlunoPresenteExtractor
from aluno_presente_sme.skills.extractors.generic import GenericExtractor
from aluno_presente_sme.skills.extractors.registry import _REGISTRY


class ExtractorRegistryTest(TestCase):
    def test_registry_contains_aluno_presente(self):
        self.assertIn('aluno_presente', _REGISTRY)

    def test_registry_contains_generic(self):
        self.assertIn('generic', _REGISTRY)

    def test_get_extractor_aluno_presente(self):
        cls = get_extractor('aluno_presente')
        self.assertIs(cls, AlunoPresenteExtractor)

    def test_get_extractor_generic(self):
        cls = get_extractor('generic')
        self.assertIs(cls, GenericExtractor)

    def test_get_extractor_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            get_extractor('nonexistent')
        self.assertIn('nonexistent', str(ctx.exception))

    def test_list_site_types(self):
        types = list_site_types()
        self.assertIn('aluno_presente', types)
        self.assertIn('generic', types)

    def test_list_site_choices(self):
        choices = list_site_choices()
        self.assertIn(('aluno_presente', 'Aluno Presente'), choices)
        self.assertIn(('generic', 'Genérico (Playwright)'), choices)


class ExtractorBaseContractTest(TestCase):
    def test_all_extractors_have_site_type(self):
        for st, cls in _REGISTRY.items():
            self.assertEqual(cls.site_type, st)

    def test_all_extractors_have_site_label(self):
        for st, cls in _REGISTRY.items():
            self.assertTrue(cls.site_label)


class AlunoPresenteExtractorTest(TestCase):
    def test_site_type_and_label(self):
        self.assertEqual(AlunoPresenteExtractor.site_type, 'aluno_presente')
        self.assertEqual(AlunoPresenteExtractor.site_label, 'Aluno Presente')
        self.assertEqual(AlunoPresenteExtractor.api_base, 'https://cba.alunopresente.srv.br')
        self.assertEqual(AlunoPresenteExtractor.token_key, 'aluno-presente-token')

    def test_matches_url(self):
        extractor = AlunoPresenteExtractor()
        self.assertTrue(extractor.matches_url('https://cba.alunopresente.srv.br/dashboard'))
        self.assertFalse(extractor.matches_url('https://example.com'))

    @patch('aluno_presente_sme.skills.extractors.aluno_presente.STORAGE_PATH')
    def test_get_token_success(self, mock_path):
        mock_path.read_text.return_value = '''{
            "origins": [{
                "localStorage": [
                    {"name": "aluno-presente-token", "value": "mytoken123"}
                ]
            }]
        }'''
        extractor = AlunoPresenteExtractor()
        token = extractor.get_token()
        self.assertEqual(token, 'mytoken123')

    @patch('aluno_presente_sme.skills.extractors.aluno_presente.STORAGE_PATH')
    def test_get_token_not_found(self, mock_path):
        mock_path.read_text.return_value = '{"origins": [{"localStorage": []}]}'
        extractor = AlunoPresenteExtractor()
        token = extractor.get_token()
        self.assertIsNone(token)

    @patch('aluno_presente_sme.skills.extractors.aluno_presente.STORAGE_PATH')
    def test_get_token_file_error(self, mock_path):
        mock_path.read_text.side_effect = FileNotFoundError
        extractor = AlunoPresenteExtractor()
        token = extractor.get_token()
        self.assertIsNone(token)


class GenericExtractorTest(TestCase):
    def test_site_type_and_label(self):
        self.assertEqual(GenericExtractor.site_type, 'generic')
        self.assertEqual(GenericExtractor.site_label, 'Genérico (Playwright)')


class ExtractorSecurityTest(TestCase):
    def test_aluno_presente_matches_url_seguro(self):
        extractor = AlunoPresenteExtractor()
        self.assertFalse(extractor.matches_url('https://alunopresente-malicioso.com.br'))
        self.assertFalse(extractor.matches_url('https://evildomain.com.br'))
        self.assertTrue(extractor.matches_url('https://cba.alunopresente.srv.br/dashboard'))
        self.assertTrue(extractor.matches_url('https://api.alunopresente.srv.br'))


class ExtractionSkillPluginTest(TestCase):
    @patch('aluno_presente_sme.skills.extract_skill.get_extractor')
    async def test_extract_delegates_to_extractor(self, mock_get_extractor):
        async def async_playwright_result(url, fields):
            return {'url': url, 'extracted_at': '2025-01-01T00:00:00', 'data': {'key': 'value'}}

        mock_instance = MagicMock()
        mock_instance.get_token.return_value = None
        mock_instance.extract_via_playwright = async_playwright_result
        mock_get_extractor.return_value.return_value = mock_instance

        from aluno_presente_sme.skills.extract_skill import ExtractionSkill
        skill = ExtractionSkill()
        result = await skill.extract(
            url='https://example.com',
            fields=[],
            site_type='generic',
        )

        mock_get_extractor.assert_called_once_with('generic')
        self.assertEqual(result['data']['key'], 'value')


LOGIN_URL = 'https://cba.alunopresente.srv.br/login'
DASHBOARD_URL = 'https://cba.alunopresente.srv.br/alunopresente/dashboard-secretario'
STORAGE_STATE = {'origins': []}


class _FakeElement:
    def __init__(self, text):
        self._text = text

    async def inner_text(self):
        return self._text


class _FakePage:
    """`url_map` simula a resposta do servidor: requested_url -> url efetiva
    (redirect para /login quando a sessão é inválida)."""

    def __init__(self, url_map, dom=None):
        self.url_map = url_map or {}
        self.dom = dom or {}
        self.url = ''
        self.context = None

    async def goto(self, url, **kwargs):
        self.url = self.url_map.get(url, url)

    async def query_selector(self, selector):
        if selector in self.dom:
            return _FakeElement(self.dom[selector])
        return None


class _FakeContext:
    def __init__(self, browser, url_map, dom):
        self.page = _FakePage(url_map, dom)
        self.page.context = self
        self.closed = False

    async def new_page(self):
        return self.page

    async def close(self):
        self.closed = True


class _FakeBrowser:
    """Emula navegador Playwright. Cada novo contexto usa o próximo url_map."""

    def __init__(self, url_maps, dom=None):
        self.url_maps = list(url_maps)
        self.dom = dom or {}
        self.contexts = []
        self.closed = False

    async def new_context(self, storage_state=None):
        url_map = self.url_maps[min(len(self.contexts), len(self.url_maps) - 1)]
        ctx = _FakeContext(self, url_map, self.dom)
        self.contexts.append(ctx)
        return ctx

    async def close(self):
        self.closed = True


class _FakePlaywright:
    def __init__(self, browser):
        self.chromium = MagicMock()
        self.chromium.launch = AsyncMock(return_value=browser)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class PlaywrightFallbackAuthTest(SimpleTestCase):
    """Fallback Playwright não pode mais produzir dados inúteis (page.url)."""

    def _extractor(self):
        extractor = AlunoPresenteExtractor()
        extractor.relogin = AsyncMock()
        return extractor

    @patch('aluno_presente_sme.skills.auth_skill.get_storage_state')
    @patch('playwright.async_api.async_playwright')
    def test_sem_sessao_reloga_antes_de_extrair(self, mock_pw, mock_storage):
        mock_storage.side_effect = [None, STORAGE_STATE]
        mock_pw.return_value = _FakePlaywright(
            _FakeBrowser([{}], dom={'.qtd': '123'})
        )
        extractor = self._extractor()

        result = asyncio.run(extractor.extract_via_playwright(
            DASHBOARD_URL,
            [ExtractionContract(field_name='presentes', selector='.qtd')],
        ))

        extractor.relogin.assert_awaited_once()
        self.assertEqual(result['data']['presentes'], '123')
        self.assertNotEqual(result['data']['presentes'], result['url'])

    @patch('aluno_presente_sme.skills.auth_skill.get_storage_state')
    @patch('playwright.async_api.async_playwright')
    def test_redirecionado_para_login_reloga_e_recupera(self, mock_pw, mock_storage):
        mock_storage.return_value = STORAGE_STATE
        mock_pw.return_value = _FakePlaywright(
            _FakeBrowser([{DASHBOARD_URL: LOGIN_URL}, {}], dom={'.qtd': '456'})
        )
        extractor = self._extractor()

        result = asyncio.run(extractor.extract_via_playwright(
            DASHBOARD_URL,
            [ExtractionContract(field_name='presentes', selector='.qtd')],
        ))

        extractor.relogin.assert_awaited_once()
        self.assertEqual(result['data']['presentes'], '456')

    @patch('aluno_presente_sme.skills.auth_skill.get_storage_state')
    @patch('playwright.async_api.async_playwright')
    def test_login_persistente_apos_relogin_levanta_erro_claro(self, mock_pw, mock_storage):
        mock_storage.return_value = STORAGE_STATE
        mock_pw.return_value = _FakePlaywright(
            _FakeBrowser([{DASHBOARD_URL: LOGIN_URL}, {DASHBOARD_URL: LOGIN_URL}], dom={'.qtd': '789'})
        )
        extractor = self._extractor()

        with self.assertRaises(RuntimeError) as ctx:
            asyncio.run(extractor.extract_via_playwright(
                DASHBOARD_URL,
                [ExtractionContract(field_name='presentes', selector='.qtd')],
            ))
        self.assertIn('Re-login automático falhou', str(ctx.exception))
        self.assertEqual(extractor.relogin.await_count, 1)

    @patch('aluno_presente_sme.skills.auth_skill.get_storage_state')
    @patch('playwright.async_api.async_playwright')
    def test_campo_sem_selector_nao_vaza_page_url(self, mock_pw, mock_storage):
        """Aluno Presente: campo sem selector falha de forma explícita (sem page.url)."""
        mock_storage.return_value = STORAGE_STATE
        mock_pw.return_value = _FakePlaywright(_FakeBrowser([{}]))
        extractor = self._extractor()

        with self.assertRaises(RuntimeError) as ctx:
            asyncio.run(extractor.extract_via_playwright(
                DASHBOARD_URL,
                [ExtractionContract(field_name='presentes')],
            ))
        self.assertIn('selector', str(ctx.exception))

    @patch('aluno_presente_sme.skills.auth_skill.get_storage_state')
    @patch('playwright.async_api.async_playwright')
    def test_generic_sem_selector_retorna_none_nao_page_url(self, mock_pw, mock_storage):
        """Genérico: campo sem selector vira None (honesto), nunca a URL da página."""
        mock_storage.return_value = STORAGE_STATE
        mock_pw.return_value = _FakePlaywright(_FakeBrowser([{}]))
        extractor = GenericExtractor()

        result = asyncio.run(extractor.extract_via_playwright(
            DASHBOARD_URL,
            [ExtractionContract(field_name='titulo')],
        ))

        self.assertIsNone(result['data']['titulo'])
        self.assertNotEqual(result['data']['titulo'], result['url'])


class ExtractionSkillAuthFlowTest(SimpleTestCase):
    """ExtractionSkill deve obter token (relogin) antes de cair no fallback."""

    def setUp(self):
        self.extractor_cls = MagicMock()
        self.extractor = MagicMock()
        self.extractor_cls.return_value = self.extractor
        self.extractor.login_url = LOGIN_URL

    @patch('aluno_presente_sme.skills.extract_skill.get_extractor')
    def test_sem_token_reloga_para_obter_token_e_usa_api(self, mock_get):
        mock_get.return_value = self.extractor_cls
        self.extractor.get_token.side_effect = [None, 'novo-token']
        self.extractor.relogin = AsyncMock()
        self.extractor.extract_via_api = AsyncMock(
            return_value={'url': 'x', 'data': {'presentes': '100'}}
        )

        from aluno_presente_sme.skills.extract_skill import ExtractionSkill
        result = asyncio.run(ExtractionSkill().extract(LOGIN_URL, []))

        self.assertEqual(result['data']['presentes'], '100')
        self.extractor.relogin.assert_awaited_once()
        self.extractor.extract_via_api.assert_awaited_once()

    @patch('aluno_presente_sme.skills.extract_skill.get_extractor')
    def test_relogin_inicial_falha_cai_para_playwright(self, mock_get):
        mock_get.return_value = self.extractor_cls
        self.extractor.get_token.side_effect = [None, None]
        self.extractor.relogin = AsyncMock(side_effect=RuntimeError('login quebrado'))

        async def fake_pw(url, fields):
            return {'url': url, 'data': {'x': '1'}}
        self.extractor.extract_via_playwright = fake_pw

        from aluno_presente_sme.skills.extract_skill import ExtractionSkill
        result = asyncio.run(ExtractionSkill().extract(LOGIN_URL, []))

        self.assertEqual(result['data']['x'], '1')
        self.extractor.relogin.assert_awaited_once()

    @patch('aluno_presente_sme.skills.extract_skill.get_extractor')
    def test_token_401_reloga_e_retenta_api(self, mock_get):
        mock_get.return_value = self.extractor_cls
        self.extractor.get_token.side_effect = ['expirado', 'novo-token']
        self.extractor.relogin = AsyncMock()
        request = httpx.Request('GET', 'https://cba.alunopresente.srv.br/api')
        response = httpx.Response(401, request=request)
        self.extractor.extract_via_api = AsyncMock(side_effect=[
            httpx.HTTPStatusError('401', request=request, response=response),
            {'url': 'x', 'data': {'presentes': '200'}},
        ])

        from aluno_presente_sme.skills.extract_skill import ExtractionSkill
        result = asyncio.run(ExtractionSkill().extract(LOGIN_URL, []))

        self.assertEqual(result['data']['presentes'], '200')
        self.extractor.relogin.assert_awaited_once()
        self.assertEqual(self.extractor.extract_via_api.await_count, 2)

    @patch('aluno_presente_sme.skills.extract_skill.get_extractor')
    def test_site_sem_login_nao_tenta_relogin(self, mock_get):
        """Genérico (login_url vazio) nunca chama relogin só para obter token."""
        self.extractor.login_url = ''
        mock_get.return_value = self.extractor_cls
        self.extractor.get_token.return_value = None
        self.extractor.relogin = AsyncMock()

        async def fake_pw(url, fields):
            return {'url': url, 'data': {'x': '1'}}
        self.extractor.extract_via_playwright = fake_pw

        from aluno_presente_sme.skills.extract_skill import ExtractionSkill
        result = asyncio.run(ExtractionSkill().extract('https://publico.com', []))

        self.assertEqual(result['data']['x'], '1')
        self.extractor.relogin.assert_not_awaited()
