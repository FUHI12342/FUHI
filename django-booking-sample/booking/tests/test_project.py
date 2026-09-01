from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from project.database import database_config_from_url


class DatabaseUrlParserTests(TestCase):
    def test_standard_url(self):
        config = database_config_from_url('postgres://app:s3cret@10.0.0.5:5432/booking')
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['NAME'], 'booking')
        self.assertEqual(config['USER'], 'app')
        self.assertEqual(config['PASSWORD'], 's3cret')
        self.assertEqual(config['HOST'], '10.0.0.5')
        self.assertEqual(config['PORT'], '5432')

    def test_cloud_sql_unix_socket(self):
        config = database_config_from_url(
            'postgres://app:pw@/booking?host=/cloudsql/myproj:asia-northeast1:db1'
        )
        self.assertEqual(config['HOST'], '/cloudsql/myproj:asia-northeast1:db1')
        self.assertEqual(config['NAME'], 'booking')

    def test_rejects_unknown_scheme(self):
        with self.assertRaises(ImproperlyConfigured):
            database_config_from_url('mysql://a:b@h/db')
