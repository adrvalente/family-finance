import unittest
from decimal import Decimal
from unittest.mock import Mock
from currency_converter import obter_taxa, converter, CurrencyError

class TestConversor(unittest.TestCase):
    def test_conversao(self):
        resposta = Mock()
        resposta.json.return_value = {"date": "2026-10-29", "base": "EUR", "quote": "USD", "rate": 1.2}
        cliente = Mock()
        cliente.get.return_value = resposta
        resultado = converter("100", "eur", "usd", session=cliente)
        self.assertEqual(resultado["valor_convertido"], Decimal("120.00"))
        self.assertEqual(resultado["date"], "2026-10-29")
        cliente.get.assert_called_once_with("https://api.frankfurter.dev/v2/rate/EUR/USD", timeout=10)

    def test_mesma_moeda(self):
        self.assertEqual(converter("25.50", "EUR", "EUR")["valor_convertido"], Decimal("25.50"))

    def test_valor_invalido(self):
        with self.assertRaises(ValueError):
            converter("abc", "EUR", "USD")

    def test_erro_api(self):
        cliente = Mock()
        cliente.get.side_effect = __import__('requests').Timeout()
        with self.assertRaises(CurrencyError):
            obter_taxa("EUR", "USD", session=cliente)

if __name__ == "__main__":
    unittest.main()
