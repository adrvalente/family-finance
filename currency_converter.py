"""Family Finance V3.6 — consulta e conversão de moedas via Frankfurter v2."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import requests

API_BASE = "https://api.frankfurter.dev/v2"

class CurrencyError(Exception):
    """Erro ao consultar ou interpretar uma taxa de câmbio."""


def obter_taxa(origem: str, destino: str, session=None) -> dict:
    origem, destino = origem.strip().upper(), destino.strip().upper()
    if not (len(origem) == len(destino) == 3 and origem.isalpha() and destino.isalpha()):
        raise ValueError("Utiliza códigos de moeda ISO de três letras (ex.: EUR, USD).")
    if origem == destino:
        return {"base": origem, "quote": destino, "rate": Decimal("1"), "date": None}
    cliente = session or requests
    try:
        resposta = cliente.get(f"{API_BASE}/rate/{origem}/{destino}", timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()
        taxa = Decimal(str(dados["rate"]))
        if not taxa.is_finite() or taxa <= 0:
            raise ValueError("Taxa inválida")
        return {"base": origem, "quote": destino, "rate": taxa, "date": dados.get("date")}
    except (requests.RequestException, ValueError, KeyError, TypeError, InvalidOperation) as erro:
        raise CurrencyError(f"Não foi possível obter a taxa {origem}/{destino}.") from erro


def converter(valor, origem: str, destino: str, session=None) -> dict:
    try:
        montante = Decimal(str(valor))
    except (InvalidOperation, ValueError) as erro:
        raise ValueError("O valor a converter deve ser numérico.") from erro
    if not montante.is_finite():
        raise ValueError("O valor deve ser finito.")
    info = obter_taxa(origem, destino, session=session)
    convertido = (montante * info["rate"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"valor_original": montante, "valor_convertido": convertido, **info}
