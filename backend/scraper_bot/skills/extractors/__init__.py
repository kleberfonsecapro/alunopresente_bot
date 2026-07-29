from scraper_bot.skills.extractors.base import SiteExtractor
from scraper_bot.skills.extractors.registry import (
    get_extractor,
    list_site_choices,
    list_site_types,
    register,
)
from scraper_bot.skills.extractors.generic import GenericExtractor
from scraper_bot.skills.extractors.aluno_presente import AlunoPresenteExtractor
from scraper_bot.skills.extractors.escola_segura import EscolaSeguraExtractor
