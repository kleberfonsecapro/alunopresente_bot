from unittest.mock import patch, MagicMock

from django.test import TestCase

from scraper_bot.skills.extractors import (
    get_extractor,
    list_site_choices,
    list_site_types,
)
from scraper_bot.skills.extractors.aluno_presente import AlunoPresenteExtractor
from scraper_bot.skills.extractors.escola_segura import EscolaSeguraExtractor
from scraper_bot.skills.extractors.generic import GenericExtractor
from scraper_bot.skills.extractors.registry import _REGISTRY


class ExtractorRegistryTest(TestCase):
    def test_registry_contains_aluno_presente(self):
        self.assertIn('aluno_presente', _REGISTRY)

    def test_registry_contains_generic(self):
        self.assertIn('generic', _REGISTRY)

    def test_registry_contains_escola_segura(self):
        self.assertIn('escola_segura', _REGISTRY)

    def test_get_extractor_aluno_presente(self):
        cls = get_extractor('aluno_presente')
        self.assertIs(cls, AlunoPresenteExtractor)

    def test_get_extractor_generic(self):
        cls = get_extractor('generic')
        self.assertIs(cls, GenericExtractor)

    def test_get_extractor_escola_segura(self):
        cls = get_extractor('escola_segura')
        self.assertIs(cls, EscolaSeguraExtractor)

    def test_get_extractor_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            get_extractor('nonexistent')
        self.assertIn('nonexistent', str(ctx.exception))

    def test_list_site_types(self):
        types = list_site_types()
        self.assertIn('aluno_presente', types)
        self.assertIn('generic', types)
        self.assertIn('escola_segura', types)

    def test_list_site_choices(self):
        choices = list_site_choices()
        self.assertIn(('aluno_presente', 'Aluno Presente'), choices)
        self.assertIn(('generic', 'Genérico (Playwright)'), choices)
        self.assertIn(('escola_segura', 'Escola Segura'), choices)


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

    @patch('scraper_bot.skills.extractors.aluno_presente.STORAGE_PATH')
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

    @patch('scraper_bot.skills.extractors.aluno_presente.STORAGE_PATH')
    def test_get_token_not_found(self, mock_path):
        mock_path.read_text.return_value = '{"origins": [{"localStorage": []}]}'
        extractor = AlunoPresenteExtractor()
        token = extractor.get_token()
        self.assertIsNone(token)

    @patch('scraper_bot.skills.extractors.aluno_presente.STORAGE_PATH')
    def test_get_token_file_error(self, mock_path):
        mock_path.read_text.side_effect = FileNotFoundError
        extractor = AlunoPresenteExtractor()
        token = extractor.get_token()
        self.assertIsNone(token)


class GenericExtractorTest(TestCase):
    def test_site_type_and_label(self):
        self.assertEqual(GenericExtractor.site_type, 'generic')
        self.assertEqual(GenericExtractor.site_label, 'Genérico (Playwright)')


class EscolaSeguraExtractorTest(TestCase):
    def test_site_type_and_label(self):
        self.assertEqual(EscolaSeguraExtractor.site_type, 'escola_segura')
        self.assertEqual(EscolaSeguraExtractor.site_label, 'Escola Segura')
        self.assertEqual(EscolaSeguraExtractor.token_key, 'escola-segura-token')

    def test_matches_url(self):
        extractor = EscolaSeguraExtractor()
        self.assertTrue(extractor.matches_url('https://escolasegura.srv.br/dashboard'))
        self.assertFalse(extractor.matches_url('https://example.com'))

    @patch('scraper_bot.skills.extractors.escola_segura.STORAGE_PATH')
    def test_get_token_success(self, mock_path):
        mock_path.read_text.return_value = '''{
            "origins": [{
                "localStorage": [
                    {"name": "escola-segura-token", "value": "esc-token-123"}
                ]
            }]
        }'''
        extractor = EscolaSeguraExtractor()
        token = extractor.get_token()
        self.assertEqual(token, 'esc-token-123')

    @patch('scraper_bot.skills.extractors.escola_segura.STORAGE_PATH')
    def test_get_token_not_found(self, mock_path):
        mock_path.read_text.return_value = '{"origins": [{"localStorage": []}]}'
        extractor = EscolaSeguraExtractor()
        token = extractor.get_token()
        self.assertIsNone(token)

    @patch('scraper_bot.skills.extractors.escola_segura.STORAGE_PATH')
    def test_get_token_file_error(self, mock_path):
        mock_path.read_text.side_effect = FileNotFoundError
        extractor = EscolaSeguraExtractor()
        token = extractor.get_token()
        self.assertIsNone(token)

    def test_safe_get_existing_key(self):
        extractor = EscolaSeguraExtractor()
        data = {'alunos': 150, 'nome': 'Escola A'}
        self.assertEqual(extractor._safe_get(data, 'alunos'), '150')
        self.assertEqual(extractor._safe_get(data, 'nome'), 'Escola A')

    def test_safe_get_missing_key(self):
        extractor = EscolaSeguraExtractor()
        self.assertIsNone(extractor._safe_get({}, 'inexistente'))

    def test_safe_get_none_value(self):
        extractor = EscolaSeguraExtractor()
        self.assertIsNone(extractor._safe_get({'x': None}, 'x'))

    def test_fmt_int_formata_corretamente(self):
        extractor = EscolaSeguraExtractor()
        self.assertEqual(extractor._fmt_int(1000), '1.000')
        self.assertEqual(extractor._fmt_int(1500000), '1.500.000')
        self.assertEqual(extractor._fmt_int(0), '0')

    def test_normalize_response_flat_values(self):
        extractor = EscolaSeguraExtractor()
        raw = {'total_alunos': 500, 'total_professores': 50}
        norm = extractor._normalize_response(raw)
        self.assertEqual(norm['total_alunos'], '500')
        self.assertEqual(norm['total_professores'], '50')

    def test_normalize_response_nested_dict(self):
        extractor = EscolaSeguraExtractor()
        raw = {'indicadores': {'presenca': 85, 'evasao': 15}}
        norm = extractor._normalize_response(raw)
        self.assertEqual(norm['indicadores_presenca'], '85')
        self.assertEqual(norm['indicadores_evasao'], '15')

    def test_normalize_response_list_counts(self):
        extractor = EscolaSeguraExtractor()
        raw = {'ocorrencias': ['A', 'B', 'C']}
        norm = extractor._normalize_response(raw)
        self.assertEqual(norm['ocorrencias'], '3')

    def test_extract_via_api_respeita_campos_solicitados(self):
        from scraper_bot.schemas import ExtractionContract
        extractor = EscolaSeguraExtractor()
        raw = {'total_alunos': 500, 'total_professores': 50}
        norm = extractor._normalize_response(raw)
        extracted = {}
        fields = [ExtractionContract(field_name='total_alunos'), ExtractionContract(field_name='inexistente')]
        for field in fields:
            val = extractor._safe_get(norm, field.field_name)
            extracted[field.field_name] = str(val) if val is not None else None
        self.assertEqual(extracted['total_alunos'], '500')
        self.assertIsNone(extracted['inexistente'])


class ExtractorSecurityTest(TestCase):
    def test_token_nao_vaza_em_mensagem_de_erro(self):
        from scraper_bot.skills.extractors.escola_segura import EscolaSeguraExtractor
        try:
            extractor = EscolaSeguraExtractor()
            extractor._safe_get({}, '')
        except Exception as e:
            msg = str(e).lower()
            self.assertNotIn('escola-segura-token', msg)
            self.assertNotIn('esc-token', msg)

    def test_relogin_nao_expoe_credenciais_no_log(self):
        import logging
        from io import StringIO

        buf = StringIO()
        handler = logging.StreamHandler(buf)
        logger = logging.getLogger('scraper_bot.skills.extractors.escola_segura')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info('Iniciando relogin para %s', 'escola_segura')
        logged = buf.getvalue()
        logger.removeHandler(handler)

        self.assertNotIn('ESCOLA_SEGURA_USER', logged)
        self.assertNotIn('ESCOLA_SEGURA_PASSWORD', logged)

    def test_matches_url_rejeita_url_estranha(self):
        extractor = EscolaSeguraExtractor()
        self.assertFalse(extractor.matches_url('https://escolasegura-malicioso.com.br'))
        self.assertFalse(extractor.matches_url('https://evildomain.com.br'))
        self.assertFalse(extractor.matches_url(''))
        self.assertFalse(extractor.matches_url('not-a-url'))
        self.assertTrue(extractor.matches_url('https://escolasegura.srv.br/painel'))
        self.assertTrue(extractor.matches_url('https://api.escolasegura.srv.br'))

    def test_aluno_presente_matches_url_seguro(self):
        from scraper_bot.skills.extractors.aluno_presente import AlunoPresenteExtractor
        extractor = AlunoPresenteExtractor()
        self.assertFalse(extractor.matches_url('https://alunopresente-malicioso.com.br'))
        self.assertFalse(extractor.matches_url('https://evildomain.com.br'))
        self.assertTrue(extractor.matches_url('https://cba.alunopresente.srv.br/dashboard'))
        self.assertTrue(extractor.matches_url('https://api.alunopresente.srv.br'))


class ExtractionSkillPluginTest(TestCase):
    @patch('scraper_bot.skills.extract_skill.get_extractor')
    async def test_extract_delegates_to_extractor(self, mock_get_extractor):
        async def async_playwright_result(url, fields):
            return {'url': url, 'extracted_at': '2025-01-01T00:00:00', 'data': {'key': 'value'}}

        mock_instance = MagicMock()
        mock_instance.get_token.return_value = None
        mock_instance.extract_via_playwright = async_playwright_result
        mock_get_extractor.return_value.return_value = mock_instance

        from scraper_bot.skills.extract_skill import ExtractionSkill
        skill = ExtractionSkill()
        result = await skill.extract(
            url='https://example.com',
            fields=[],
            site_type='generic',
        )

        mock_get_extractor.assert_called_once_with('generic')
        self.assertEqual(result['data']['key'], 'value')
