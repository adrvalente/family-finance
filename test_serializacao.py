"""Family Finance — Critério 17 (RVCC): classes e serialização JSON.

Execução: python test_serializacao.py
Testes:   python -m unittest test_serializacao -v
Não requer dependências externas nem ligação à base de dados.
"""

import json
import unittest
from dataclasses import asdict, dataclass


# EVIDÊNCIA 33 — Definição de classe e criação de objeto Python
@dataclass
class CenarioFinanceiro:
    """Representa um cenário financeiro simples do agregado familiar."""

    nome: str
    rendimento_mensal: float
    despesa_mensal: float
    moeda: str = "EUR"

    @property
    def saldo_mensal(self) -> float:
        return round(self.rendimento_mensal - self.despesa_mensal, 2)

    def para_json(self) -> str:
        """EVIDÊNCIA 34 — Serializa os atributos do objeto para JSON."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=4)

    @classmethod
    def de_json(cls, texto_json: str) -> "CenarioFinanceiro":
        """EVIDÊNCIA 34 — Desserializa JSON e reconstrói o objeto."""
        dados = json.loads(texto_json)
        if not isinstance(dados, dict):
            raise ValueError("O JSON deve representar um objeto.")
        return cls(**dados)


class TestSerializacao(unittest.TestCase):
    """Testes da serialização e desserialização de objetos."""

    def setUp(self) -> None:
        self.cenario = CenarioFinanceiro(
            nome="Orçamento Familiar",
            rendimento_mensal=2500.00,
            despesa_mensal=1750.50,
        )

    def test_criacao_objeto(self) -> None:
        self.assertEqual(self.cenario.nome, "Orçamento Familiar")
        self.assertEqual(self.cenario.saldo_mensal, 749.50)

    def test_serializacao_json(self) -> None:
        dados = json.loads(self.cenario.para_json())
        self.assertEqual(dados["nome"], "Orçamento Familiar")
        self.assertEqual(dados["moeda"], "EUR")

    def test_desserializacao_json(self) -> None:
        recuperado = CenarioFinanceiro.de_json(self.cenario.para_json())
        self.assertIsInstance(recuperado, CenarioFinanceiro)
        self.assertEqual(recuperado, self.cenario)

    def test_json_invalido(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            CenarioFinanceiro.de_json("{json inválido}")


def demonstracao() -> None:
    cenario = CenarioFinanceiro("Orçamento Familiar", 2500.00, 1750.50)
    print("=== EVIDÊNCIA 33 — Classe e objeto Python ===")
    print(f"Classe: {type(cenario).__name__}")
    print(f"Cenário: {cenario.nome}")
    print(f"Saldo mensal: {cenario.saldo_mensal:.2f} {cenario.moeda}")

    print("\n=== EVIDÊNCIA 34 — Serialização para JSON ===")
    texto_json = cenario.para_json()
    print(texto_json)

    print("\n=== EVIDÊNCIA 34 — Desserialização do JSON ===")
    recuperado = CenarioFinanceiro.de_json(texto_json)
    print(f"Objeto reconstruído: {recuperado}")
    print(f"Dados preservados: {recuperado == cenario}")


if __name__ == "__main__":
    demonstracao()
    print("\n=== Testes automáticos ===")
    unittest.main(argv=[__file__], verbosity=2)
