import unittest
from unittest.mock import patch
import sys
from types import ModuleType

# Os testes não precisam de servidor MariaDB nem de PyMySQL.
if "db" not in sys.modules:
    db_stub = ModuleType("db")
    db_stub.fetch_one = lambda *args, **kwargs: None
    db_stub.execute = lambda *args, **kwargs: None
    sys.modules["db"] = db_stub

from currency_repository import guardar_taxa, obter_ultima_taxa


class TestRepositorio(unittest.TestCase):
    @patch('currency_repository.execute')
    def test_guardar(self, executar):
        guardar_taxa({'base': 'EUR', 'quote': 'USD', 'date': '2026-10-30', 'rate': '1.1165'})
        self.assertEqual(executar.call_count, 1)

    @patch('currency_repository.execute')
    def test_rejeitar_sem_data(self, executar):
        with self.assertRaises(ValueError):
            guardar_taxa({'base': 'EUR', 'quote': 'USD', 'date': None, 'rate': '1.1'})
        executar.assert_not_called()

    @patch('currency_repository.fetch_one', return_value=None)
    def test_sem_registos(self, consultar):
        self.assertIsNone(obter_ultima_taxa('EUR', 'USD'))
        consultar.assert_called_once()


if __name__ == '__main__':
    unittest.main()
