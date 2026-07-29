from unittest.mock import patch, MagicMock

from django.test import TestCase

from scraper_bot.skills.extractors import (
    get_extractor,
    list_site_choices,
    list_site_types,
)
from scraper_bot.skills.extractors.aluno_presente import AlunoPresenteExtractor
from scraper_bot.skills.extractors.generic import GenericExtractor
from scraper_bot.skills.extractors.registry import _REGISTRY


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


class ExtractorSecurityTest(TestCase):
    def test_aluno_presente_matches_url_seguro(self):
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
