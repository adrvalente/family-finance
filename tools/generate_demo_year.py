#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Family Finance / RVCC APP - V3.1.1
Gerador de 12 meses completos de dados financeiros simulados.

Compatível com a estrutura atual do db.py (MySQL/MariaDB + PyMySQL).
Não altera o db.py.

Uso:
    python tools/generate_demo_year.py
    python tools/generate_demo_year.py --household-id 1
    python tools/generate_demo_year.py --reset
    python tools/generate_demo_year.py --seed 3101

Por omissão gera os 12 meses completos anteriores ao mês atual.
Ex.: executado em setembro/2026 -> setembro/2025 a agosto/2026.
"""

from __future__ import annotations

import argparse
import calendar
import random
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

# Permite executar o script dentro de app/tools/
APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from db import get_config  # noqa: E402
import pymysql  # noqa: E402


MARKER = "[V3.1.1-DEMO]"
LEGACY_MARKERS = ("[V3.1-DEMO]",)
DEFAULT_SEED = 3101


def norm(text: str | None) -> str:
    text = (text or "").strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def month_add(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def first_day_previous_month(today: date) -> date:
    return date(today.year, today.month, 1) - timedelta(days=1)


def demo_period(today: date) -> tuple[date, date]:
    last = first_day_previous_month(today)
    end = date(last.year, last.month, calendar.monthrange(last.year, last.month)[1])
    start_month = month_add(date(end.year, end.month, 1), -11)
    return start_month, end


def random_day(rng: random.Random, year: int, month: int, start=1, end=28) -> date:
    max_day = calendar.monthrange(year, month)[1]
    lo = max(1, start)
    hi = min(end, max_day)
    return date(year, month, rng.randint(lo, hi))


def money(value: float) -> float:
    return round(max(0.01, value), 2)


def table_columns(cur, table: str) -> set[str]:
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    return {row["Field"] for row in cur.fetchall()}


def table_exists(cur, table: str) -> bool:
    cur.execute("SHOW TABLES LIKE %s", (table,))
    return cur.fetchone() is not None


def pick_household(cur, requested_id: int | None) -> int:
    if requested_id:
        cur.execute(
            "SELECT id FROM households WHERE id=%s AND is_active=1 LIMIT 1",
            (requested_id,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Household #{requested_id} não existe ou está inativo.")
        return int(row["id"])

    cur.execute("SELECT id FROM households WHERE is_active=1 ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Não existe nenhum household ativo.")
    return int(row["id"])


def pick_user(cur, household_id: int) -> int:
    cur.execute(
        """
        SELECT u.id
        FROM users u
        INNER JOIN household_members hm
            ON hm.user_id=u.id AND hm.is_active=1
        WHERE hm.household_id=%s AND u.is_active=1
        ORDER BY CASE WHEN u.role='admin' THEN 0 ELSE 1 END, u.id
        LIMIT 1
        """,
        (household_id,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("O agregado selecionado não tem utilizadores ativos.")
    return int(row["id"])


def load_categories(cur, category_type: str) -> list[dict]:
    cur.execute(
        """
        SELECT id, name
        FROM categories
        WHERE type=%s AND is_active=1
        ORDER BY id
        """,
        (category_type,),
    )
    return list(cur.fetchall())


def category_id(categories: list[dict], aliases: list[str]) -> int:
    if not categories:
        raise RuntimeError("Não existem categorias ativas para este tipo.")

    normalized = [(int(c["id"]), norm(c["name"])) for c in categories]

    # 1) correspondência exata
    for alias in aliases:
        a = norm(alias)
        for cid, cname in normalized:
            if cname == a:
                return cid

    # 2) alias contido no nome / nome contido no alias
    for alias in aliases:
        a = norm(alias)
        for cid, cname in normalized:
            if a in cname or cname in a:
                return cid

    # fallback seguro
    return int(categories[0]["id"])


def insert_income(
    cur, household_id, category_id_, owner_user_id, description,
    amount, income_date, created_by
) -> int:
    cur.execute(
        """
        INSERT INTO incomes(
            household_id, category_id, owner_user_id, description, amount,
            income_date, recurrence_type, frequency, start_date, end_date,
            notes, created_by, is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,'one_time','none',NULL,NULL,%s,%s,1)
        """,
        (
            household_id, category_id_, owner_user_id, description,
            money(amount), income_date, MARKER, created_by,
        ),
    )
    income_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO income_occurrences(
            income_id, household_id, occurrence_date, amount, is_active
        )
        VALUES(%s,%s,%s,%s,1)
        """,
        (income_id, household_id, income_date, money(amount)),
    )
    return int(income_id)


def insert_expense(
    cur, household_id, category_id_, owner_user_id, supplier, description,
    amount, expense_date, payment_method, created_by
) -> int:
    cur.execute(
        """
        INSERT INTO expenses(
            household_id, category_id, owner_user_id, supplier, description,
            amount, expense_date, recurrence_type, frequency, start_date,
            end_date, payment_method, notes, created_by, is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,'one_time','none',NULL,NULL,%s,%s,%s,1)
        """,
        (
            household_id, category_id_, owner_user_id, supplier, description,
            money(amount), expense_date, payment_method, MARKER, created_by,
        ),
    )
    expense_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO expense_occurrences(
            expense_id, household_id, occurrence_date, amount, is_active
        )
        VALUES(%s,%s,%s,%s,1)
        """,
        (expense_id, household_id, expense_date, money(amount)),
    )
    return int(expense_id)


def reset_demo(cur, household_id: int) -> tuple[int, int]:
    markers = (MARKER,) + LEGACY_MARKERS
    placeholders_markers = ",".join(["%s"] * len(markers))

    cur.execute(
        f"SELECT id FROM expenses WHERE household_id=%s AND notes IN ({placeholders_markers})",
        (household_id, *markers),
    )
    expense_ids = [int(r["id"]) for r in cur.fetchall()]

    cur.execute(
        f"SELECT id FROM incomes WHERE household_id=%s AND notes IN ({placeholders_markers})",
        (household_id, *markers),
    )
    income_ids = [int(r["id"]) for r in cur.fetchall()]

    if expense_ids:
        placeholders = ",".join(["%s"] * len(expense_ids))
        cur.execute(
            f"DELETE FROM expense_occurrences WHERE expense_id IN ({placeholders})",
            tuple(expense_ids),
        )
        cur.execute(
            f"DELETE FROM expenses WHERE id IN ({placeholders})",
            tuple(expense_ids),
        )

    if income_ids:
        placeholders = ",".join(["%s"] * len(income_ids))
        cur.execute(
            f"DELETE FROM income_occurrences WHERE income_id IN ({placeholders})",
            tuple(income_ids),
        )
        cur.execute(
            f"DELETE FROM incomes WHERE id IN ({placeholders})",
            tuple(income_ids),
        )

    return len(income_ids), len(expense_ids)


def existing_demo(cur, household_id: int) -> bool:
    markers = (MARKER,) + LEGACY_MARKERS
    placeholders = ",".join(["%s"] * len(markers))
    cur.execute(
        f"SELECT COUNT(*) AS n FROM expenses WHERE household_id=%s AND notes IN ({placeholders})",
        (household_id, *markers),
    )
    return int(cur.fetchone()["n"]) > 0


def generate_year(cur, household_id: int, user_id: int, seed: int) -> dict:
    rng = random.Random(seed)
    start, end = demo_period(date.today())

    income_categories = load_categories(cur, "income")
    expense_categories = load_categories(cur, "expense")

    cat_salary = category_id(income_categories, ["Salário", "Salarios", "Rendimento", "Ordenado"])
    cat_other_income = category_id(income_categories, ["Outros", "Extra", "Prémios", "Premios"])

    cats = {
        "casa": category_id(expense_categories, ["Habitação", "Habitacao", "Casa", "Renda"]),
        "energia": category_id(expense_categories, ["Energia", "Eletricidade", "Electricidade"]),
        "agua": category_id(expense_categories, ["Água", "Agua"]),
        "telecom": category_id(expense_categories, ["Telecomunicações", "Telecomunicacoes", "Internet", "Comunicações"]),
        "supermercado": category_id(expense_categories, ["Alimentação", "Alimentacao", "Supermercado"]),
        "transporte": category_id(expense_categories, ["Transportes", "Transporte", "Combustível", "Combustivel"]),
        "restauracao": category_id(expense_categories, ["Restauração", "Restauracao", "Lazer", "Restaurantes"]),
        "saude": category_id(expense_categories, ["Saúde", "Saude", "Farmácia", "Farmacia"]),
        "educacao": category_id(expense_categories, ["Educação", "Educacao", "Formação", "Formacao"]),
        "seguros": category_id(expense_categories, ["Seguros", "Seguro"]),
        "subscricoes": category_id(expense_categories, ["Subscrições", "Subscricoes", "Streaming"]),
        "outros": category_id(expense_categories, ["Outros", "Diversos"]),
    }

    counts = {"incomes": 0, "expenses": 0}
    totals = {"income": 0.0, "expense": 0.0}

    month = start
    month_index = 0

    while month <= end:
        y, m = month.year, month.month

        # ---------------------------
        # RENDIMENTOS
        # ---------------------------
        salary_a = money(2350 + rng.uniform(-25, 35))
        salary_b = money(1550 + rng.uniform(-20, 30))

        for desc, amount, day in [
            ("Salário A", salary_a, min(28, calendar.monthrange(y, m)[1])),
            ("Salário B", salary_b, min(25, calendar.monthrange(y, m)[1])),
        ]:
            insert_income(
                cur, household_id, cat_salary, user_id, desc,
                amount, date(y, m, day), user_id
            )
            counts["incomes"] += 1
            totals["income"] += amount

        # Subsídio de férias / Natal para tornar o histórico mais realista
        if m in (6, 11):
            extra = money(850 + rng.uniform(-50, 80))
            insert_income(
                cur, household_id, cat_other_income, user_id,
                "Rendimento extraordinário", extra,
                random_day(rng, y, m, 10, 24), user_id
            )
            counts["incomes"] += 1
            totals["income"] += extra

        # ---------------------------
        # DESPESAS FIXAS / SERVIÇOS
        # ---------------------------
        fixed = [
            ("Banco Habitação", "Prestação da habitação", 850.00, 2, "Débito direto", cats["casa"]),
            ("Operador Telecom", "Internet + TV + telemóveis",
             64.90 if month_index < 7 else 69.90, 8, "Débito direto", cats["telecom"]),
            ("Streaming", "Serviços digitais", 19.98, 12, "Cartão", cats["subscricoes"]),
        ]

        for supplier, desc, amount, day, payment, cat in fixed:
            insert_expense(
                cur, household_id, cat, user_id, supplier, desc,
                amount, date(y, m, min(day, calendar.monthrange(y, m)[1])),
                payment, user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        # Energia: sobe no inverno e tem aumento de preço no último terço do período
        winter_factor = 1.35 if m in (12, 1, 2) else (1.12 if m in (3, 11) else 0.88)
        tariff_factor = 1.08 if month_index >= 8 else 1.0
        energy = money((92 + rng.uniform(-15, 18)) * winter_factor * tariff_factor)
        insert_expense(
            cur, household_id, cats["energia"], user_id,
            "Fornecedor Energia", "Eletricidade", energy,
            random_day(rng, y, m, 10, 18), "Débito direto", user_id
        )
        counts["expenses"] += 1
        totals["expense"] += energy

        # Água bimestral
        if month_index % 2 == 0:
            water = money(46 + rng.uniform(-6, 9))
            insert_expense(
                cur, household_id, cats["agua"], user_id,
                "Águas Municipais", "Fatura de água", water,
                random_day(rng, y, m, 8, 18), "Débito direto", user_id
            )
            counts["expenses"] += 1
            totals["expense"] += water

        # ---------------------------
        # DESPESAS VARIÁVEIS
        # ---------------------------
        # Supermercado: 4-6 compras/mês
        for _ in range(rng.randint(4, 6)):
            amount = money(rng.uniform(48, 112))
            insert_expense(
                cur, household_id, cats["supermercado"], user_id,
                rng.choice(["Continente", "Pingo Doce", "Lidl", "Mercadona"]),
                "Compras de supermercado", amount,
                random_day(rng, y, m, 2, 27), rng.choice(["Cartão", "MB WAY"]), user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        # Combustível: 2-3 vezes/mês
        for _ in range(rng.randint(2, 3)):
            amount = money(rng.uniform(55, 78))
            insert_expense(
                cur, household_id, cats["transporte"], user_id,
                rng.choice(["Galp", "BP", "Repsol"]),
                "Combustível", amount,
                random_day(rng, y, m, 2, 27), "Cartão", user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        # Restauração/lazer: 1-3 vezes/mês
        for _ in range(rng.randint(1, 3)):
            amount = money(rng.uniform(24, 62))
            insert_expense(
                cur, household_id, cats["restauracao"], user_id,
                rng.choice(["Restaurante local", "Take-away", "Café"]),
                "Restauração / lazer", amount,
                random_day(rng, y, m, 2, 27), rng.choice(["Cartão", "MB WAY"]), user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        # Saúde aleatória
        if rng.random() < 0.55:
            amount = money(rng.uniform(15, 75))
            insert_expense(
                cur, household_id, cats["saude"], user_id,
                rng.choice(["Farmácia", "Clínica"]),
                "Saúde", amount, random_day(rng, y, m, 3, 26),
                "Cartão", user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        # Educação/formação trimestral
        if month_index in (1, 4, 7, 10):
            amount = money(rng.uniform(65, 140))
            insert_expense(
                cur, household_id, cats["educacao"], user_id,
                "Formação", "Material / formação", amount,
                random_day(rng, y, m, 4, 20), "Transferência", user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        # Seguro automóvel anual
        if month_index == 3:
            amount = 328.40
            insert_expense(
                cur, household_id, cats["seguros"], user_id,
                "Seguradora", "Seguro automóvel anual", amount,
                random_day(rng, y, m, 5, 15), "Débito direto", user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        # Despesa inesperada para criar anomalia detetável
        if month_index == 6:
            amount = 465.00
            insert_expense(
                cur, household_id, cats["outros"], user_id,
                "Oficina", "Reparação automóvel inesperada", amount,
                random_day(rng, y, m, 8, 20), "Cartão", user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        # Férias/verão: despesa pontual adicional
        if m in (7, 8):
            amount = money(rng.uniform(180, 320))
            insert_expense(
                cur, household_id, cats["restauracao"], user_id,
                "Férias / lazer", "Despesa sazonal de verão", amount,
                random_day(rng, y, m, 5, 24), "Cartão", user_id
            )
            counts["expenses"] += 1
            totals["expense"] += amount

        month = month_add(month, 1)
        month_index += 1

    return {
        "start": start,
        "end": end,
        "counts": counts,
        "totals": {k: money(v) for k, v in totals.items()},
        "balance": money(totals["income"] - totals["expense"]),
    }


def print_summary(household_id: int, user_id: int, result: dict) -> None:
    print("\n" + "=" * 66)
    print(" RVCC APP / FAMILY FINANCE — V3.1.1")
    print(" Dados simulados de 1 ano gerados com sucesso")
    print("=" * 66)
    print(f" Household:          #{household_id}")
    print(f" Utilizador:         #{user_id}")
    print(f" Período:            {result['start']} -> {result['end']}")
    print(f" Rendimentos:        {result['counts']['incomes']} registos")
    print(f" Despesas:           {result['counts']['expenses']} registos")
    print(f" Total rendimentos:  {result['totals']['income']:.2f} EUR")
    print(f" Total despesas:     {result['totals']['expense']:.2f} EUR")
    print(f" Saldo simulado:     {result['balance']:.2f} EUR")
    print("=" * 66)
    print("Cenários incluídos:")
    print(" - 12 meses completos de histórico")
    print(" - salários mensais + rendimentos extraordinários")
    print(" - habitação, telecom, streaming, energia e água")
    print(" - supermercado, combustível, restauração, saúde e formação")
    print(" - sazonalidade de energia")
    print(" - aumento de preço de telecom")
    print(" - aumento de tarifa de energia")
    print(" - seguro anual")
    print(" - reparação automóvel inesperada / anomalia")
    print(" - aumento de despesas no verão")
    print("=" * 66)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera 12 meses completos de dados simulados para a V3.1.1."
    )
    parser.add_argument("--household-id", type=int, default=None)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Apaga primeiro apenas os dados criados por este gerador.",
    )
    args = parser.parse_args()

    cfg = get_config().copy()
    cfg["autocommit"] = False

    conn = pymysql.connect(**cfg)
    try:
        with conn.cursor() as cur:
            required = [
                "households", "users", "household_members", "categories",
                "incomes", "income_occurrences", "expenses", "expense_occurrences",
            ]
            missing = [t for t in required if not table_exists(cur, t)]
            if missing:
                raise RuntimeError(
                    "Faltam tabelas necessárias: " + ", ".join(missing)
                )

            household_id = pick_household(cur, args.household_id)
            user_id = pick_user(cur, household_id)

            if args.reset:
                inc, exp = reset_demo(cur, household_id)
                print(f"Reset V3.1.1: removidos {inc} rendimentos e {exp} despesas.")

            if existing_demo(cur, household_id):
                raise RuntimeError(
                    "Já existem dados V3.1.1-DEMO neste agregado. "
                    "Use --reset para os substituir."
                )

            result = generate_year(cur, household_id, user_id, args.seed)
            conn.commit()
            print_summary(household_id, user_id, result)

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
