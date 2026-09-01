from django.apps import AppConfig


class SnsConfig(AppConfig):
    name = 'sns'
    verbose_name = 'SNS投稿'

    def ready(self):
        from . import receivers  # noqa: F401
