"""Persistência isolada das taxas de câmbio; usa a ligação existente do db.py."""
from datetime import date
from decimal import Decimal
from db import fetch_one, execute


def guardar_taxa(info: dict) -> None:
    """Guarda uma cotação datada. A operação pode ser repetida sem duplicar registos."""
    origem = info['base'].upper()
    destino = info['quote'].upper()
    data_cotacao = info['date']
    taxa = Decimal(str(info['rate']))
    if not all(len(m) == 3 and m.isalpha() for m in (origem, destino)):
        raise ValueError('Código de moeda inválido')
    if not data_cotacao:
        raise ValueError('A API não forneceu uma data de cotação')
    date.fromisoformat(str(data_cotacao))
    if not taxa.is_finite() or taxa <= 0:
        raise ValueError('Taxa inválida')
    execute('''
        INSERT INTO taxas_cambio
          (moeda_origem, moeda_destino, data_cotacao, taxa, fonte)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE taxa = VALUES(taxa), consultado_em = CURRENT_TIMESTAMP
    ''', (origem, destino, data_cotacao, str(taxa), 'Frankfurter'))


def obter_ultima_taxa(origem: str, destino: str):
    """Devolve a cotação mais recente guardada, ou None."""
    return fetch_one('''
        SELECT moeda_origem, moeda_destino, data_cotacao, taxa, fonte, consultado_em
        FROM taxas_cambio
        WHERE moeda_origem = %s AND moeda_destino = %s
        ORDER BY data_cotacao DESC LIMIT 1
    ''', (origem.upper(), destino.upper()))
