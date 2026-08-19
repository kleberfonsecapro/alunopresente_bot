from aluno_presente_sme.skills.extractors.base import SiteExtractor


_REGISTRY: dict[str, type[SiteExtractor]] = {}


def register(cls: type[SiteExtractor]) -> type[SiteExtractor]:
    _REGISTRY[cls.site_type] = cls
    return cls


def get_extractor(site_type: str) -> type[SiteExtractor]:
    cls = _REGISTRY.get(site_type)
    if not cls:
        raise ValueError(
            f"Extractor '{site_type}' não encontrado. "
            f"Disponíveis: {', '.join(_REGISTRY)}"
        )
    return cls


def list_site_types() -> list[str]:
    return list(_REGISTRY)


def list_site_choices() -> list[tuple[str, str]]:
    return [(st, cls.site_label) for st, cls in _REGISTRY.items()]
