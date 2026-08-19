from django.apps import AppConfig


class AlunoPresenteSmeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aluno_presente_sme'
    verbose_name = 'Aluno Presente SME'

    def ready(self):
        import aluno_presente_sme.signals  # noqa: F401
