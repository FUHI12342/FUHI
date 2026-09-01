from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'inventory'
    verbose_name = '在庫・発注'

    def ready(self):
        from . import receivers  # noqa: F401
