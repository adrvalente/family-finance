import os
import json
from contextlib import contextmanager
from datetime import date, timedelta

import pymysql
from dotenv import load_dotenv


# ==========================================================
# FAMILY FINANCE
# Configuração de Base de Dados
#
# Local / VM:
#   .env -> MariaDB local
#
# Streamlit Community Cloud:
#   st.secrets["database"] -> Aiven MySQL
# ==========================================================

# ==========================================================
# FAMILY FINANCE V3.3.3
# Database Environment Manager
#
# FF_DATABASE_MODE:
#   local -> força .env / MariaDB local
#   cloud -> força Streamlit Secrets / Aiven
#   auto  -> Cloud se existirem secrets; caso contrário Local
# ==========================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))


def _database_mode():
    """
    Devolve o modo de base de dados solicitado.

    Valores válidos:
        local
        cloud
        auto

    Por defeito usa 'auto'.
    """
    mode = os.getenv("FF_DATABASE_MODE", "auto").strip().lower()

    if mode not in ("local", "cloud", "auto"):
        mode = "auto"

    return mode


def _streamlit_database_config():
    """
    Obtém a configuração Cloud através de Streamlit Secrets.
    Nunca expõe credenciais.
    """
    try:
        import streamlit as st

        if "database" not in st.secrets:
            return None

        db = st.secrets["database"]

        required = ("host", "port", "user", "password", "name")

        if not all(key in db for key in required):
            return None

        return {
            "host": str(db["host"]),
            "port": int(db["port"]),
            "user": str(db["user"]),
            "password": str(db["password"]),
            "database": str(db["name"]),
            "ssl": {
                "check_hostname": True
            },
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "autocommit": True,
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
        }

    except Exception:
        return None


def _local_database_config():
    """
    Configuração da MariaDB local através de .env.
    """
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "family_app"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "family_finance"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    }


def get_database_environment():
    """
    Informação segura sobre o ambiente atualmente selecionado.

    Pode ser usada na página Sistema sem revelar
    passwords, hosts ou utilizadores.
    """
    mode = _database_mode()
    cloud_config = _streamlit_database_config()

    if mode == "local":
        return "LOCAL"

    if mode == "cloud":
        return "CLOUD"

    # AUTO
    return "CLOUD" if cloud_config else "LOCAL"


def get_config():
    """
    Resolve a configuração efetiva da BD.

    LOCAL:
        força .env / MariaDB.

    CLOUD:
        exige [database] em Streamlit Secrets.

    AUTO:
        prefere Streamlit Secrets e usa .env como fallback.
    """
    mode = _database_mode()

    if mode == "local":
        return _local_database_config()

    cloud_config = _streamlit_database_config()

    if mode == "cloud":
        if not cloud_config:
            raise RuntimeError(
                "FF_DATABASE_MODE=cloud, mas não existe uma configuração "
                "[database] válida em Streamlit Secrets."
            )

        return cloud_config

    # AUTO
    if cloud_config:
        return cloud_config

    return _local_database_config()# ==========================================================
# FAMILY FINANCE V3.3.3
# Database Environment Manager
#
# FF_DATABASE_MODE:
#   local -> força .env / MariaDB local
#   cloud -> força Streamlit Secrets / Aiven
#   auto  -> Cloud se existirem secrets; caso contrário Local
# ==========================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))


@contextmanager
def connection():
    conn = pymysql.connect(**get_config())

    try:
        yield conn
    finally:
        conn.close()


def fetch_one(sql, params=None):
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()


def fetch_all(sql, params=None):
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


def execute(sql, params=None):
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid


def test_connection():
    return fetch_one("""
        SELECT
            VERSION() AS version,
            DATABASE() AS db_name
    """)

def get_categories():
    return fetch_all("""
        SELECT id, name, type, is_active
        FROM categories
        ORDER BY type, name
    """)

def get_income_categories():
    return fetch_all("""
        SELECT id, name
        FROM categories
        WHERE type='income' AND is_active=1
        ORDER BY name
    """)

def get_system_stats():
    return {
        "categories": fetch_one("SELECT COUNT(*) AS n FROM categories WHERE is_active=1")["n"],
        "settings": fetch_one("SELECT COUNT(*) AS n FROM app_settings")["n"],
        "migrations": fetch_one("SELECT COUNT(*) AS n FROM schema_migrations")["n"],
        "users": fetch_one("SELECT COUNT(*) AS n FROM users WHERE is_active=1")["n"],
        "households": fetch_one("SELECT COUNT(*) AS n FROM households WHERE is_active=1")["n"],
        "incomes": fetch_one("SELECT COUNT(*) AS n FROM incomes WHERE is_active=1")["n"],
        "expenses": fetch_one("SELECT COUNT(*) AS n FROM expenses WHERE is_active=1")["n"],
        "documents": fetch_one("SELECT COUNT(*) AS n FROM documents WHERE is_active=1")["n"],
    }

def get_user_by_username(username):
    return fetch_one("""
        SELECT u.id,u.username,u.full_name,u.email,u.password_hash,u.role,
               u.is_active,u.must_change_password,
               hm.household_id,h.name AS household_name
        FROM users u
        LEFT JOIN household_members hm
          ON hm.user_id=u.id AND hm.is_active=1
        LEFT JOIN households h ON h.id=hm.household_id
        WHERE u.username=%s
        LIMIT 1
    """, (username,))

def update_last_login(user_id):
    execute("UPDATE users SET last_login_at=NOW() WHERE id=%s", (user_id,))

def update_password(user_id, password_hash):
    execute("""
        UPDATE users
        SET password_hash=%s,must_change_password=0,updated_at=NOW()
        WHERE id=%s
    """, (password_hash, user_id))

def list_users():
    return fetch_all("""
        SELECT u.id,u.username,u.full_name,u.email,u.role,u.is_active,
               u.last_login_at,h.name AS household_name
        FROM users u
        LEFT JOIN household_members hm
          ON hm.user_id=u.id AND hm.is_active=1
        LEFT JOIN households h ON h.id=hm.household_id
        ORDER BY u.full_name,u.username
    """)

def list_users_by_household(household_id):
    return fetch_all("""
        SELECT u.id, u.full_name, u.username
        FROM users u
        INNER JOIN household_members hm
            ON hm.user_id=u.id AND hm.is_active=1
        WHERE hm.household_id=%s AND u.is_active=1
        ORDER BY u.full_name
    """, (household_id,))

def list_households():
    return fetch_all("""
        SELECT id,name
        FROM households
        WHERE is_active=1
        ORDER BY name
    """)

def create_user(username, full_name, email, password_hash, role, household_id=None):
    user_id = execute("""
        INSERT INTO users
            (username,full_name,email,password_hash,role,is_active,must_change_password)
        VALUES (%s,%s,%s,%s,%s,1,1)
    """, (username,full_name,email,password_hash,role))

    if household_id:
        execute("""
            INSERT INTO household_members
                (household_id,user_id,member_role,is_active)
            VALUES (%s,%s,%s,1)
        """, (household_id,user_id,"owner" if role=="admin" else "member"))

    return user_id

def set_user_active(user_id, active):
    execute("""
        UPDATE users SET is_active=%s,updated_at=NOW()
        WHERE id=%s
    """, (1 if active else 0,user_id))

def create_household(name, created_by):
    return execute("""
        INSERT INTO households(name,created_by,is_active)
        VALUES(%s,%s,1)
    """, (name,created_by))

def assign_user_to_household(user_id, household_id, member_role="member"):
    execute("UPDATE household_members SET is_active=0 WHERE user_id=%s",(user_id,))
    execute("""
        INSERT INTO household_members(household_id,user_id,member_role,is_active)
        VALUES(%s,%s,%s,1)
    """,(household_id,user_id,member_role))

def log_action(user_id, action, entity_type=None, entity_id=None, details=None):
    execute("""
        INSERT INTO audit_log(user_id,action,entity_type,entity_id,details)
        VALUES(%s,%s,%s,%s,%s)
    """,(user_id,action,entity_type,entity_id,details))

# ------------------------------
# Rendimentos - V1.2
# ------------------------------

def create_income(
    household_id, category_id, owner_user_id, description, amount,
    income_date, recurrence_type, frequency, start_date, end_date,
    notes, created_by
):
    return execute("""
        INSERT INTO incomes(
            household_id, category_id, owner_user_id, description, amount,
            income_date, recurrence_type, frequency, start_date, end_date,
            notes, created_by, is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
    """, (
        household_id, category_id, owner_user_id, description, amount,
        income_date, recurrence_type, frequency, start_date, end_date,
        notes, created_by
    ))

def list_incomes(household_id):
    return fetch_all("""
        SELECT
            i.id,
            i.description,
            i.amount,
            i.income_date,
            i.recurrence_type,
            i.frequency,
            i.start_date,
            i.end_date,
            i.notes,
            i.is_active,
            c.name AS category_name,
            u.full_name AS owner_name,
            creator.full_name AS created_by_name,
            i.created_at
        FROM incomes i
        INNER JOIN categories c ON c.id=i.category_id
        LEFT JOIN users u ON u.id=i.owner_user_id
        LEFT JOIN users creator ON creator.id=i.created_by
        WHERE i.household_id=%s
        ORDER BY COALESCE(i.income_date, i.start_date) DESC, i.id DESC
    """, (household_id,))

def set_income_active(income_id, household_id, active):
    execute("""
        UPDATE incomes
        SET is_active=%s, updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (1 if active else 0, income_id, household_id))

def delete_income(income_id, household_id):
    execute("""
        DELETE FROM incomes
        WHERE id=%s AND household_id=%s
    """, (income_id, household_id))

def get_income_by_id(income_id, household_id):
    return fetch_one("""
        SELECT *
        FROM incomes
        WHERE id=%s AND household_id=%s
        LIMIT 1
    """, (income_id, household_id))

def update_income(
    income_id, household_id, category_id, owner_user_id, description, amount,
    income_date, recurrence_type, frequency, start_date, end_date, notes
):
    execute("""
        UPDATE incomes
        SET category_id=%s,
            owner_user_id=%s,
            description=%s,
            amount=%s,
            income_date=%s,
            recurrence_type=%s,
            frequency=%s,
            start_date=%s,
            end_date=%s,
            notes=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (
        category_id, owner_user_id, description, amount,
        income_date, recurrence_type, frequency, start_date, end_date,
        notes, income_id, household_id
    ))

def get_monthly_income_total(household_id, year, month):
    result = fetch_one("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM income_occurrences
        WHERE household_id=%s
          AND YEAR(occurrence_date)=%s
          AND MONTH(occurrence_date)=%s
          AND is_active=1
    """, (household_id, year, month))
    return float(result["total"] or 0)

def list_income_occurrences(household_id, year=None, month=None):
    sql = """
        SELECT
            io.id,
            io.income_id,
            io.occurrence_date,
            io.amount,
            io.is_active,
            i.description,
            c.name AS category_name,
            u.full_name AS owner_name
        FROM income_occurrences io
        INNER JOIN incomes i ON i.id=io.income_id
        INNER JOIN categories c ON c.id=i.category_id
        LEFT JOIN users u ON u.id=i.owner_user_id
        WHERE io.household_id=%s
    """
    params = [household_id]

    if year is not None:
        sql += " AND YEAR(io.occurrence_date)=%s"
        params.append(year)

    if month is not None:
        sql += " AND MONTH(io.occurrence_date)=%s"
        params.append(month)

    sql += " ORDER BY io.occurrence_date DESC, io.id DESC"
    return fetch_all(sql, tuple(params))

def get_income_history_monthly(household_id, limit_months=12):
    return fetch_all("""
        SELECT
            DATE_FORMAT(occurrence_date, '%%Y-%%m') AS month_key,
            YEAR(occurrence_date) AS year_num,
            MONTH(occurrence_date) AS month_num,
            SUM(amount) AS total
        FROM income_occurrences
        WHERE household_id=%s AND is_active=1
        GROUP BY
            DATE_FORMAT(occurrence_date, '%%Y-%%m'),
            YEAR(occurrence_date),
            MONTH(occurrence_date)
        ORDER BY
            year_num DESC,
            month_num DESC
        LIMIT %s
    """, (household_id, limit_months))

def rebuild_income_occurrences(income_id, household_id):
    income = get_income_by_id(income_id, household_id)
    if not income:
        return

    execute("DELETE FROM income_occurrences WHERE income_id=%s", (income_id,))

    from datetime import date
    from calendar import monthrange

    if income["recurrence_type"] == "one_time":
        occurrence_date = income["income_date"] or income["start_date"]
        if occurrence_date:
            execute("""
                INSERT INTO income_occurrences(
                    income_id, household_id, occurrence_date, amount, is_active
                )
                VALUES(%s,%s,%s,%s,1)
            """, (income_id, household_id, occurrence_date, income["amount"]))
        return

    start = income["start_date"] or income["income_date"]
    if not start:
        return

    end = income["end_date"] or date(start.year + 5, start.month, min(start.day, 28))
    current = start
    freq = income["frequency"]

    def add_months(d, months):
        month = d.month - 1 + months
        year = d.year + month // 12
        month = month % 12 + 1
        day = min(d.day, monthrange(year, month)[1])
        return date(year, month, day)

    while current <= end:
        execute("""
            INSERT INTO income_occurrences(
                income_id, household_id, occurrence_date, amount, is_active
            )
            VALUES(%s,%s,%s,%s,1)
        """, (income_id, household_id, current, income["amount"]))

        if freq == "monthly":
            current = add_months(current, 1)
        elif freq == "quarterly":
            current = add_months(current, 3)
        elif freq == "semiannual":
            current = add_months(current, 6)
        elif freq == "annual":
            current = add_months(current, 12)
        else:
            break


# ------------------------------
# Despesas - V1.3
# ------------------------------

def get_expense_categories():
    return fetch_all("""
        SELECT id, name
        FROM categories
        WHERE type='expense' AND is_active=1
        ORDER BY name
    """)

def create_expense(
    household_id, category_id, owner_user_id, supplier, description, amount,
    expense_date, recurrence_type, frequency, start_date, end_date,
    payment_method, notes, created_by
):
    return execute("""
        INSERT INTO expenses(
            household_id, category_id, owner_user_id, supplier, description,
            amount, expense_date, recurrence_type, frequency, start_date,
            end_date, payment_method, notes, created_by, is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
    """, (
        household_id, category_id, owner_user_id, supplier, description,
        amount, expense_date, recurrence_type, frequency, start_date,
        end_date, payment_method, notes, created_by
    ))

def list_expenses(household_id):
    return fetch_all("""
        SELECT
            e.id,
            e.supplier,
            e.description,
            e.amount,
            e.expense_date,
            e.recurrence_type,
            e.frequency,
            e.start_date,
            e.end_date,
            e.payment_method,
            e.notes,
            e.is_active,
            c.name AS category_name,
            u.full_name AS owner_name,
            creator.full_name AS created_by_name,
            e.created_at
        FROM expenses e
        INNER JOIN categories c ON c.id=e.category_id
        LEFT JOIN users u ON u.id=e.owner_user_id
        LEFT JOIN users creator ON creator.id=e.created_by
        WHERE e.household_id=%s
        ORDER BY COALESCE(e.expense_date, e.start_date) DESC, e.id DESC
    """, (household_id,))

def get_expense_by_id(expense_id, household_id):
    return fetch_one("""
        SELECT *
        FROM expenses
        WHERE id=%s AND household_id=%s
        LIMIT 1
    """, (expense_id, household_id))

def update_expense(
    expense_id, household_id, category_id, owner_user_id, supplier,
    description, amount, expense_date, recurrence_type, frequency,
    start_date, end_date, payment_method, notes
):
    execute("""
        UPDATE expenses
        SET category_id=%s,
            owner_user_id=%s,
            supplier=%s,
            description=%s,
            amount=%s,
            expense_date=%s,
            recurrence_type=%s,
            frequency=%s,
            start_date=%s,
            end_date=%s,
            payment_method=%s,
            notes=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (
        category_id, owner_user_id, supplier, description, amount,
        expense_date, recurrence_type, frequency, start_date, end_date,
        payment_method, notes, expense_id, household_id
    ))

def set_expense_active(expense_id, household_id, active):
    execute("""
        UPDATE expenses
        SET is_active=%s, updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (1 if active else 0, expense_id, household_id))

def delete_expense(expense_id, household_id):
    execute("""
        DELETE FROM expenses
        WHERE id=%s AND household_id=%s
    """, (expense_id, household_id))

def rebuild_expense_occurrences(expense_id, household_id):
    expense = get_expense_by_id(expense_id, household_id)
    if not expense:
        return

    execute("DELETE FROM expense_occurrences WHERE expense_id=%s", (expense_id,))

    from datetime import date
    from calendar import monthrange

    if expense["recurrence_type"] == "one_time":
        occurrence_date = expense["expense_date"] or expense["start_date"]
        if occurrence_date:
            execute("""
                INSERT INTO expense_occurrences(
                    expense_id, household_id, occurrence_date, amount, is_active
                )
                VALUES(%s,%s,%s,%s,1)
            """, (expense_id, household_id, occurrence_date, expense["amount"]))
        return

    start = expense["start_date"] or expense["expense_date"]
    if not start:
        return

    end = expense["end_date"] or date(start.year + 5, start.month, min(start.day, 28))
    current = start
    freq = expense["frequency"]

    def add_months(d, months):
        month = d.month - 1 + months
        year = d.year + month // 12
        month = month % 12 + 1
        day = min(d.day, monthrange(year, month)[1])
        return date(year, month, day)

    while current <= end:
        execute("""
            INSERT INTO expense_occurrences(
                expense_id, household_id, occurrence_date, amount, is_active
            )
            VALUES(%s,%s,%s,%s,1)
        """, (expense_id, household_id, current, expense["amount"]))

        if freq == "monthly":
            current = add_months(current, 1)
        elif freq == "quarterly":
            current = add_months(current, 3)
        elif freq == "semiannual":
            current = add_months(current, 6)
        elif freq == "annual":
            current = add_months(current, 12)
        else:
            break

def get_monthly_expense_total(household_id, year, month):
    result = fetch_one("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM expense_occurrences
        WHERE household_id=%s
          AND YEAR(occurrence_date)=%s
          AND MONTH(occurrence_date)=%s
          AND is_active=1
    """, (household_id, year, month))
    return float(result["total"] or 0)

def list_expense_occurrences(household_id, year=None, month=None):
    sql = """
        SELECT
            eo.id,
            eo.expense_id,
            eo.occurrence_date,
            eo.amount,
            eo.is_active,
            e.supplier,
            e.description,
            e.payment_method,
            c.name AS category_name,
            u.full_name AS owner_name
        FROM expense_occurrences eo
        INNER JOIN expenses e ON e.id=eo.expense_id
        INNER JOIN categories c ON c.id=e.category_id
        LEFT JOIN users u ON u.id=e.owner_user_id
        WHERE eo.household_id=%s
    """
    params = [household_id]

    if year is not None:
        sql += " AND YEAR(eo.occurrence_date)=%s"
        params.append(year)

    if month is not None:
        sql += " AND MONTH(eo.occurrence_date)=%s"
        params.append(month)

    sql += " ORDER BY eo.occurrence_date DESC, eo.id DESC"
    return fetch_all(sql, tuple(params))

def get_expense_history_monthly(household_id, limit_months=12):
    return fetch_all("""
        SELECT
            YEAR(occurrence_date) AS year_num,
            MONTH(occurrence_date) AS month_num,
            SUM(amount) AS total
        FROM expense_occurrences
        WHERE household_id=%s AND is_active=1
        GROUP BY YEAR(occurrence_date), MONTH(occurrence_date)
        ORDER BY YEAR(occurrence_date) DESC, MONTH(occurrence_date) DESC
        LIMIT %s
    """, (household_id, limit_months))

def get_expenses_by_category(household_id, year, month):
    return fetch_all("""
        SELECT c.name AS category_name, SUM(eo.amount) AS total
        FROM expense_occurrences eo
        INNER JOIN expenses e ON e.id=eo.expense_id
        INNER JOIN categories c ON c.id=e.category_id
        WHERE eo.household_id=%s
          AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s
          AND eo.is_active=1
        GROUP BY c.id, c.name
        ORDER BY total DESC
    """, (household_id, year, month))

# ------------------------------
# Dashboard Financeiro Avançado - V1.4
# ------------------------------
def get_previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)

def get_top_expense_categories(household_id, year, month, limit_rows=5):
    return fetch_all("""
        SELECT c.name AS category_name, SUM(eo.amount) AS total
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        JOIN categories c ON c.id=e.category_id
        WHERE eo.household_id=%s
          AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s
          AND eo.is_active=1
        GROUP BY c.id,c.name
        ORDER BY total DESC
        LIMIT %s
    """,(household_id,year,month,limit_rows))

def get_top_suppliers(household_id, year, month, limit_rows=5):
    return fetch_all("""
        SELECT COALESCE(NULLIF(TRIM(e.supplier),''),'Sem fornecedor') AS supplier,
               SUM(eo.amount) AS total, COUNT(*) AS occurrences
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        WHERE eo.household_id=%s
          AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s
          AND eo.is_active=1
        GROUP BY COALESCE(NULLIF(TRIM(e.supplier),''),'Sem fornecedor')
        ORDER BY total DESC
        LIMIT %s
    """,(household_id,year,month,limit_rows))

def get_fixed_variable_expenses(household_id, year, month):
    return fetch_all("""
        SELECT CASE WHEN e.recurrence_type='recurring' THEN 'Fixa' ELSE 'Variável' END AS expense_kind,
               SUM(eo.amount) AS total
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        WHERE eo.household_id=%s
          AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s
          AND eo.is_active=1
        GROUP BY expense_kind
        ORDER BY total DESC
    """,(household_id,year,month))

def get_month_summary(household_id, year, month):
    income=get_monthly_income_total(household_id,year,month)
    expense=get_monthly_expense_total(household_id,year,month)
    balance=income-expense
    return {
        "income":income,
        "expense":expense,
        "balance":balance,
        "savings_rate":(balance/income*100) if income>0 else 0,
        "expense_weight":(expense/income*100) if income>0 else 0
    }

def get_month_comparison(household_id, year, month):
    py,pm=get_previous_month(year,month)
    cur=get_month_summary(household_id,year,month)
    prev=get_month_summary(household_id,py,pm)
    def pct(a,b):
        return None if b==0 else ((a-b)/b)*100
    return {
        "current":cur,"previous":prev,
        "previous_year":py,"previous_month":pm,
        "income_change_pct":pct(cur["income"],prev["income"]),
        "expense_change_pct":pct(cur["expense"],prev["expense"]),
        "balance_change_pct":pct(cur["balance"],prev["balance"])
    }

def get_financial_history(household_id, months=12):
    inc=get_income_history_monthly(household_id,months)
    exp=get_expense_history_monthly(household_id,months)
    merged={}
    for r in inc:
        k=(int(r["year_num"]),int(r["month_num"]))
        merged.setdefault(k,{"income":0.0,"expense":0.0})
        merged[k]["income"]=float(r["total"])
    for r in exp:
        k=(int(r["year_num"]),int(r["month_num"]))
        merged.setdefault(k,{"income":0.0,"expense":0.0})
        merged[k]["expense"]=float(r["total"])
    out=[]
    for (y,m),v in sorted(merged.items()):
        out.append({"year_num":y,"month_num":m,"income":v["income"],"expense":v["expense"],"balance":v["income"]-v["expense"]})
    return out[-months:]


# ------------------------------
# Documentos - V1.5
# ------------------------------

def create_document(
    household_id, uploaded_by, original_name, stored_name, storage_path,
    mime_type, file_extension, file_size, document_type,
    expense_id=None, notes=None, processing_status="uploaded"
):
    return execute("""
        INSERT INTO documents(
            household_id, uploaded_by, expense_id,
            original_name, stored_name, storage_path,
            mime_type, file_extension, file_size,
            document_type, processing_status, notes, is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
    """, (
        household_id, uploaded_by, expense_id,
        original_name, stored_name, storage_path,
        mime_type, file_extension, file_size,
        document_type, processing_status, notes
    ))

def list_documents(household_id):
    return fetch_all("""
        SELECT
            d.id,
            d.household_id,
            d.expense_id,
            d.original_name,
            d.stored_name,
            d.storage_path,
            d.mime_type,
            d.file_extension,
            d.file_size,
            d.document_type,
            d.processing_status,
            d.ocr_status,
            d.ocr_text,
            d.notes,
            d.is_active,
            d.created_at,
            u.full_name AS uploaded_by_name,
            e.description AS expense_description,
            e.supplier AS expense_supplier,
            e.amount AS expense_amount
        FROM documents d
        LEFT JOIN users u ON u.id=d.uploaded_by
        LEFT JOIN expenses e ON e.id=d.expense_id
        WHERE d.household_id=%s
        ORDER BY d.created_at DESC, d.id DESC
    """, (household_id,))

def get_document_by_id(document_id, household_id):
    return fetch_one("""
        SELECT
            d.*,
            u.full_name AS uploaded_by_name,
            e.description AS expense_description,
            e.supplier AS expense_supplier,
            e.amount AS expense_amount
        FROM documents d
        LEFT JOIN users u ON u.id=d.uploaded_by
        LEFT JOIN expenses e ON e.id=d.expense_id
        WHERE d.id=%s AND d.household_id=%s
        LIMIT 1
    """, (document_id, household_id))

def update_document_link(document_id, household_id, expense_id):
    execute("""
        UPDATE documents
        SET expense_id=%s, updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (expense_id, document_id, household_id))

def update_document_notes(document_id, household_id, notes):
    execute("""
        UPDATE documents
        SET notes=%s, updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (notes, document_id, household_id))

def update_document_processing(document_id, household_id, processing_status, ocr_status=None):
    execute("""
        UPDATE documents
        SET processing_status=%s,
            ocr_status=COALESCE(%s,ocr_status),
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (processing_status, ocr_status, document_id, household_id))

def set_document_active(document_id, household_id, active):
    execute("""
        UPDATE documents
        SET is_active=%s, updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (1 if active else 0, document_id, household_id))

def delete_document(document_id, household_id):
    execute("""
        DELETE FROM documents
        WHERE id=%s AND household_id=%s
    """, (document_id, household_id))

def list_expenses_for_document_link(household_id):
    return fetch_all("""
        SELECT
            e.id,
            e.description,
            e.supplier,
            e.amount,
            COALESCE(e.expense_date,e.start_date) AS reference_date
        FROM expenses e
        WHERE e.household_id=%s AND e.is_active=1
        ORDER BY COALESCE(e.expense_date,e.start_date) DESC, e.id DESC
    """, (household_id,))

def get_document_stats(household_id):
    total = fetch_one("""
        SELECT COUNT(*) AS n
        FROM documents
        WHERE household_id=%s AND is_active=1
    """, (household_id,))["n"]

    linked = fetch_one("""
        SELECT COUNT(*) AS n
        FROM documents
        WHERE household_id=%s AND is_active=1 AND expense_id IS NOT NULL
    """, (household_id,))["n"]

    pending_ocr = fetch_one("""
        SELECT COUNT(*) AS n
        FROM documents
        WHERE household_id=%s AND is_active=1
          AND ocr_status IN ('not_started','pending')
    """, (household_id,))["n"]

    return {
        "total": total,
        "linked": linked,
        "unlinked": total - linked,
        "pending_ocr": pending_ocr
    }


# ------------------------------
# OCR / Extração automática - V1.6
# ------------------------------

def save_document_extraction(
    document_id, household_id, ocr_text, extracted_supplier,
    extracted_tax_id, extracted_document_number, extracted_document_date,
    extracted_total, extracted_vat, extracted_category_id,
    extraction_confidence, processing_status="processed",
    ocr_status="completed", extraction_method=None
):
    execute("""
        UPDATE documents
        SET ocr_text=%s,
            extracted_supplier=%s,
            extracted_tax_id=%s,
            extracted_document_number=%s,
            extracted_document_date=%s,
            extracted_total=%s,
            extracted_vat=%s,
            extracted_category_id=%s,
            extraction_confidence=%s,
            processing_status=%s,
            ocr_status=%s,
            extraction_method=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (
        ocr_text, extracted_supplier, extracted_tax_id,
        extracted_document_number, extracted_document_date,
        extracted_total, extracted_vat, extracted_category_id,
        extraction_confidence, processing_status, ocr_status,
        extraction_method, document_id, household_id
    ))

def mark_document_ocr_error(document_id, household_id, error_message):
    execute("""
        UPDATE documents
        SET processing_status='error',
            ocr_status='error',
            ocr_error=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (error_message, document_id, household_id))

def get_category_id_by_name(category_name):
    row = fetch_one("""
        SELECT id
        FROM categories
        WHERE type='expense' AND is_active=1 AND name=%s
        LIMIT 1
    """, (category_name,))
    return row["id"] if row else None

def create_expense_from_document(
    document_id, household_id, owner_user_id, category_id, supplier,
    description, amount, expense_date, payment_method, created_by
):
    expense_id = create_expense(
        household_id=household_id,
        category_id=category_id,
        owner_user_id=owner_user_id,
        supplier=supplier,
        description=description,
        amount=amount,
        expense_date=expense_date,
        recurrence_type="one_time",
        frequency="none",
        start_date=None,
        end_date=None,
        payment_method=payment_method,
        notes=f"Criada automaticamente a partir do documento #{document_id}",
        created_by=created_by
    )

    rebuild_expense_occurrences(expense_id, household_id)

    update_document_link(document_id, household_id, expense_id)

    return expense_id


# ------------------------------
# Robustez OCR e aprendizagem - V1.7
# ------------------------------

def find_duplicate_document(household_id, file_hash=None, tax_id=None, document_number=None, total=None, document_date=None):
    if file_hash:
        row = fetch_one("""
            SELECT id, original_name, created_at, file_hash
            FROM documents
            WHERE household_id=%s
              AND file_hash=%s
              AND is_active=1
            LIMIT 1
        """, (household_id, file_hash))
        if row:
            return {"match_type": "file_hash", **row}

    if tax_id and document_number:
        row = fetch_one("""
            SELECT id, original_name, created_at, extracted_tax_id, extracted_document_number
            FROM documents
            WHERE household_id=%s
              AND extracted_tax_id=%s
              AND extracted_document_number=%s
              AND is_active=1
            LIMIT 1
        """, (household_id, tax_id, document_number))
        if row:
            return {"match_type": "tax_id_document_number", **row}

    if total is not None and document_date is not None:
        row = fetch_one("""
            SELECT id, original_name, created_at, extracted_total, extracted_document_date
            FROM documents
            WHERE household_id=%s
              AND extracted_total=%s
              AND extracted_document_date=%s
              AND is_active=1
            LIMIT 1
        """, (household_id, total, document_date))
        if row:
            return {"match_type": "total_date", **row}

    return None

def update_document_hash(document_id, household_id, file_hash):
    execute("""
        UPDATE documents
        SET file_hash=%s, updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (file_hash, document_id, household_id))

def save_document_extraction_v17(
    document_id, household_id, ocr_text, extracted_supplier,
    extracted_tax_id, extracted_document_number, extracted_document_date,
    extracted_total, extracted_vat, extracted_category_id,
    extraction_confidence, field_confidence_json, nif_valid,
    extraction_method=None, duplicate_document_id=None, duplicate_match_type=None
):
    execute("""
        UPDATE documents
        SET ocr_text=%s,
            extracted_supplier=%s,
            extracted_tax_id=%s,
            extracted_document_number=%s,
            extracted_document_date=%s,
            extracted_total=%s,
            extracted_vat=%s,
            extracted_category_id=%s,
            extraction_confidence=%s,
            field_confidence_json=%s,
            nif_valid=%s,
            extraction_method=%s,
            duplicate_document_id=%s,
            duplicate_match_type=%s,
            processing_status='processed',
            ocr_status='completed',
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (
        ocr_text, extracted_supplier, extracted_tax_id,
        extracted_document_number, extracted_document_date,
        extracted_total, extracted_vat, extracted_category_id,
        extraction_confidence, field_confidence_json, 1 if nif_valid else 0,
        extraction_method, duplicate_document_id, duplicate_match_type,
        document_id, household_id
    ))

def list_learning_rules(household_id):
    return fetch_all("""
        SELECT id, supplier_name, category_id, match_tokens, usage_count, is_active
        FROM document_learning_rules
        WHERE household_id=%s AND is_active=1
        ORDER BY usage_count DESC, id DESC
    """, (household_id,))

def get_learning_rules_for_extractor(household_id):
    rows = fetch_all("""
        SELECT
            r.id,
            r.supplier_name,
            r.match_tokens,
            c.name AS category_name
        FROM document_learning_rules r
        LEFT JOIN categories c ON c.id=r.category_id
        WHERE r.household_id=%s AND r.is_active=1
        ORDER BY r.usage_count DESC, r.id DESC
    """, (household_id,))

    result = []
    import json
    for row in rows:
        try:
            tokens = json.loads(row["match_tokens"]) if row["match_tokens"] else []
        except Exception:
            tokens = []
        result.append({
            "id": row["id"],
            "supplier_name": row["supplier_name"],
            "match_tokens": tokens,
            "category_name": row["category_name"],
        })
    return result

def learn_document_correction(household_id, supplier_name, category_id, match_tokens):
    import json
    supplier_name = (supplier_name or "").strip()
    if not supplier_name:
        return None

    existing = fetch_one("""
        SELECT id
        FROM document_learning_rules
        WHERE household_id=%s
          AND supplier_name=%s
          AND category_id=%s
          AND is_active=1
        LIMIT 1
    """, (household_id, supplier_name, category_id))

    tokens_json = json.dumps(match_tokens or [], ensure_ascii=False)

    if existing:
        execute("""
            UPDATE document_learning_rules
            SET match_tokens=%s,
                usage_count=usage_count+1,
                updated_at=NOW()
            WHERE id=%s
        """, (tokens_json, existing["id"]))
        return existing["id"]

    return execute("""
        INSERT INTO document_learning_rules(
            household_id, supplier_name, category_id,
            match_tokens, usage_count, is_active
        )
        VALUES(%s,%s,%s,%s,1,1)
    """, (household_id, supplier_name, category_id, tokens_json))


# ------------------------------
# Classificação avançada - V1.8
# ------------------------------

def get_supplier_history(household_id, supplier_name, limit_rows=25):
    if not supplier_name:
        return []

    return fetch_all("""
        SELECT
            e.id,
            e.supplier,
            e.description,
            e.amount,
            e.expense_date,
            e.recurrence_type,
            e.frequency,
            e.category_id,
            c.name AS category_name
        FROM expenses e
        JOIN categories c ON c.id=e.category_id
        WHERE e.household_id=%s
          AND e.is_active=1
          AND LOWER(TRIM(COALESCE(e.supplier,'')))=LOWER(TRIM(%s))
        ORDER BY COALESCE(e.expense_date,e.start_date) DESC, e.id DESC
        LIMIT %s
    """, (household_id, supplier_name, limit_rows))

def get_supplier_category_stats(household_id, supplier_name):
    if not supplier_name:
        return []

    return fetch_all("""
        SELECT
            c.id AS category_id,
            c.name AS category_name,
            COUNT(*) AS usage_count,
            AVG(e.amount) AS average_amount,
            MAX(COALESCE(e.expense_date,e.start_date)) AS last_date
        FROM expenses e
        JOIN categories c ON c.id=e.category_id
        WHERE e.household_id=%s
          AND e.is_active=1
          AND LOWER(TRIM(COALESCE(e.supplier,'')))=LOWER(TRIM(%s))
        GROUP BY c.id,c.name
        ORDER BY usage_count DESC, last_date DESC
    """, (household_id, supplier_name))

def detect_monthly_supplier_pattern(household_id, supplier_name):
    if not supplier_name:
        return None

    rows = fetch_all("""
        SELECT DISTINCT
            YEAR(COALESCE(e.expense_date,e.start_date)) AS year_num,
            MONTH(COALESCE(e.expense_date,e.start_date)) AS month_num,
            AVG(e.amount) AS average_amount,
            COUNT(*) AS occurrence_count
        FROM expenses e
        WHERE e.household_id=%s
          AND e.is_active=1
          AND LOWER(TRIM(COALESCE(e.supplier,'')))=LOWER(TRIM(%s))
          AND COALESCE(e.expense_date,e.start_date) IS NOT NULL
        GROUP BY YEAR(COALESCE(e.expense_date,e.start_date)),
                 MONTH(COALESCE(e.expense_date,e.start_date))
        ORDER BY year_num DESC, month_num DESC
        LIMIT 12
    """, (household_id, supplier_name))

    if not rows:
        return None

    distinct_months = len(rows)
    total_occurrences = sum(int(r["occurrence_count"]) for r in rows)
    avg_amount = sum(float(r["average_amount"]) for r in rows) / distinct_months

    return {
        "distinct_months": distinct_months,
        "total_occurrences": total_occurrences,
        "average_amount": avg_amount,
        "is_monthly_pattern": distinct_months >= 3
    }

def classify_document_with_history(household_id, supplier_name, suggested_category_id, amount=None):
    stats = get_supplier_category_stats(household_id, supplier_name)

    result = {
        "category_id": suggested_category_id,
        "history_confidence": 0.0,
        "history_reason": None
    }

    if not stats:
        return result

    top = stats[0]
    total_usage = sum(int(x["usage_count"]) for x in stats)
    top_usage = int(top["usage_count"])

    confidence = (top_usage / total_usage * 100) if total_usage else 0

    if amount is not None and top["average_amount"] is not None:
        avg = float(top["average_amount"])
        if avg > 0:
            diff = abs(float(amount) - avg) / avg
            if diff <= 0.15:
                confidence = min(100.0, confidence + 10)
            elif diff > 0.75:
                confidence = max(0.0, confidence - 10)

    result["category_id"] = top["category_id"]
    result["history_confidence"] = round(confidence, 1)
    result["history_reason"] = (
        f"Fornecedor já classificado {top_usage}x como {top['category_name']}"
    )
    return result

def save_document_v18_intelligence(
    document_id, household_id, final_category_id,
    history_confidence, history_reason,
    monthly_pattern, auto_create_eligible
):
    import json
    execute("""
        UPDATE documents
        SET history_category_id=%s,
            history_confidence=%s,
            history_reason=%s,
            monthly_pattern_json=%s,
            auto_create_eligible=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (
        final_category_id,
        history_confidence,
        history_reason,
        json.dumps(monthly_pattern, ensure_ascii=False) if monthly_pattern else None,
        1 if auto_create_eligible else 0,
        document_id,
        household_id
    ))

def get_auto_create_threshold(household_id):
    row = fetch_one("""
        SELECT auto_create_threshold, auto_create_enabled
        FROM household_ai_settings
        WHERE household_id=%s
        LIMIT 1
    """, (household_id,))

    if row:
        return {
            "threshold": float(row["auto_create_threshold"]),
            "enabled": bool(row["auto_create_enabled"])
        }

    return {
        "threshold": 95.0,
        "enabled": False
    }

def save_auto_create_settings(household_id, enabled, threshold):
    existing = fetch_one("""
        SELECT household_id
        FROM household_ai_settings
        WHERE household_id=%s
        LIMIT 1
    """, (household_id,))

    if existing:
        execute("""
            UPDATE household_ai_settings
            SET auto_create_enabled=%s,
                auto_create_threshold=%s,
                updated_at=NOW()
            WHERE household_id=%s
        """, (1 if enabled else 0, threshold, household_id))
    else:
        execute("""
            INSERT INTO household_ai_settings(
                household_id, auto_create_enabled, auto_create_threshold
            )
            VALUES(%s,%s,%s)
        """, (household_id, 1 if enabled else 0, threshold))


# ============================================================
# V1.9 — Linhas de fatura, orçamentos e alertas
# ============================================================

def replace_document_items(document_id, household_id, items):
    execute("""
        DELETE di
        FROM document_items di
        JOIN documents d ON d.id=di.document_id
        WHERE di.document_id=%s AND d.household_id=%s
    """, (document_id, household_id))

    for pos, item in enumerate(items, start=1):
        category_id = item.get("category_id")
        execute("""
            INSERT INTO document_items(
                document_id, line_no, description, quantity,
                unit_price, line_total, category_id,
                category_confidence, source, is_confirmed
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'automatic',0)
        """, (
            document_id,
            pos,
            item.get("description"),
            item.get("quantity", 1),
            item.get("unit_price"),
            item.get("line_total"),
            category_id,
            item.get("category_confidence")
        ))

def list_document_items(document_id, household_id):
    return fetch_all("""
        SELECT
            di.id,
            di.line_no,
            di.description,
            di.quantity,
            di.unit_price,
            di.line_total,
            di.category_id,
            c.name AS category_name,
            di.category_confidence,
            di.source,
            di.is_confirmed
        FROM document_items di
        JOIN documents d ON d.id=di.document_id
        LEFT JOIN categories c ON c.id=di.category_id
        WHERE di.document_id=%s
          AND d.household_id=%s
        ORDER BY di.line_no, di.id
    """, (document_id, household_id))

def update_document_item(
    item_id, document_id, household_id, description,
    quantity, unit_price, line_total, category_id, confirmed=True
):
    execute("""
        UPDATE document_items di
        JOIN documents d ON d.id=di.document_id
        SET di.description=%s,
            di.quantity=%s,
            di.unit_price=%s,
            di.line_total=%s,
            di.category_id=%s,
            di.is_confirmed=%s,
            di.source='user_confirmed',
            di.updated_at=NOW()
        WHERE di.id=%s
          AND di.document_id=%s
          AND d.household_id=%s
    """, (
        description, quantity, unit_price, line_total,
        category_id, 1 if confirmed else 0,
        item_id, document_id, household_id
    ))

def delete_document_item(item_id, document_id, household_id):
    execute("""
        DELETE di
        FROM document_items di
        JOIN documents d ON d.id=di.document_id
        WHERE di.id=%s
          AND di.document_id=%s
          AND d.household_id=%s
    """, (item_id, document_id, household_id))

def add_document_item(
    document_id, household_id, description,
    quantity, unit_price, line_total, category_id
):
    doc = fetch_one("""
        SELECT id FROM documents
        WHERE id=%s AND household_id=%s
        LIMIT 1
    """, (document_id, household_id))
    if not doc:
        raise ValueError("Documento inválido.")

    row = fetch_one("""
        SELECT COALESCE(MAX(line_no),0)+1 AS next_line
        FROM document_items
        WHERE document_id=%s
    """, (document_id,))

    return execute("""
        INSERT INTO document_items(
            document_id,line_no,description,quantity,
            unit_price,line_total,category_id,
            category_confidence,source,is_confirmed
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,100,'user_added',1)
    """, (
        document_id, row["next_line"], description, quantity,
        unit_price, line_total, category_id
    ))

def get_document_item_summary(document_id, household_id):
    return fetch_all("""
        SELECT
            COALESCE(c.name,'Outros') AS category_name,
            SUM(di.line_total) AS total,
            COUNT(*) AS item_count
        FROM document_items di
        JOIN documents d ON d.id=di.document_id
        LEFT JOIN categories c ON c.id=di.category_id
        WHERE di.document_id=%s
          AND d.household_id=%s
        GROUP BY c.id,c.name
        ORDER BY total DESC
    """, (document_id, household_id))

def get_item_category_history(household_id, description, limit_rows=20):
    token = (description or "").strip().lower()
    if len(token) < 3:
        return []

    return fetch_all("""
        SELECT
            di.category_id,
            c.name AS category_name,
            COUNT(*) AS usage_count
        FROM document_items di
        JOIN documents d ON d.id=di.document_id
        LEFT JOIN categories c ON c.id=di.category_id
        WHERE d.household_id=%s
          AND di.is_confirmed=1
          AND LOWER(di.description) LIKE %s
          AND di.category_id IS NOT NULL
        GROUP BY di.category_id,c.name
        ORDER BY usage_count DESC
        LIMIT %s
    """, (household_id, f"%{token}%", limit_rows))

def list_budgets(household_id, year, month):
    return fetch_all("""
        SELECT
            b.id,
            b.category_id,
            c.name AS category_name,
            b.year_num,
            b.month_num,
            b.amount_limit,
            b.warning_percent,
            COALESCE(SUM(di.line_total),0) AS spent_items
        FROM category_budgets b
        JOIN categories c ON c.id=b.category_id
        LEFT JOIN documents d
            ON d.household_id=b.household_id
           AND d.is_active=1
           AND YEAR(COALESCE(d.extracted_document_date,d.created_at))=b.year_num
           AND MONTH(COALESCE(d.extracted_document_date,d.created_at))=b.month_num
        LEFT JOIN document_items di
            ON di.document_id=d.id
           AND di.category_id=b.category_id
        WHERE b.household_id=%s
          AND b.year_num=%s
          AND b.month_num=%s
        GROUP BY b.id,c.id,c.name,b.year_num,b.month_num,b.amount_limit,b.warning_percent
        ORDER BY c.name
    """, (household_id, year, month))

def upsert_budget(household_id, category_id, year, month, amount_limit, warning_percent=80):
    existing = fetch_one("""
        SELECT id FROM category_budgets
        WHERE household_id=%s AND category_id=%s
          AND year_num=%s AND month_num=%s
        LIMIT 1
    """, (household_id, category_id, year, month))

    if existing:
        execute("""
            UPDATE category_budgets
            SET amount_limit=%s,
                warning_percent=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (amount_limit, warning_percent, existing["id"]))
        return existing["id"]

    return execute("""
        INSERT INTO category_budgets(
            household_id,category_id,year_num,month_num,
            amount_limit,warning_percent
        )
        VALUES(%s,%s,%s,%s,%s,%s)
    """, (
        household_id, category_id, year, month,
        amount_limit, warning_percent
    ))

def delete_budget(budget_id, household_id):
    execute("""
        DELETE FROM category_budgets
        WHERE id=%s AND household_id=%s
    """, (budget_id, household_id))

def get_budget_alerts(household_id, year, month):
    rows = list_budgets(household_id, year, month)
    alerts = []

    for row in rows:
        limit_value = float(row["amount_limit"] or 0)
        spent = float(row["spent_items"] or 0)
        warning = float(row["warning_percent"] or 80)

        percent = (spent / limit_value * 100) if limit_value > 0 else 0

        if percent >= 100:
            level = "exceeded"
        elif percent >= warning:
            level = "warning"
        else:
            level = "ok"

        alerts.append({
            **row,
            "spent": spent,
            "percent": round(percent, 1),
            "remaining": round(limit_value - spent, 2),
            "level": level
        })

    return alerts

def suggest_budget_from_history(household_id, category_id, months=3):
    row = fetch_one("""
        SELECT AVG(month_total) AS avg_month
        FROM (
            SELECT
                YEAR(COALESCE(d.extracted_document_date,d.created_at)) AS y,
                MONTH(COALESCE(d.extracted_document_date,d.created_at)) AS m,
                SUM(di.line_total) AS month_total
            FROM document_items di
            JOIN documents d ON d.id=di.document_id
            WHERE d.household_id=%s
              AND d.is_active=1
              AND di.category_id=%s
            GROUP BY
                YEAR(COALESCE(d.extracted_document_date,d.created_at)),
                MONTH(COALESCE(d.extracted_document_date,d.created_at))
            ORDER BY y DESC,m DESC
            LIMIT %s
        ) x
    """, (household_id, category_id, months))

    avg = float(row["avg_month"]) if row and row["avg_month"] is not None else 0.0

    # orçamento sugerido com pequena margem de segurança
    return round(avg * 1.05, 2) if avg > 0 else 0.0


def save_document_items_metadata(
    document_id, household_id, items_total, coverage_percent
):
    execute("""
        UPDATE documents
        SET items_extracted=1,
            items_total=%s,
            items_coverage_percent=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (
        items_total, coverage_percent,
        document_id, household_id
    ))


# ============================================================
# V2.0 — Previsão financeira, calendário e metas
# ============================================================

def get_month_occurrences(household_id, year, month):
    incomes = fetch_all("""
        SELECT
            io.id AS occurrence_id,
            'income' AS kind,
            i.description,
            io.amount,
            io.occurrence_date,
            i.recurrence_type,
            i.frequency
        FROM income_occurrences io
        JOIN incomes i ON i.id=io.income_id
        WHERE io.household_id=%s
          AND io.is_active=1
          AND i.is_active=1
          AND YEAR(io.occurrence_date)=%s
          AND MONTH(io.occurrence_date)=%s
    """, (household_id, year, month))

    expenses = fetch_all("""
        SELECT
            eo.id AS occurrence_id,
            'expense' AS kind,
            e.description,
            eo.amount,
            eo.occurrence_date,
            e.recurrence_type,
            e.frequency,
            e.supplier
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        WHERE eo.household_id=%s
          AND eo.is_active=1
          AND e.is_active=1
          AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s
    """, (household_id, year, month))

    return sorted(
        [*incomes, *expenses],
        key=lambda x: x["occurrence_date"]
    )

def get_financial_forecast(household_id, year, month, reference_date=None):
    from datetime import date

    if reference_date is None:
        reference_date = date.today()

    rows = get_month_occurrences(household_id, year, month)

    realized_income = 0.0
    realized_expense = 0.0
    future_income = 0.0
    future_expense = 0.0

    for row in rows:
        amount = float(row["amount"] or 0)
        is_future = row["occurrence_date"] > reference_date

        if row["kind"] == "income":
            if is_future:
                future_income += amount
            else:
                realized_income += amount
        else:
            if is_future:
                future_expense += amount
            else:
                realized_expense += amount

    projected_income = realized_income + future_income
    projected_expense = realized_expense + future_expense
    projected_balance = projected_income - projected_expense
    current_balance = realized_income - realized_expense

    return {
        "realized_income": round(realized_income, 2),
        "realized_expense": round(realized_expense, 2),
        "future_income": round(future_income, 2),
        "future_expense": round(future_expense, 2),
        "current_balance": round(current_balance, 2),
        "projected_income": round(projected_income, 2),
        "projected_expense": round(projected_expense, 2),
        "projected_balance": round(projected_balance, 2),
        "rows": rows
    }

def get_upcoming_commitments(household_id, start_date, days=30):
    from datetime import timedelta
    end_date = start_date + timedelta(days=days)

    rows = fetch_all("""
        SELECT
            'income' AS kind,
            i.description,
            io.amount,
            io.occurrence_date,
            NULL AS supplier
        FROM income_occurrences io
        JOIN incomes i ON i.id=io.income_id
        WHERE io.household_id=%s
          AND io.is_active=1
          AND i.is_active=1
          AND io.occurrence_date BETWEEN %s AND %s

        UNION ALL

        SELECT
            'expense' AS kind,
            e.description,
            eo.amount,
            eo.occurrence_date,
            e.supplier
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        WHERE eo.household_id=%s
          AND eo.is_active=1
          AND e.is_active=1
          AND eo.occurrence_date BETWEEN %s AND %s

        ORDER BY occurrence_date
    """, (
        household_id, start_date, end_date,
        household_id, start_date, end_date
    ))
    return rows

def get_forecast_alerts(household_id, reference_date=None, horizon_days=30):
    from datetime import date, timedelta

    if reference_date is None:
        reference_date = date.today()

    alerts = []
    commitments = get_upcoming_commitments(
        household_id, reference_date, horizon_days
    )

    running = 0.0
    for row in commitments:
        amount = float(row["amount"] or 0)
        if row["kind"] == "income":
            running += amount
        else:
            running -= amount

        if row["kind"] == "expense" and amount >= 250:
            alerts.append({
                "level": "info",
                "date": row["occurrence_date"],
                "title": "Despesa relevante aproximar-se",
                "message": f"{row['description']} — {amount:.2f} €"
            })

        if running < -500:
            alerts.append({
                "level": "warning",
                "date": row["occurrence_date"],
                "title": "Pressão de tesouraria prevista",
                "message": f"O saldo projetado dos próximos compromissos fica em {running:.2f} €."
            })
            break

    return alerts

def list_saving_goals(household_id):
    return fetch_all("""
        SELECT
            id,
            name,
            target_amount,
            current_amount,
            target_date,
            is_active,
            created_at
        FROM saving_goals
        WHERE household_id=%s
        ORDER BY is_active DESC, target_date IS NULL, target_date, id DESC
    """, (household_id,))

def create_saving_goal(household_id, name, target_amount, target_date=None, current_amount=0):
    return execute("""
        INSERT INTO saving_goals(
            household_id,name,target_amount,current_amount,target_date,is_active
        )
        VALUES(%s,%s,%s,%s,%s,1)
    """, (
        household_id, name, target_amount, current_amount, target_date
    ))

def update_saving_goal(goal_id, household_id, current_amount=None, target_amount=None, target_date=None, is_active=None):
    fields = []
    params = []

    if current_amount is not None:
        fields.append("current_amount=%s")
        params.append(current_amount)
    if target_amount is not None:
        fields.append("target_amount=%s")
        params.append(target_amount)
    if target_date is not None:
        fields.append("target_date=%s")
        params.append(target_date)
    if is_active is not None:
        fields.append("is_active=%s")
        params.append(1 if is_active else 0)

    if not fields:
        return

    params.extend([goal_id, household_id])

    execute(
        f"""
        UPDATE saving_goals
        SET {", ".join(fields)}, updated_at=NOW()
        WHERE id=%s AND household_id=%s
        """,
        tuple(params)
    )

def delete_saving_goal(goal_id, household_id):
    execute("""
        DELETE FROM saving_goals
        WHERE id=%s AND household_id=%s
    """, (goal_id, household_id))

def get_goal_projection(household_id, goal):
    history = get_financial_history(household_id, months=6)
    positive_balances = [
        float(r["balance"])
        for r in history
        if float(r["balance"]) > 0
    ]

    avg_saving = (
        sum(positive_balances) / len(positive_balances)
        if positive_balances else 0.0
    )

    remaining = max(
        0.0,
        float(goal["target_amount"]) - float(goal["current_amount"])
    )

    months_needed = (
        remaining / avg_saving
        if avg_saving > 0 else None
    )

    return {
        "average_monthly_saving": round(avg_saving, 2),
        "remaining": round(remaining, 2),
        "months_needed": round(months_needed, 1) if months_needed is not None else None
    }


# ============================================================
# V2.1 — Calendário, previsões multi-mês e cenários "E se?"
# ============================================================

def get_calendar_events(household_id, start_date, end_date):
    incomes = fetch_all("""
        SELECT
            io.occurrence_date AS event_date,
            'income' AS kind,
            i.description AS title,
            io.amount,
            NULL AS supplier
        FROM income_occurrences io
        JOIN incomes i ON i.id=io.income_id
        WHERE io.household_id=%s
          AND io.is_active=1
          AND i.is_active=1
          AND io.occurrence_date BETWEEN %s AND %s
    """, (household_id, start_date, end_date))

    expenses = fetch_all("""
        SELECT
            eo.occurrence_date AS event_date,
            'expense' AS kind,
            e.description AS title,
            eo.amount,
            e.supplier
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        WHERE eo.household_id=%s
          AND eo.is_active=1
          AND e.is_active=1
          AND eo.occurrence_date BETWEEN %s AND %s
    """, (household_id, start_date, end_date))

    return sorted(
        [*incomes, *expenses],
        key=lambda x: (x["event_date"], x["kind"], x["title"] or "")
    )

def get_multi_month_forecast(household_id, start_year, start_month, months=12):
    from datetime import date
    import calendar

    results = []
    year = start_year
    month = start_month

    for _ in range(months):
        first_day = date(year, month, 1)
        last_day_num = calendar.monthrange(year, month)[1]
        reference = date(year, month, last_day_num)

        summary = get_month_summary(household_id, year, month)
        events = get_month_occurrences(household_id, year, month)

        recurring_income = sum(
            float(r["amount"] or 0)
            for r in events
            if r["kind"] == "income" and r.get("recurrence_type") == "recurring"
        )
        recurring_expense = sum(
            float(r["amount"] or 0)
            for r in events
            if r["kind"] == "expense" and r.get("recurrence_type") == "recurring"
        )

        results.append({
            "year": year,
            "month": month,
            "income": float(summary["income"]),
            "expense": float(summary["expense"]),
            "balance": float(summary["balance"]),
            "recurring_income": round(recurring_income, 2),
            "recurring_expense": round(recurring_expense, 2),
        })

        month += 1
        if month > 12:
            month = 1
            year += 1

    return results

def get_recurring_expenses_for_scenarios(household_id):
    return fetch_all("""
        SELECT
            e.id,
            e.description,
            e.supplier,
            e.amount,
            e.frequency,
            e.category_id,
            c.name AS category_name
        FROM expenses e
        LEFT JOIN categories c ON c.id=e.category_id
        WHERE e.household_id=%s
          AND e.is_active=1
          AND e.recurrence_type='recurring'
        ORDER BY e.amount DESC, e.description
    """, (household_id,))

def simulate_expense_reduction(household_id, expense_reductions, months=12):
    """
    expense_reductions:
      {expense_id: percent_reduction}
    """
    expenses = get_recurring_expenses_for_scenarios(household_id)

    monthly_saving = 0.0
    details = []

    for expense in expenses:
        reduction_pct = float(expense_reductions.get(expense["id"], 0) or 0)
        if reduction_pct <= 0:
            continue

        amount = float(expense["amount"] or 0)

        # normalização aproximada mensal por frequência
        freq = expense["frequency"]
        if freq == "monthly":
            monthly_equivalent = amount
        elif freq == "quarterly":
            monthly_equivalent = amount / 3
        elif freq == "semiannual":
            monthly_equivalent = amount / 6
        elif freq == "annual":
            monthly_equivalent = amount / 12
        else:
            monthly_equivalent = amount

        saving = monthly_equivalent * reduction_pct / 100
        monthly_saving += saving

        details.append({
            "expense_id": expense["id"],
            "description": expense["description"],
            "supplier": expense["supplier"],
            "reduction_pct": reduction_pct,
            "monthly_saving": round(saving, 2),
            "annual_saving": round(saving * 12, 2),
        })

    return {
        "monthly_saving": round(monthly_saving, 2),
        "annual_saving": round(monthly_saving * 12, 2),
        "period_saving": round(monthly_saving * months, 2),
        "details": details,
    }

def get_annual_savings_projection(household_id, year):
    rows = []
    total_income = 0.0
    total_expense = 0.0

    for month in range(1, 13):
        summary = get_month_summary(household_id, year, month)
        income = float(summary["income"])
        expense = float(summary["expense"])
        balance = income - expense

        total_income += income
        total_expense += expense

        rows.append({
            "month": month,
            "income": income,
            "expense": expense,
            "balance": balance
        })

    total_saving = total_income - total_expense
    savings_rate = (total_saving / total_income * 100) if total_income > 0 else 0

    return {
        "year": year,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "total_saving": round(total_saving, 2),
        "savings_rate": round(savings_rate, 1),
        "months": rows
    }

def get_scenario_presets(household_id):
    return fetch_all("""
        SELECT
            id,
            name,
            scenario_json,
            created_at,
            updated_at
        FROM financial_scenarios
        WHERE household_id=%s
        ORDER BY updated_at DESC, id DESC
    """, (household_id,))

def save_scenario_preset(household_id, name, scenario_json):
    existing = fetch_one("""
        SELECT id FROM financial_scenarios
        WHERE household_id=%s AND name=%s
        LIMIT 1
    """, (household_id, name))

    if existing:
        execute("""
            UPDATE financial_scenarios
            SET scenario_json=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (scenario_json, existing["id"]))
        return existing["id"]

    return execute("""
        INSERT INTO financial_scenarios(
            household_id, name, scenario_json
        )
        VALUES(%s,%s,%s)
    """, (household_id, name, scenario_json))

def delete_scenario_preset(scenario_id, household_id):
    execute("""
        DELETE FROM financial_scenarios
        WHERE id=%s AND household_id=%s
    """, (scenario_id, household_id))


# ============================================================
# V2.2 — Risco financeiro, anomalias e recomendações
# ============================================================

def get_monthly_category_history(household_id, category_id, months=6):
    return fetch_all("""
        SELECT
            YEAR(eo.occurrence_date) AS year_num,
            MONTH(eo.occurrence_date) AS month_num,
            SUM(eo.amount) AS total
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        WHERE eo.household_id=%s
          AND eo.is_active=1
          AND e.is_active=1
          AND e.category_id=%s
        GROUP BY YEAR(eo.occurrence_date), MONTH(eo.occurrence_date)
        ORDER BY year_num DESC, month_num DESC
        LIMIT %s
    """, (household_id, category_id, months))

def detect_expense_anomalies(household_id, months=6, threshold_pct=35):
    categories = get_expense_categories()
    anomalies = []

    for category in categories:
        history = get_monthly_category_history(
            household_id,
            category["id"],
            months
        )

        if len(history) < 3:
            continue

        values = [float(r["total"] or 0) for r in history]
        current = values[0]
        baseline_values = values[1:]

        if not baseline_values:
            continue

        baseline = sum(baseline_values) / len(baseline_values)

        if baseline <= 0:
            continue

        deviation_pct = ((current - baseline) / baseline) * 100

        if deviation_pct >= threshold_pct:
            anomalies.append({
                "category_id": category["id"],
                "category_name": category["name"],
                "current_total": round(current, 2),
                "baseline": round(baseline, 2),
                "deviation_pct": round(deviation_pct, 1),
                "level": (
                    "high" if deviation_pct >= 75
                    else "medium"
                )
            })

    return sorted(
        anomalies,
        key=lambda x: x["deviation_pct"],
        reverse=True
    )

def get_budget_deviation_forecast(household_id, year, month):
    import calendar
    from datetime import date

    today = date.today()
    rows = get_budget_alerts(household_id, year, month)

    if year == today.year and month == today.month:
        elapsed_days = today.day
        total_days = calendar.monthrange(year, month)[1]
    else:
        elapsed_days = calendar.monthrange(year, month)[1]
        total_days = elapsed_days

    result = []

    for row in rows:
        spent = float(row["spent"] or 0)
        limit_value = float(row["amount_limit"] or 0)

        if elapsed_days > 0:
            projected = spent / elapsed_days * total_days
        else:
            projected = spent

        deviation = projected - limit_value
        deviation_pct = (
            deviation / limit_value * 100
            if limit_value > 0 else 0
        )

        result.append({
            **row,
            "projected_spend": round(projected, 2),
            "projected_deviation": round(deviation, 2),
            "projected_deviation_pct": round(deviation_pct, 1),
            "projected_over_budget": projected > limit_value
        })

    return result

def get_financial_risk_score(household_id, year, month):
    """
    Score 0-100:
      0 = baixo risco
      100 = risco muito elevado
    """
    summary = get_month_summary(household_id, year, month)
    forecast = get_financial_forecast(household_id, year, month)
    budget_rows = get_budget_deviation_forecast(household_id, year, month)
    anomalies = detect_expense_anomalies(household_id)

    score = 0.0
    reasons = []

    income = float(summary["income"])
    expense = float(summary["expense"])
    balance = float(summary["balance"])
    savings_rate = float(summary["savings_rate"])
    projected_balance = float(forecast["projected_balance"])

    # Peso da despesa no rendimento
    if income > 0:
        expense_weight = expense / income * 100
    else:
        expense_weight = 100 if expense > 0 else 0

    if expense_weight >= 100:
        score += 30
        reasons.append("Despesas iguais ou superiores aos rendimentos.")
    elif expense_weight >= 90:
        score += 22
        reasons.append("Despesas acima de 90% dos rendimentos.")
    elif expense_weight >= 80:
        score += 14
        reasons.append("Despesas acima de 80% dos rendimentos.")

    # Saldo projetado
    if projected_balance < 0:
        score += 30
        reasons.append("Saldo projetado negativo no final do mês.")
    elif projected_balance < 250:
        score += 18
        reasons.append("Margem projetada inferior a 250 €.")
    elif projected_balance < 500:
        score += 8
        reasons.append("Margem projetada reduzida.")

    # Taxa de poupança
    if savings_rate < 0:
        score += 15
        reasons.append("Taxa de poupança negativa.")
    elif savings_rate < 5:
        score += 10
        reasons.append("Taxa de poupança muito baixa.")
    elif savings_rate < 10:
        score += 5
        reasons.append("Taxa de poupança abaixo de 10%.")

    # Orçamentos
    over_budget = sum(
        1 for r in budget_rows
        if r["projected_over_budget"]
    )

    if over_budget >= 3:
        score += 15
        reasons.append(
            f"{over_budget} categorias com previsão de ultrapassar orçamento."
        )
    elif over_budget == 2:
        score += 10
        reasons.append("2 categorias com previsão de ultrapassar orçamento.")
    elif over_budget == 1:
        score += 5
        reasons.append("1 categoria com previsão de ultrapassar orçamento.")

    # Anomalias
    if len(anomalies) >= 3:
        score += 10
        reasons.append("Várias categorias apresentam aumentos anormais.")
    elif len(anomalies) >= 1:
        score += 5
        reasons.append("Foi detetado pelo menos um aumento anormal de despesa.")

    score = max(0.0, min(100.0, score))

    if score < 25:
        level = "low"
        label = "Baixo"
    elif score < 50:
        level = "moderate"
        label = "Moderado"
    elif score < 75:
        level = "high"
        label = "Elevado"
    else:
        level = "critical"
        label = "Crítico"

    return {
        "score": round(score, 0),
        "level": level,
        "label": label,
        "reasons": reasons,
        "expense_weight": round(expense_weight, 1),
        "projected_balance": projected_balance,
        "savings_rate": savings_rate,
        "over_budget_count": over_budget,
        "anomaly_count": len(anomalies)
    }

def get_cut_recommendations(household_id, year=None, month=None, max_rows=10):
    if year is None or month is None:
        today = date.today()
        year = year or today.year
        month = month or today.month
    recurring = get_recurring_expenses_for_scenarios(household_id)
    budget_rows = get_budget_deviation_forecast(household_id, year, month)
    anomalies = detect_expense_anomalies(household_id)

    budget_by_category = {
        int(r["category_id"]): r
        for r in budget_rows
        if r.get("category_id") is not None
    }

    anomaly_by_category = {
        int(r["category_id"]): r
        for r in anomalies
        if r.get("category_id") is not None
    }

    recommendations = []

    for exp in recurring:
        amount = float(exp["amount"] or 0)
        freq = exp["frequency"]

        if freq == "monthly":
            monthly = amount
        elif freq == "quarterly":
            monthly = amount / 3
        elif freq == "semiannual":
            monthly = amount / 6
        elif freq == "annual":
            monthly = amount / 12
        else:
            monthly = amount

        category_id = int(exp["category_id"]) if exp.get("category_id") else None
        budget = budget_by_category.get(category_id)
        anomaly = anomaly_by_category.get(category_id)

        priority_score = monthly
        reasons = []

        if budget and budget["projected_over_budget"]:
            priority_score *= 1.35
            reasons.append(
                f"Categoria prevê exceder o orçamento em "
                f"{abs(float(budget['projected_deviation'])):.2f} €."
            )

        if anomaly:
            priority_score *= 1.25
            reasons.append(
                f"Categoria está {float(anomaly['deviation_pct']):.0f}% "
                f"acima da média recente."
            )

        # recomendação de corte proporcional ao valor mensal
        if monthly >= 100:
            suggested_pct = 20
        elif monthly >= 50:
            suggested_pct = 15
        else:
            suggested_pct = 10

        monthly_saving = monthly * suggested_pct / 100

        recommendations.append({
            "expense_id": exp["id"],
            "description": exp["description"],
            "supplier": exp["supplier"],
            "category_name": exp["category_name"],
            "monthly_equivalent": round(monthly, 2),
            "suggested_reduction_pct": suggested_pct,
            "estimated_monthly_saving": round(monthly_saving, 2),
            "estimated_annual_saving": round(monthly_saving * 12, 2),
            "priority_score": round(priority_score, 2),
            "reasons": reasons or ["Despesa recorrente com potencial de redução."]
        })

    return sorted(
        recommendations,
        key=lambda x: x["priority_score"],
        reverse=True
    )[:max_rows]

def save_risk_snapshot(household_id, year, month, risk):
    existing = fetch_one("""
        SELECT id
        FROM financial_risk_snapshots
        WHERE household_id=%s
          AND year_num=%s
          AND month_num=%s
        LIMIT 1
    """, (household_id, year, month))

    payload = json.dumps(risk, ensure_ascii=False)

    if existing:
        execute("""
            UPDATE financial_risk_snapshots
            SET score=%s,
                level=%s,
                details_json=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (
            risk["score"],
            risk["level"],
            payload,
            existing["id"]
        ))
    else:
        execute("""
            INSERT INTO financial_risk_snapshots(
                household_id,year_num,month_num,
                score,level,details_json
            )
            VALUES(%s,%s,%s,%s,%s,%s)
        """, (
            household_id,
            year,
            month,
            risk["score"],
            risk["level"],
            payload
        ))

def list_risk_snapshots(household_id, limit_rows=12):
    return fetch_all("""
        SELECT
            id, year_num, month_num, score, level,
            details_json, created_at, updated_at
        FROM financial_risk_snapshots
        WHERE household_id=%s
        ORDER BY year_num DESC, month_num DESC
        LIMIT %s
    """, (household_id, limit_rows))


# ============================================================
# V2.3 — Market Intelligence
# ============================================================

def list_market_providers(service_type=None, active_only=True):
    sql = """
        SELECT
            id,
            name,
            service_type,
            website,
            notes,
            is_active,
            created_at,
            updated_at
        FROM market_providers
        WHERE 1=1
    """
    params = []

    if service_type:
        sql += " AND service_type=%s"
        params.append(service_type)

    if active_only:
        sql += " AND is_active=1"

    sql += " ORDER BY service_type,name"
    return fetch_all(sql, tuple(params))

def create_market_provider(name, service_type, website=None, notes=None):
    return execute("""
        INSERT INTO market_providers(
            name,service_type,website,notes,is_active
        )
        VALUES(%s,%s,%s,%s,1)
    """, (name,service_type,website,notes))

def update_market_provider(provider_id, name, service_type, website=None, notes=None, is_active=True):
    execute("""
        UPDATE market_providers
        SET name=%s,
            service_type=%s,
            website=%s,
            notes=%s,
            is_active=%s,
            updated_at=NOW()
        WHERE id=%s
    """, (
        name,service_type,website,notes,
        1 if is_active else 0,
        provider_id
    ))

def list_market_offers(service_type=None, provider_id=None, active_only=True):
    sql = """
        SELECT
            mo.id,
            mo.provider_id,
            mp.name AS provider_name,
            mp.service_type,
            mo.plan_name,
            mo.monthly_price,
            mo.unit_price,
            mo.daily_price,
            mo.contract_months,
            mo.conditions,
            mo.source,
            mo.source_url,
            mo.date_checked,
            mo.is_active,
            mo.created_at,
            mo.updated_at
        FROM market_offers mo
        JOIN market_providers mp ON mp.id=mo.provider_id
        WHERE 1=1
    """
    params = []

    if service_type:
        sql += " AND mp.service_type=%s"
        params.append(service_type)

    if provider_id:
        sql += " AND mo.provider_id=%s"
        params.append(provider_id)

    if active_only:
        sql += " AND mo.is_active=1 AND mp.is_active=1"

    sql += " ORDER BY mp.service_type,mo.monthly_price,mp.name,mo.plan_name"
    return fetch_all(sql, tuple(params))

def create_market_offer(
    provider_id, plan_name, monthly_price=None,
    unit_price=None, daily_price=None,
    contract_months=None, conditions=None,
    source=None, source_url=None, date_checked=None
):
    return execute("""
        INSERT INTO market_offers(
            provider_id,plan_name,monthly_price,unit_price,daily_price,
            contract_months,conditions,source,source_url,date_checked,is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
    """, (
        provider_id,plan_name,monthly_price,unit_price,daily_price,
        contract_months,conditions,source,source_url,date_checked
    ))

def update_market_offer(
    offer_id, plan_name, monthly_price=None,
    unit_price=None, daily_price=None,
    contract_months=None, conditions=None,
    source=None, source_url=None, date_checked=None,
    is_active=True
):
    execute("""
        UPDATE market_offers
        SET plan_name=%s,
            monthly_price=%s,
            unit_price=%s,
            daily_price=%s,
            contract_months=%s,
            conditions=%s,
            source=%s,
            source_url=%s,
            date_checked=%s,
            is_active=%s,
            updated_at=NOW()
        WHERE id=%s
    """, (
        plan_name,monthly_price,unit_price,daily_price,
        contract_months,conditions,source,source_url,date_checked,
        1 if is_active else 0,
        offer_id
    ))

def delete_market_offer(offer_id):
    execute("""
        DELETE FROM market_offers
        WHERE id=%s
    """, (offer_id,))

def list_household_services(household_id, active_only=True):
    sql = """
        SELECT
            hs.id,
            hs.household_id,
            hs.service_type,
            hs.provider_name,
            hs.plan_name,
            hs.monthly_cost,
            hs.unit_price,
            hs.daily_price,
            hs.contract_end_date,
            hs.notes,
            hs.is_active,
            hs.created_at,
            hs.updated_at
        FROM household_services hs
        WHERE hs.household_id=%s
    """
    params = [household_id]

    if active_only:
        sql += " AND hs.is_active=1"

    sql += " ORDER BY hs.service_type,hs.provider_name"
    return fetch_all(sql, tuple(params))

def create_household_service(
    household_id, service_type, provider_name,
    plan_name=None, monthly_cost=None,
    unit_price=None, daily_price=None,
    contract_end_date=None, notes=None
):
    return execute("""
        INSERT INTO household_services(
            household_id,service_type,provider_name,plan_name,
            monthly_cost,unit_price,daily_price,
            contract_end_date,notes,is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
    """, (
        household_id,service_type,provider_name,plan_name,
        monthly_cost,unit_price,daily_price,
        contract_end_date,notes
    ))

def update_household_service(
    service_id, household_id, provider_name, plan_name=None,
    monthly_cost=None, unit_price=None, daily_price=None,
    contract_end_date=None, notes=None, is_active=True
):
    execute("""
        UPDATE household_services
        SET provider_name=%s,
            plan_name=%s,
            monthly_cost=%s,
            unit_price=%s,
            daily_price=%s,
            contract_end_date=%s,
            notes=%s,
            is_active=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (
        provider_name,plan_name,monthly_cost,unit_price,daily_price,
        contract_end_date,notes,1 if is_active else 0,
        service_id,household_id
    ))

def delete_household_service(service_id, household_id):
    execute("""
        DELETE FROM household_services
        WHERE id=%s AND household_id=%s
    """, (service_id,household_id))

def compare_service_offers(household_service):
    """
    Comparação normalizada simples.
    - Se monthly_price estiver disponível, compara custo mensal.
    - Para eletricidade/gás, se houver preços unitários,
      estima impacto usando o rácio relativo entre tarifa atual e alternativa.
    """
    service_type = household_service["service_type"]
    current_monthly = float(household_service["monthly_cost"] or 0)
    current_unit = (
        float(household_service["unit_price"])
        if household_service.get("unit_price") is not None
        else None
    )
    current_daily = (
        float(household_service["daily_price"])
        if household_service.get("daily_price") is not None
        else None
    )

    offers = list_market_offers(service_type=service_type)
    results = []

    for offer in offers:
        alt_monthly = (
            float(offer["monthly_price"])
            if offer["monthly_price"] is not None
            else None
        )
        alt_unit = (
            float(offer["unit_price"])
            if offer["unit_price"] is not None
            else None
        )
        alt_daily = (
            float(offer["daily_price"])
            if offer["daily_price"] is not None
            else None
        )

        estimated_monthly = alt_monthly
        comparison_method = "monthly_price"

        # Para energia, usa tarifa unitária quando não existe mensalidade direta.
        if estimated_monthly is None and current_monthly > 0 and current_unit and alt_unit:
            ratio = alt_unit / current_unit if current_unit > 0 else 1
            estimated_monthly = current_monthly * ratio
            comparison_method = "unit_price_ratio"

            if current_daily and alt_daily:
                # Ajuste simples do componente diário (30 dias).
                current_daily_month = current_daily * 30
                alt_daily_month = alt_daily * 30
                variable_current = max(0, current_monthly - current_daily_month)
                estimated_monthly = (
                    variable_current * ratio
                    + alt_daily_month
                )
                comparison_method = "unit_and_daily_price"

        if estimated_monthly is None or current_monthly <= 0:
            saving_month = None
            saving_year = None
            saving_pct = None
        else:
            saving_month = current_monthly - estimated_monthly
            saving_year = saving_month * 12
            saving_pct = (
                saving_month / current_monthly * 100
                if current_monthly > 0 else 0
            )

        results.append({
            "offer_id": offer["id"],
            "provider_name": offer["provider_name"],
            "plan_name": offer["plan_name"],
            "service_type": offer["service_type"],
            "estimated_monthly_cost": (
                round(estimated_monthly, 2)
                if estimated_monthly is not None
                else None
            ),
            "saving_month": (
                round(saving_month, 2)
                if saving_month is not None else None
            ),
            "saving_year": (
                round(saving_year, 2)
                if saving_year is not None else None
            ),
            "saving_pct": (
                round(saving_pct, 1)
                if saving_pct is not None else None
            ),
            "comparison_method": comparison_method,
            "contract_months": offer["contract_months"],
            "conditions": offer["conditions"],
            "source": offer["source"],
            "source_url": offer["source_url"],
            "date_checked": offer["date_checked"],
        })

    return sorted(
        results,
        key=lambda r: (
            r["saving_year"] is None,
            -(r["saving_year"] or -999999)
        )
    )

def get_market_savings_summary(household_id):
    services = list_household_services(household_id)
    total_current = 0.0
    total_best = 0.0
    rows = []

    for service in services:
        current = float(service["monthly_cost"] or 0)
        total_current += current

        comparisons = compare_service_offers(service)
        useful = [
            r for r in comparisons
            if r["estimated_monthly_cost"] is not None
        ]

        if useful:
            best = min(
                useful,
                key=lambda x: x["estimated_monthly_cost"]
            )
            best_cost = float(best["estimated_monthly_cost"])
            total_best += best_cost

            rows.append({
                "service_id": service["id"],
                "service_type": service["service_type"],
                "current_provider": service["provider_name"],
                "current_monthly": current,
                "best_provider": best["provider_name"],
                "best_plan": best["plan_name"],
                "best_monthly": best_cost,
                "saving_month": round(current - best_cost, 2),
                "saving_year": round((current - best_cost) * 12, 2),
                "date_checked": best["date_checked"],
            })
        else:
            total_best += current

    return {
        "current_monthly_total": round(total_current, 2),
        "best_monthly_total": round(total_best, 2),
        "potential_monthly_saving": round(total_current-total_best, 2),
        "potential_annual_saving": round((total_current-total_best)*12, 2),
        "rows": rows
    }


# ============================================================
# V2.4 — Recolha automática, histórico e alertas de mercado
# ============================================================

def list_market_sources(active_only=False):
    sql = """
        SELECT
            id, name, service_type, source_type, endpoint_url,
            config_json, default_validity_days,
            last_run_at, last_status, last_error,
            is_active, created_at, updated_at
        FROM market_sources
        WHERE 1=1
    """
    params = []

    if active_only:
        sql += " AND is_active=1"

    sql += " ORDER BY service_type,name"
    return fetch_all(sql, tuple(params))

def create_market_source(
    name, service_type, source_type, endpoint_url,
    config_json=None, default_validity_days=7, is_active=True
):
    return execute("""
        INSERT INTO market_sources(
            name,service_type,source_type,endpoint_url,
            config_json,default_validity_days,is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s)
    """, (
        name,service_type,source_type,endpoint_url,
        config_json,default_validity_days,
        1 if is_active else 0
    ))

def update_market_source(
    source_id, name, service_type, source_type,
    endpoint_url, config_json=None,
    default_validity_days=7, is_active=True
):
    execute("""
        UPDATE market_sources
        SET name=%s,
            service_type=%s,
            source_type=%s,
            endpoint_url=%s,
            config_json=%s,
            default_validity_days=%s,
            is_active=%s,
            updated_at=NOW()
        WHERE id=%s
    """, (
        name,service_type,source_type,endpoint_url,
        config_json,default_validity_days,
        1 if is_active else 0,
        source_id
    ))

def delete_market_source(source_id):
    execute("""
        DELETE FROM market_sources
        WHERE id=%s
    """, (source_id,))

def update_market_source_run(source_id, status, error=None):
    execute("""
        UPDATE market_sources
        SET last_run_at=NOW(),
            last_status=%s,
            last_error=%s,
            updated_at=NOW()
        WHERE id=%s
    """, (status,error,source_id))

def find_or_create_market_provider(name, service_type, website=None):
    row = fetch_one("""
        SELECT id
        FROM market_providers
        WHERE name=%s AND service_type=%s
        LIMIT 1
    """, (name,service_type))

    if row:
        return row["id"]

    return create_market_provider(
        name=name,
        service_type=service_type,
        website=website
    )

def find_market_offer(provider_id, plan_name):
    return fetch_one("""
        SELECT *
        FROM market_offers
        WHERE provider_id=%s
          AND plan_name=%s
        LIMIT 1
    """, (provider_id,plan_name))

def upsert_market_offer_from_source(
    source_id, provider_id, plan_name,
    monthly_price=None, unit_price=None, daily_price=None,
    contract_months=None, conditions=None,
    source=None, source_url=None,
    date_checked=None, valid_until=None
):
    existing = find_market_offer(provider_id, plan_name)

    if existing:
        execute("""
            UPDATE market_offers
            SET monthly_price=%s,
                unit_price=%s,
                daily_price=%s,
                contract_months=%s,
                conditions=%s,
                source=%s,
                source_url=%s,
                date_checked=%s,
                valid_until=%s,
                source_id=%s,
                is_active=1,
                updated_at=NOW()
            WHERE id=%s
        """, (
            monthly_price,unit_price,daily_price,
            contract_months,conditions,source,
            source_url,date_checked,valid_until,
            source_id,existing["id"]
        ))
        offer_id = existing["id"]
    else:
        offer_id = execute("""
            INSERT INTO market_offers(
                provider_id,plan_name,monthly_price,unit_price,daily_price,
                contract_months,conditions,source,source_url,date_checked,
                valid_until,source_id,is_active
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
        """, (
            provider_id,plan_name,monthly_price,unit_price,daily_price,
            contract_months,conditions,source,source_url,date_checked,
            valid_until,source_id
        ))

    return offer_id

def add_market_offer_history(
    offer_id, monthly_price=None, unit_price=None,
    daily_price=None, date_checked=None, source_id=None
):
    last = fetch_one("""
        SELECT monthly_price,unit_price,daily_price
        FROM market_offer_history
        WHERE offer_id=%s
        ORDER BY observed_at DESC,id DESC
        LIMIT 1
    """, (offer_id,))

    current_tuple = (
        float(monthly_price) if monthly_price is not None else None,
        float(unit_price) if unit_price is not None else None,
        float(daily_price) if daily_price is not None else None
    )

    if last:
        previous_tuple = (
            float(last["monthly_price"]) if last["monthly_price"] is not None else None,
            float(last["unit_price"]) if last["unit_price"] is not None else None,
            float(last["daily_price"]) if last["daily_price"] is not None else None
        )
        if current_tuple == previous_tuple:
            return None

    return execute("""
        INSERT INTO market_offer_history(
            offer_id,source_id,monthly_price,unit_price,daily_price,
            checked_date,observed_at
        )
        VALUES(%s,%s,%s,%s,%s,%s,NOW())
    """, (
        offer_id,source_id,monthly_price,unit_price,daily_price,
        date_checked
    ))

def list_market_offer_history(offer_id, limit_rows=24):
    return fetch_all("""
        SELECT
            id,offer_id,source_id,
            monthly_price,unit_price,daily_price,
            checked_date,observed_at
        FROM market_offer_history
        WHERE offer_id=%s
        ORDER BY observed_at DESC,id DESC
        LIMIT %s
    """, (offer_id,limit_rows))

def expire_old_market_offers():
    execute("""
        UPDATE market_offers
        SET is_active=0,
            updated_at=NOW()
        WHERE valid_until IS NOT NULL
          AND valid_until < CURDATE()
          AND is_active=1
    """)

def list_market_offers_valid(service_type=None, provider_id=None):
    sql = """
        SELECT
            mo.id,
            mo.provider_id,
            mp.name AS provider_name,
            mp.service_type,
            mo.plan_name,
            mo.monthly_price,
            mo.unit_price,
            mo.daily_price,
            mo.contract_months,
            mo.conditions,
            mo.source,
            mo.source_url,
            mo.date_checked,
            mo.valid_until,
            mo.source_id,
            mo.is_active,
            mo.created_at,
            mo.updated_at
        FROM market_offers mo
        JOIN market_providers mp ON mp.id=mo.provider_id
        WHERE mo.is_active=1
          AND mp.is_active=1
          AND (mo.valid_until IS NULL OR mo.valid_until >= CURDATE())
    """
    params = []

    if service_type:
        sql += " AND mp.service_type=%s"
        params.append(service_type)

    if provider_id:
        sql += " AND mo.provider_id=%s"
        params.append(provider_id)

    sql += " ORDER BY mp.service_type,mo.monthly_price,mp.name,mo.plan_name"
    return fetch_all(sql, tuple(params))

def compare_service_offers_v24(household_service):
    service_type = household_service["service_type"]
    current_monthly = float(household_service["monthly_cost"] or 0)
    current_unit = (
        float(household_service["unit_price"])
        if household_service.get("unit_price") is not None
        else None
    )
    current_daily = (
        float(household_service["daily_price"])
        if household_service.get("daily_price") is not None
        else None
    )

    offers = list_market_offers_valid(service_type=service_type)
    results = []

    for offer in offers:
        alt_monthly = (
            float(offer["monthly_price"])
            if offer["monthly_price"] is not None
            else None
        )
        alt_unit = (
            float(offer["unit_price"])
            if offer["unit_price"] is not None
            else None
        )
        alt_daily = (
            float(offer["daily_price"])
            if offer["daily_price"] is not None
            else None
        )

        estimated_monthly = alt_monthly
        method = "monthly_price"

        if estimated_monthly is None and current_monthly > 0 and current_unit and alt_unit:
            ratio = alt_unit / current_unit if current_unit > 0 else 1
            estimated_monthly = current_monthly * ratio
            method = "unit_price_ratio"

            if current_daily and alt_daily:
                current_daily_month = current_daily * 30
                variable_current = max(0, current_monthly-current_daily_month)
                estimated_monthly = (
                    variable_current * ratio
                    + alt_daily * 30
                )
                method = "unit_and_daily_price"

        if estimated_monthly is None or current_monthly <= 0:
            saving_month = saving_year = saving_pct = None
        else:
            saving_month = current_monthly-estimated_monthly
            saving_year = saving_month*12
            saving_pct = saving_month/current_monthly*100

        results.append({
            "offer_id": offer["id"],
            "provider_name": offer["provider_name"],
            "plan_name": offer["plan_name"],
            "service_type": offer["service_type"],
            "estimated_monthly_cost": round(estimated_monthly,2) if estimated_monthly is not None else None,
            "saving_month": round(saving_month,2) if saving_month is not None else None,
            "saving_year": round(saving_year,2) if saving_year is not None else None,
            "saving_pct": round(saving_pct,1) if saving_pct is not None else None,
            "comparison_method": method,
            "contract_months": offer["contract_months"],
            "conditions": offer["conditions"],
            "source": offer["source"],
            "source_url": offer["source_url"],
            "date_checked": offer["date_checked"],
            "valid_until": offer["valid_until"],
        })

    return sorted(
        results,
        key=lambda r: (
            r["saving_year"] is None,
            -(r["saving_year"] or -999999)
        )
    )

def refresh_market_alerts(household_id, minimum_annual_saving=60):
    services = list_household_services(household_id)
    created = 0

    for service in services:
        comparisons = compare_service_offers_v24(service)
        useful = [
            r for r in comparisons
            if r["saving_year"] is not None
            and r["saving_year"] >= minimum_annual_saving
        ]

        if not useful:
            continue

        best = useful[0]

        existing = fetch_one("""
            SELECT id
            FROM market_alerts
            WHERE household_id=%s
              AND household_service_id=%s
              AND offer_id=%s
              AND status='new'
            LIMIT 1
        """, (
            household_id,
            service["id"],
            best["offer_id"]
        ))

        if existing:
            execute("""
                UPDATE market_alerts
                SET potential_monthly_saving=%s,
                    potential_annual_saving=%s,
                    message=%s,
                    updated_at=NOW()
                WHERE id=%s
            """, (
                best["saving_month"],
                best["saving_year"],
                f"Alternativa {best['provider_name']} / {best['plan_name']} "
                f"pode poupar cerca de {best['saving_year']:.2f} €/ano.",
                existing["id"]
            ))
        else:
            execute("""
                INSERT INTO market_alerts(
                    household_id,household_service_id,offer_id,
                    potential_monthly_saving,potential_annual_saving,
                    message,status
                )
                VALUES(%s,%s,%s,%s,%s,%s,'new')
            """, (
                household_id,
                service["id"],
                best["offer_id"],
                best["saving_month"],
                best["saving_year"],
                f"Alternativa {best['provider_name']} / {best['plan_name']} "
                f"pode poupar cerca de {best['saving_year']:.2f} €/ano."
            ))
            created += 1

    return created

def list_market_alerts(household_id, status=None, limit_rows=50):
    sql = """
        SELECT
            ma.id,
            ma.household_service_id,
            ma.offer_id,
            ma.potential_monthly_saving,
            ma.potential_annual_saving,
            ma.message,
            ma.status,
            ma.created_at,
            ma.updated_at,
            hs.service_type,
            hs.provider_name AS current_provider,
            mp.name AS alternative_provider,
            mo.plan_name AS alternative_plan,
            mo.valid_until
        FROM market_alerts ma
        JOIN household_services hs ON hs.id=ma.household_service_id
        JOIN market_offers mo ON mo.id=ma.offer_id
        JOIN market_providers mp ON mp.id=mo.provider_id
        WHERE ma.household_id=%s
    """
    params = [household_id]

    if status:
        sql += " AND ma.status=%s"
        params.append(status)

    sql += " ORDER BY ma.created_at DESC LIMIT %s"
    params.append(limit_rows)
    return fetch_all(sql, tuple(params))

def update_market_alert_status(alert_id, household_id, status):
    execute("""
        UPDATE market_alerts
        SET status=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (status,alert_id,household_id))

def get_market_freshness_summary():
    row = fetch_one("""
        SELECT
            COUNT(*) AS total_offers,
            SUM(CASE
                WHEN is_active=1
                 AND (valid_until IS NULL OR valid_until >= CURDATE())
                THEN 1 ELSE 0 END
            ) AS valid_offers,
            SUM(CASE
                WHEN valid_until IS NOT NULL
                 AND valid_until < CURDATE()
                THEN 1 ELSE 0 END
            ) AS expired_offers,
            MAX(date_checked) AS last_checked
        FROM market_offers
    """)
    return row or {
        "total_offers":0,
        "valid_offers":0,
        "expired_offers":0,
        "last_checked":None
    }


# ============================================================
# V2.5 — Contratos, associação documental e notificações
# ============================================================

def get_household_primary_email(household_id):
    row = fetch_one("""
        SELECT u.email
        FROM household_members hm
        JOIN users u ON u.id=hm.user_id
        WHERE hm.household_id=%s
          AND u.is_active=1
          AND u.email IS NOT NULL
          AND u.email <> ''
        ORDER BY hm.id
        LIMIT 1
    """, (household_id,))
    return row["email"] if row else None

def list_notification_settings(household_id):
    return fetch_one("""
        SELECT
            household_id,
            email_enabled,
            email_to,
            notify_market_better_offer,
            notify_contract_end,
            notify_price_increase,
            contract_warning_days,
            minimum_market_annual_saving,
            minimum_price_increase_pct,
            updated_at
        FROM household_notification_settings
        WHERE household_id=%s
        LIMIT 1
    """, (household_id,))

def save_notification_settings(
    household_id, email_enabled, email_to,
    notify_market_better_offer=True,
    notify_contract_end=True,
    notify_price_increase=True,
    contract_warning_days=30,
    minimum_market_annual_saving=60,
    minimum_price_increase_pct=5
):
    existing = list_notification_settings(household_id)

    if existing:
        execute("""
            UPDATE household_notification_settings
            SET email_enabled=%s,
                email_to=%s,
                notify_market_better_offer=%s,
                notify_contract_end=%s,
                notify_price_increase=%s,
                contract_warning_days=%s,
                minimum_market_annual_saving=%s,
                minimum_price_increase_pct=%s,
                updated_at=NOW()
            WHERE household_id=%s
        """, (
            1 if email_enabled else 0,
            email_to,
            1 if notify_market_better_offer else 0,
            1 if notify_contract_end else 0,
            1 if notify_price_increase else 0,
            contract_warning_days,
            minimum_market_annual_saving,
            minimum_price_increase_pct,
            household_id
        ))
    else:
        execute("""
            INSERT INTO household_notification_settings(
                household_id,email_enabled,email_to,
                notify_market_better_offer,notify_contract_end,
                notify_price_increase,contract_warning_days,
                minimum_market_annual_saving,minimum_price_increase_pct
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            household_id,
            1 if email_enabled else 0,
            email_to,
            1 if notify_market_better_offer else 0,
            1 if notify_contract_end else 0,
            1 if notify_price_increase else 0,
            contract_warning_days,
            minimum_market_annual_saving,
            minimum_price_increase_pct
        ))

def list_household_service_price_history(service_id, household_id, limit_rows=24):
    return fetch_all("""
        SELECT
            id,household_service_id,
            monthly_cost,unit_price,daily_price,
            source,observed_at
        FROM household_service_price_history
        WHERE household_service_id=%s
          AND household_id=%s
        ORDER BY observed_at DESC,id DESC
        LIMIT %s
    """, (service_id,household_id,limit_rows))

def add_household_service_price_history(
    service_id, household_id,
    monthly_cost=None, unit_price=None, daily_price=None,
    source="manual"
):
    last = fetch_one("""
        SELECT monthly_cost,unit_price,daily_price
        FROM household_service_price_history
        WHERE household_service_id=%s
          AND household_id=%s
        ORDER BY observed_at DESC,id DESC
        LIMIT 1
    """, (service_id,household_id))

    current_tuple = (
        float(monthly_cost) if monthly_cost is not None else None,
        float(unit_price) if unit_price is not None else None,
        float(daily_price) if daily_price is not None else None,
    )

    if last:
        previous_tuple = (
            float(last["monthly_cost"]) if last["monthly_cost"] is not None else None,
            float(last["unit_price"]) if last["unit_price"] is not None else None,
            float(last["daily_price"]) if last["daily_price"] is not None else None,
        )
        if current_tuple == previous_tuple:
            return None

    return execute("""
        INSERT INTO household_service_price_history(
            household_id,household_service_id,
            monthly_cost,unit_price,daily_price,
            source,observed_at
        )
        VALUES(%s,%s,%s,%s,%s,%s,NOW())
    """, (
        household_id,service_id,
        monthly_cost,unit_price,daily_price,
        source
    ))

def get_household_service(service_id, household_id):
    return fetch_one("""
        SELECT *
        FROM household_services
        WHERE id=%s AND household_id=%s
        LIMIT 1
    """, (service_id,household_id))

def update_household_service_v25(
    service_id, household_id, provider_name, plan_name=None,
    monthly_cost=None, unit_price=None, daily_price=None,
    contract_start_date=None, contract_end_date=None,
    fidelity_end_date=None, contract_reference=None,
    source_document_id=None, notes=None, is_active=True
):
    execute("""
        UPDATE household_services
        SET provider_name=%s,
            plan_name=%s,
            monthly_cost=%s,
            unit_price=%s,
            daily_price=%s,
            contract_start_date=%s,
            contract_end_date=%s,
            fidelity_end_date=%s,
            contract_reference=%s,
            source_document_id=%s,
            notes=%s,
            is_active=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (
        provider_name,plan_name,monthly_cost,unit_price,daily_price,
        contract_start_date,contract_end_date,fidelity_end_date,
        contract_reference,source_document_id,notes,
        1 if is_active else 0,
        service_id,household_id
    ))

    add_household_service_price_history(
        service_id,
        household_id,
        monthly_cost,
        unit_price,
        daily_price,
        source="service_update"
    )

def create_household_service_v25(
    household_id, service_type, provider_name,
    plan_name=None, monthly_cost=None,
    unit_price=None, daily_price=None,
    contract_start_date=None, contract_end_date=None,
    fidelity_end_date=None, contract_reference=None,
    source_document_id=None, notes=None
):
    service_id = execute("""
        INSERT INTO household_services(
            household_id,service_type,provider_name,plan_name,
            monthly_cost,unit_price,daily_price,
            contract_start_date,contract_end_date,fidelity_end_date,
            contract_reference,source_document_id,notes,is_active
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
    """, (
        household_id,service_type,provider_name,plan_name,
        monthly_cost,unit_price,daily_price,
        contract_start_date,contract_end_date,fidelity_end_date,
        contract_reference,source_document_id,notes
    ))

    add_household_service_price_history(
        service_id,
        household_id,
        monthly_cost,
        unit_price,
        daily_price,
        source="service_create"
    )
    return service_id

def normalize_provider_token(value):
    if not value:
        return ""
    value = value.lower().strip()

    replacements = {
        "meo - serviços de comunicações": "meo",
        "nos comunicações": "nos",
        "vodafone portugal": "vodafone",
        "digi portugal": "digi",
        "edp comercial": "edp",
        "endesa energia": "endesa",
        "goldenergy": "goldenergy",
    }

    for old,new in replacements.items():
        if old in value:
            return new

    cleaned = []
    for ch in value:
        cleaned.append(ch if ch.isalnum() or ch.isspace() else " ")
    return " ".join("".join(cleaned).split())

def detect_service_type_from_text(text, supplier=None):
    haystack = f"{supplier or ''} {text or ''}".lower()

    rules = {
        "Eletricidade": [
            "eletricidade","energia elétrica","kwh","potência contratada",
            "edp","endesa","goldenergy","iberdrola"
        ],
        "Gás": [
            "gás natural","m3","galp gás","goldenergy gás"
        ],
        "Telecomunicações": [
            "fibra","televisão","tv net voz","meo","nos","vodafone","digi",
            "telecomunicações"
        ],
        "Internet": [
            "internet","fibra ótica","fibra optica"
        ],
        "Telemóvel": [
            "telemóvel","telemovel","dados móveis","dados moveis"
        ],
        "Seguros": [
            "seguro","apólice","apolice","prémio de seguro","premio de seguro"
        ],
        "Streaming": [
            "netflix","spotify","disney","hbo","max","prime video"
        ],
        "Crédito": [
            "prestação","prestacao","crédito","credito","taeg","tan"
        ],
    }

    for service_type, keywords in rules.items():
        if any(keyword in haystack for keyword in keywords):
            return service_type

    return "Outros"

def suggest_document_service_link(document_id, household_id):
    doc = get_document_by_id(document_id, household_id)
    if not doc:
        return None

    supplier = doc.get("extracted_supplier") or ""
    text = doc.get("ocr_text") or ""
    service_type = detect_service_type_from_text(text, supplier)
    supplier_token = normalize_provider_token(supplier)

    services = list_household_services(household_id)

    best = None
    best_score = 0

    for service in services:
        score = 0
        provider_token = normalize_provider_token(service["provider_name"])

        if service["service_type"] == service_type:
            score += 50

        if supplier_token and provider_token:
            if supplier_token == provider_token:
                score += 45
            elif supplier_token in provider_token or provider_token in supplier_token:
                score += 30

        if score > best_score:
            best = service
            best_score = score

    confidence = min(100, best_score)

    return {
        "document_id": document_id,
        "supplier": supplier,
        "service_type": service_type,
        "suggested_service_id": best["id"] if best else None,
        "suggested_service_label": (
            f"{best['service_type']} — {best['provider_name']}"
            if best else None
        ),
        "confidence": confidence
    }

def link_document_to_service(document_id, household_id, service_id, confidence=None, method="manual"):
    existing = fetch_one("""
        SELECT id
        FROM document_service_links
        WHERE document_id=%s
          AND household_id=%s
        LIMIT 1
    """, (document_id,household_id))

    if existing:
        execute("""
            UPDATE document_service_links
            SET household_service_id=%s,
                confidence=%s,
                method=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (
            service_id,confidence,method,existing["id"]
        ))
    else:
        execute("""
            INSERT INTO document_service_links(
                household_id,document_id,household_service_id,
                confidence,method
            )
            VALUES(%s,%s,%s,%s,%s)
        """, (
            household_id,document_id,service_id,
            confidence,method
        ))

def get_document_service_link(document_id, household_id):
    return fetch_one("""
        SELECT
            dsl.id,
            dsl.document_id,
            dsl.household_service_id,
            dsl.confidence,
            dsl.method,
            hs.service_type,
            hs.provider_name,
            hs.plan_name
        FROM document_service_links dsl
        JOIN household_services hs
          ON hs.id=dsl.household_service_id
        WHERE dsl.document_id=%s
          AND dsl.household_id=%s
        LIMIT 1
    """, (document_id,household_id))

def list_unlinked_service_documents(household_id, limit_rows=100):
    return fetch_all("""
        SELECT
            d.id,
            d.original_name,
            d.document_type,
            d.extracted_supplier,
            d.extracted_document_date,
            d.extracted_total,
            d.ocr_status
        FROM documents d
        LEFT JOIN document_service_links dsl
          ON dsl.document_id=d.id
         AND dsl.household_id=d.household_id
        WHERE d.household_id=%s
          AND d.is_active=1
          AND dsl.id IS NULL
        ORDER BY d.created_at DESC
        LIMIT %s
    """, (household_id,limit_rows))

def refresh_contract_alerts(household_id):
    settings = list_notification_settings(household_id) or {}
    warning_days = int(settings.get("contract_warning_days") or 30)

    rows = fetch_all("""
        SELECT
            id,service_type,provider_name,plan_name,
            contract_end_date,fidelity_end_date
        FROM household_services
        WHERE household_id=%s
          AND is_active=1
          AND (
              contract_end_date IS NOT NULL
              OR fidelity_end_date IS NOT NULL
          )
    """, (household_id,))

    created = 0

    for service in rows:
        target_date = service["fidelity_end_date"] or service["contract_end_date"]
        if not target_date:
            continue

        days_left = (target_date - date.today()).days

        if 0 <= days_left <= warning_days:
            alert_type = "contract_end"
            title = f"Fim de fidelização: {service['provider_name']}"
            message = (
                f"{service['service_type']} — {service['provider_name']} "
                f"termina em {days_left} dia(s), a {target_date}."
            )

            existing = fetch_one("""
                SELECT id
                FROM service_alerts
                WHERE household_id=%s
                  AND household_service_id=%s
                  AND alert_type=%s
                  AND status='new'
                LIMIT 1
            """, (household_id,service["id"],alert_type))

            if not existing:
                execute("""
                    INSERT INTO service_alerts(
                        household_id,household_service_id,
                        alert_type,title,message,status
                    )
                    VALUES(%s,%s,%s,%s,%s,'new')
                """, (
                    household_id,service["id"],
                    alert_type,title,message
                ))
                created += 1

    return created

def refresh_price_increase_alerts(household_id):
    settings = list_notification_settings(household_id) or {}
    minimum_pct = float(
        settings.get("minimum_price_increase_pct") or 5
    )

    services = list_household_services(household_id)
    created = 0

    for service in services:
        history = list_household_service_price_history(
            service["id"],
            household_id,
            2
        )

        if len(history) < 2:
            continue

        current = float(history[0]["monthly_cost"] or 0)
        previous = float(history[1]["monthly_cost"] or 0)

        if previous <= 0:
            continue

        pct = (current-previous)/previous*100

        if pct < minimum_pct:
            continue

        existing = fetch_one("""
            SELECT id
            FROM service_alerts
            WHERE household_id=%s
              AND household_service_id=%s
              AND alert_type='price_increase'
              AND status='new'
            LIMIT 1
        """, (household_id,service["id"]))

        if not existing:
            execute("""
                INSERT INTO service_alerts(
                    household_id,household_service_id,
                    alert_type,title,message,status
                )
                VALUES(%s,%s,'price_increase',%s,%s,'new')
            """, (
                household_id,
                service["id"],
                f"Aumento de preço: {service['provider_name']}",
                f"O custo mensal passou de {previous:.2f} € para "
                f"{current:.2f} € (+{pct:.1f}%)."
            ))
            created += 1

    return created

def list_service_alerts(household_id, status=None, limit_rows=100):
    sql = """
        SELECT
            sa.id,
            sa.household_service_id,
            sa.alert_type,
            sa.title,
            sa.message,
            sa.status,
            sa.created_at,
            sa.updated_at,
            hs.service_type,
            hs.provider_name,
            hs.plan_name
        FROM service_alerts sa
        JOIN household_services hs
          ON hs.id=sa.household_service_id
        WHERE sa.household_id=%s
    """
    params = [household_id]

    if status:
        sql += " AND sa.status=%s"
        params.append(status)

    sql += " ORDER BY sa.created_at DESC LIMIT %s"
    params.append(limit_rows)

    return fetch_all(sql, tuple(params))

def update_service_alert_status(alert_id, household_id, status):
    execute("""
        UPDATE service_alerts
        SET status=%s,
            updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (status,alert_id,household_id))

def create_email_notification(
    household_id, notification_type, subject, body,
    recipient, related_alert_id=None
):
    return execute("""
        INSERT INTO email_notifications(
            household_id,notification_type,
            subject,body,recipient,
            related_alert_id,status
        )
        VALUES(%s,%s,%s,%s,%s,%s,'pending')
    """, (
        household_id,notification_type,
        subject,body,recipient,
        related_alert_id
    ))

def list_pending_email_notifications(limit_rows=100):
    return fetch_all("""
        SELECT *
        FROM email_notifications
        WHERE status='pending'
        ORDER BY created_at
        LIMIT %s
    """, (limit_rows,))

def mark_email_notification_sent(notification_id):
    execute("""
        UPDATE email_notifications
        SET status='sent',
            sent_at=NOW(),
            last_error=NULL,
            updated_at=NOW()
        WHERE id=%s
    """, (notification_id,))

def mark_email_notification_error(notification_id, error):
    execute("""
        UPDATE email_notifications
        SET status='error',
            last_error=%s,
            updated_at=NOW()
        WHERE id=%s
    """, (str(error)[:2000],notification_id))

def queue_household_alert_emails(household_id):
    settings = list_notification_settings(household_id)

    if not settings or not settings["email_enabled"] or not settings["email_to"]:
        return 0

    created = 0
    recipient = settings["email_to"]

    if settings["notify_market_better_offer"]:
        market_alerts = list_market_alerts(
            household_id,
            status="new"
        )
        for alert in market_alerts:
            existing = fetch_one("""
                SELECT id
                FROM email_notifications
                WHERE household_id=%s
                  AND notification_type='market_better_offer'
                  AND related_alert_id=%s
                LIMIT 1
            """, (household_id,alert["id"]))

            if not existing:
                create_email_notification(
                    household_id,
                    "market_better_offer",
                    "Family Finance — Encontrámos uma oferta melhor",
                    alert["message"],
                    recipient,
                    alert["id"]
                )
                created += 1

    service_alerts = list_service_alerts(
        household_id,
        status="new"
    )

    for alert in service_alerts:
        if alert["alert_type"] == "contract_end" and not settings["notify_contract_end"]:
            continue
        if alert["alert_type"] == "price_increase" and not settings["notify_price_increase"]:
            continue

        existing = fetch_one("""
            SELECT id
            FROM email_notifications
            WHERE household_id=%s
              AND notification_type=%s
              AND related_alert_id=%s
            LIMIT 1
        """, (
            household_id,
            alert["alert_type"],
            alert["id"]
        ))

        if not existing:
            create_email_notification(
                household_id,
                alert["alert_type"],
                f"Family Finance — {alert['title']}",
                alert["message"],
                recipient,
                alert["id"]
            )
            created += 1

    return created


# ============================================================
# V2.6 — Inteligência de Contrato e decisão "mudar agora vs esperar"
# ============================================================

def get_contract_intelligence(service_id, household_id):
    return fetch_one("""
        SELECT *
        FROM contract_intelligence
        WHERE household_service_id=%s AND household_id=%s
        LIMIT 1
    """, (service_id,household_id))

def save_contract_intelligence(
    service_id, household_id, source_document_id=None,
    commitment_months=None, renewal_type=None,
    notice_days=None, early_exit_fee=None,
    extracted_end_date=None, extracted_fidelity_end=None,
    extraction_confidence=None, extraction_notes=None
):
    existing = get_contract_intelligence(service_id, household_id)
    params = (
        source_document_id,commitment_months,renewal_type,notice_days,
        early_exit_fee,extracted_end_date,extracted_fidelity_end,
        extraction_confidence,extraction_notes
    )
    if existing:
        execute("""
            UPDATE contract_intelligence
            SET source_document_id=%s,commitment_months=%s,renewal_type=%s,
                notice_days=%s,early_exit_fee=%s,extracted_end_date=%s,
                extracted_fidelity_end=%s,extraction_confidence=%s,
                extraction_notes=%s,updated_at=NOW()
            WHERE household_service_id=%s AND household_id=%s
        """, params + (service_id,household_id))
    else:
        execute("""
            INSERT INTO contract_intelligence(
                source_document_id,commitment_months,renewal_type,notice_days,
                early_exit_fee,extracted_end_date,extracted_fidelity_end,
                extraction_confidence,extraction_notes,
                household_service_id,household_id
            ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, params + (service_id,household_id))

def extract_contract_terms_from_text(text):
    """Conservative rule-based extraction. Returns suggestions for user confirmation."""
    import re as _re
    from datetime import datetime as _dt
    text = text or ""
    low = text.lower()
    result = {
        "commitment_months": None,
        "renewal_type": None,
        "notice_days": None,
        "early_exit_fee": None,
        "extracted_end_date": None,
        "extracted_fidelity_end": None,
        "confidence": 0.0,
        "notes": []
    }
    hits = 0

    m = _re.search(r'(?:fideliza[cç][aã]o|perman[eê]ncia)[^\d]{0,40}(\d{1,2})\s*mes', low)
    if m:
        result["commitment_months"] = int(m.group(1)); hits += 1

    m = _re.search(r'(?:pr[eé]-?aviso|aviso)[^\d]{0,30}(\d{1,3})\s*dias?', low)
    if m:
        result["notice_days"] = int(m.group(1)); hits += 1

    # Exit fee: only near termination/cancellation wording.
    m = _re.search(
        r'(?:rescis[aã]o|cancelamento|cessa[cç][aã]o|encargo)[^€\d]{0,80}'
        r'(\d{1,5}(?:[.,]\d{1,2})?)\s*€', low
    )
    if m:
        result["early_exit_fee"] = float(m.group(1).replace(",", ".")); hits += 1

    date_patterns = [
        r'(?:fim da fideliza[cç][aã]o|fideliza[cç][aã]o at[eé])[^0-9]{0,30}'
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        r'(?:fim do contrato|contrato at[eé])[^0-9]{0,30}'
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})'
    ]
    for idx, pat in enumerate(date_patterns):
        m = _re.search(pat, low)
        if m:
            try:
                parsed = _dt.strptime(m.group(1).replace("-", "/"), "%d/%m/%Y").date()
                if idx == 0:
                    result["extracted_fidelity_end"] = parsed
                else:
                    result["extracted_end_date"] = parsed
                hits += 1
            except Exception:
                pass

    if "renova automaticamente" in low or "renovação automática" in low:
        result["renewal_type"] = "automatic"; hits += 1
    elif "não renova" in low or "sem renovação" in low:
        result["renewal_type"] = "none"; hits += 1

    result["confidence"] = min(95.0, hits * 18.0)
    if hits == 0:
        result["notes"].append("Não foram encontrados termos contratuais suficientemente claros.")
    else:
        result["notes"].append("Dados extraídos por regras; confirmar com o contrato original.")
    return result

def extract_contract_terms_from_document(document_id, household_id):
    doc = get_document_by_id(document_id, household_id)
    if not doc:
        return None
    terms = extract_contract_terms_from_text(doc.get("ocr_text") or "")
    terms["document_id"] = document_id
    terms["supplier"] = doc.get("extracted_supplier")
    return terms

def calculate_switch_decision(service_id, household_id, reference_date=None):
    from datetime import date as _date
    reference_date = reference_date or _date.today()
    service = get_household_service(service_id, household_id)
    if not service:
        return None

    intelligence = get_contract_intelligence(service_id, household_id) or {}
    comparisons = compare_service_offers_v24(service)
    viable = [x for x in comparisons if (x.get("saving_month") or 0) > 0]
    if not viable:
        return {
            "service": service, "best_offer": None, "recommendation": "stay",
            "reason": "Não existe atualmente uma alternativa válida com poupança estimada.",
            "break_even_months": None, "switch_cost": 0.0, "net_12m_saving": 0.0
        }

    best = viable[0]
    monthly_saving = float(best.get("saving_month") or 0)
    exit_fee = float(intelligence.get("early_exit_fee") or 0)

    fidelity_end = (
        intelligence.get("extracted_fidelity_end")
        or service.get("fidelity_end_date")
        or service.get("contract_end_date")
    )
    days_to_free = max(0, (fidelity_end-reference_date).days) if fidelity_end else 0
    months_to_free = days_to_free / 30.44

    break_even = (exit_fee/monthly_saving) if monthly_saving > 0 else None
    net_12m = monthly_saving*12-exit_fee
    wait_saving = max(0.0, monthly_saving*(12-months_to_free)) if months_to_free < 12 else 0.0

    if exit_fee <= 0:
        recommendation = "switch_now"
        reason = "A alternativa poupa dinheiro e não existe penalização de saída registada."
    elif break_even is not None and break_even <= max(1.0, months_to_free):
        recommendation = "switch_now"
        reason = (
            f"A penalização é recuperada em cerca de {break_even:.1f} meses, "
            f"antes do fim estimado da fidelização."
        )
    elif days_to_free <= 45:
        recommendation = "wait"
        reason = (
            f"A fidelização termina em {days_to_free} dias; esperar tende a evitar "
            f"uma penalização de {exit_fee:.2f} €."
        )
    elif net_12m > wait_saving:
        recommendation = "switch_now"
        reason = "Mesmo incluindo a penalização, a poupança líquida estimada a 12 meses é superior."
    else:
        recommendation = "wait"
        reason = "A penalização atual reduz a vantagem de mudar já."

    ideal_date = reference_date if recommendation == "switch_now" else fidelity_end

    return {
        "service": service,
        "best_offer": best,
        "recommendation": recommendation,
        "reason": reason,
        "monthly_saving": round(monthly_saving,2),
        "annual_saving": round(monthly_saving*12,2),
        "switch_cost": round(exit_fee,2),
        "break_even_months": round(break_even,1) if break_even is not None else None,
        "net_12m_saving": round(net_12m,2),
        "fidelity_end": fidelity_end,
        "days_to_free": days_to_free,
        "ideal_switch_date": ideal_date
    }

def list_switch_decisions(household_id):
    return [
        calculate_switch_decision(s["id"], household_id)
        for s in list_household_services(household_id)
    ]

def get_financial_action_priorities(household_id):
    actions = []
    for decision in list_switch_decisions(household_id):
        if not decision or not decision.get("best_offer"):
            continue
        annual = float(decision.get("annual_saving") or 0)
        if annual <= 0:
            continue
        priority = min(100, int(annual/6))
        if decision["recommendation"] == "switch_now":
            priority = min(100, priority+20)
        if decision.get("days_to_free",999) <= 45:
            priority = min(100, priority+15)
        actions.append({
            "priority": priority,
            "type": "supplier_switch",
            "service_id": decision["service"]["id"],
            "title": f"Rever {decision['service']['service_type']} — {decision['service']['provider_name']}",
            "impact_year": annual,
            "recommendation": decision["recommendation"],
            "reason": decision["reason"]
        })

    try:
        for cut in get_cut_recommendations(household_id):
            impact = float(cut.get("annual_saving") or cut.get("potential_annual_saving") or 0)
            actions.append({
                "priority": min(100, int(impact/6)+10),
                "type": "expense_cut",
                "service_id": None,
                "title": cut.get("title") or cut.get("category") or "Reduzir despesa",
                "impact_year": impact,
                "recommendation": "review",
                "reason": cut.get("reason") or "Despesa com potencial de redução."
            })
    except Exception:
        pass

    return sorted(actions, key=lambda x: (-x["priority"], -x["impact_year"]))


# ============================================================
# V2.7 — Assistente Financeiro Familiar
# ============================================================

def get_monthly_category_comparison(household_id, year, month, limit_rows=10):
    prev_year, prev_month = get_previous_month(year, month)

    current = fetch_all("""
        SELECT
            c.id AS category_id,
            c.name AS category_name,
            SUM(eo.amount) AS total
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        JOIN categories c ON c.id=e.category_id
        WHERE eo.household_id=%s
          AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s
          AND eo.is_active=1
          AND e.is_active=1
        GROUP BY c.id,c.name
    """, (household_id,year,month))

    previous = fetch_all("""
        SELECT
            c.id AS category_id,
            c.name AS category_name,
            SUM(eo.amount) AS total
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        JOIN categories c ON c.id=e.category_id
        WHERE eo.household_id=%s
          AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s
          AND eo.is_active=1
          AND e.is_active=1
        GROUP BY c.id,c.name
    """, (household_id,prev_year,prev_month))

    prev_map = {
        int(r["category_id"]): float(r["total"] or 0)
        for r in previous
    }

    rows = []
    for r in current:
        total = float(r["total"] or 0)
        prev = prev_map.get(int(r["category_id"]), 0.0)
        diff = total-prev
        pct = (diff/prev*100) if prev > 0 else (100.0 if total > 0 else 0.0)

        rows.append({
            "category_id": r["category_id"],
            "category_name": r["category_name"],
            "current_total": round(total,2),
            "previous_total": round(prev,2),
            "difference": round(diff,2),
            "difference_pct": round(pct,1)
        })

    return sorted(
        rows,
        key=lambda x: abs(x["difference"]),
        reverse=True
    )[:limit_rows]

def get_monthly_supplier_comparison(household_id, year, month, limit_rows=10):
    prev_year, prev_month = get_previous_month(year, month)

    def rows_for(y,m):
        return fetch_all("""
            SELECT
                COALESCE(NULLIF(TRIM(e.supplier),''),'Sem fornecedor') AS supplier,
                SUM(eo.amount) AS total
            FROM expense_occurrences eo
            JOIN expenses e ON e.id=eo.expense_id
            WHERE eo.household_id=%s
              AND YEAR(eo.occurrence_date)=%s
              AND MONTH(eo.occurrence_date)=%s
              AND eo.is_active=1
              AND e.is_active=1
            GROUP BY supplier
        """, (household_id,y,m))

    current = rows_for(year,month)
    previous = rows_for(prev_year,prev_month)
    prev_map = {r["supplier"]: float(r["total"] or 0) for r in previous}

    result = []
    for r in current:
        total = float(r["total"] or 0)
        prev = prev_map.get(r["supplier"], 0.0)
        diff = total-prev
        pct = (diff/prev*100) if prev > 0 else (100.0 if total > 0 else 0.0)
        result.append({
            "supplier": r["supplier"],
            "current_total": round(total,2),
            "previous_total": round(prev,2),
            "difference": round(diff,2),
            "difference_pct": round(pct,1)
        })

    return sorted(result,key=lambda x: abs(x["difference"]),reverse=True)[:limit_rows]

def get_monthly_assistant_snapshot(household_id, year, month):
    summary = get_month_summary(household_id, year, month)
    comparison = get_month_comparison(household_id, year, month)
    risk = get_financial_risk_score(household_id, year, month)
    forecast = get_financial_forecast(household_id, year, month)
    anomalies = detect_expense_anomalies(household_id)
    category_changes = get_monthly_category_comparison(
        household_id, year, month, 10
    )
    supplier_changes = get_monthly_supplier_comparison(
        household_id, year, month, 10
    )
    market = get_market_savings_summary(household_id)
    priorities = get_financial_action_priorities(household_id)

    return {
        "year": year,
        "month": month,
        "summary": summary,
        "comparison": comparison,
        "risk": risk,
        "forecast": forecast,
        "anomalies": anomalies,
        "category_changes": category_changes,
        "supplier_changes": supplier_changes,
        "market": market,
        "priorities": priorities[:5],
    }

def build_monthly_financial_narrative(household_id, year, month):
    data = get_monthly_assistant_snapshot(household_id, year, month)

    summary = data["summary"]
    risk = data["risk"]
    forecast = data["forecast"]
    market = data["market"]

    income = float(summary.get("income") or 0)
    expense = float(summary.get("expense") or 0)
    balance = float(summary.get("balance") or 0)
    savings_rate = float(summary.get("savings_rate") or 0)

    paragraphs = []

    paragraphs.append(
        f"No período analisado, o agregado registou {income:.2f} € de rendimentos "
        f"e {expense:.2f} € de despesas, resultando num saldo de {balance:.2f} €. "
        f"A taxa de poupança ficou em {savings_rate:.1f}%."
    )

    changes = [
        c for c in data["category_changes"]
        if abs(float(c["difference"])) >= 10
    ]

    increases = [c for c in changes if c["difference"] > 0][:3]
    decreases = [c for c in changes if c["difference"] < 0][:2]

    if increases:
        txt = []
        for c in increases:
            txt.append(
                f"{c['category_name']} (+{c['difference']:.2f} €, "
                f"{c['difference_pct']:.1f}%)"
            )
        paragraphs.append(
            "As maiores subidas de despesa ocorreram em " + ", ".join(txt) + "."
        )

    if decreases:
        txt = []
        for c in decreases:
            txt.append(
                f"{c['category_name']} ({c['difference']:.2f} €)"
            )
        paragraphs.append(
            "Em sentido positivo, houve redução em " + ", ".join(txt) + "."
        )

    if data["anomalies"]:
        top = data["anomalies"][0]
        paragraphs.append(
            f"Foi detetado um comportamento fora do padrão em {top['category_name']}: "
            f"o valor atual está {top['deviation_pct']:.1f}% acima da média recente."
        )

    paragraphs.append(
        f"O score de risco financeiro é {float(risk['score']):.0f}/100 "
        f"({risk['label']}). "
        f"O saldo projetado para o final do mês é "
        f"{float(forecast['projected_balance']):.2f} €."
    )

    if market["potential_annual_saving"] > 0:
        paragraphs.append(
            f"As alternativas de mercado já registadas indicam uma poupança potencial "
            f"de cerca de {market['potential_monthly_saving']:.2f} € por mês, "
            f"ou {market['potential_annual_saving']:.2f} € por ano."
        )

    if data["priorities"]:
        paragraphs.append(
            "As ações com maior impacto para o próximo período são apresentadas "
            "na lista de prioridades abaixo."
        )

    return "\n\n".join(paragraphs), data

def generate_next_month_actions(household_id, year, month, max_actions=5):
    snapshot = get_monthly_assistant_snapshot(household_id, year, month)
    actions = []

    # 1. Existing strategic priorities
    for item in snapshot["priorities"]:
        actions.append({
            "priority": int(item.get("priority") or 0),
            "title": item.get("title") or "Rever despesa",
            "impact_year": float(item.get("impact_year") or 0),
            "reason": item.get("reason") or "",
            "source": item.get("type") or "assistant"
        })

    # 2. Budget / category increases
    for c in snapshot["category_changes"]:
        if c["difference"] > 25 and c["difference_pct"] > 10:
            priority = min(95, int(c["difference"] / 3) + 25)
            actions.append({
                "priority": priority,
                "title": f"Rever a categoria {c['category_name']}",
                "impact_year": round(max(0,c["difference"]) * 12,2),
                "reason": (
                    f"A despesa subiu {c['difference']:.2f} € "
                    f"({c['difference_pct']:.1f}%) face ao mês anterior."
                ),
                "source": "category_change"
            })

    # 3. Risk-driven action
    risk = snapshot["risk"]
    if risk["level"] in ("high","critical"):
        actions.append({
            "priority": 100 if risk["level"] == "critical" else 90,
            "title": "Reduzir o risco financeiro do próximo mês",
            "impact_year": 0.0,
            "reason": (
                f"O score atual é {float(risk['score']):.0f}/100 ({risk['label']}). "
                "Prioriza despesas discricionárias e compromissos recorrentes."
            ),
            "source": "risk"
        })

    # Deduplicate by title
    dedup = {}
    for action in actions:
        title = action["title"].strip().lower()
        if title not in dedup or action["priority"] > dedup[title]["priority"]:
            dedup[title] = action

    ordered = sorted(
        dedup.values(),
        key=lambda x: (-x["priority"], -x["impact_year"])
    )[:max_actions]

    for idx, action in enumerate(ordered, start=1):
        action["rank"] = idx

    return ordered

def save_monthly_financial_brief(household_id, year, month):
    narrative, snapshot = build_monthly_financial_narrative(
        household_id, year, month
    )
    actions = generate_next_month_actions(
        household_id, year, month, 5
    )

    existing = fetch_one("""
        SELECT id
        FROM monthly_financial_briefs
        WHERE household_id=%s
          AND year_num=%s
          AND month_num=%s
        LIMIT 1
    """, (household_id,year,month))

    payload = json.dumps(snapshot, ensure_ascii=False, default=str)
    actions_json = json.dumps(actions, ensure_ascii=False, default=str)

    if existing:
        execute("""
            UPDATE monthly_financial_briefs
            SET narrative=%s,
                snapshot_json=%s,
                actions_json=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (
            narrative,payload,actions_json,existing["id"]
        ))
        return existing["id"]

    return execute("""
        INSERT INTO monthly_financial_briefs(
            household_id,year_num,month_num,
            narrative,snapshot_json,actions_json
        )
        VALUES(%s,%s,%s,%s,%s,%s)
    """, (
        household_id,year,month,
        narrative,payload,actions_json
    ))

def get_monthly_financial_brief(household_id, year, month):
    return fetch_one("""
        SELECT *
        FROM monthly_financial_briefs
        WHERE household_id=%s
          AND year_num=%s
          AND month_num=%s
        LIMIT 1
    """, (household_id,year,month))

def list_monthly_financial_briefs(household_id, limit_rows=12):
    return fetch_all("""
        SELECT
            id,year_num,month_num,narrative,
            snapshot_json,actions_json,
            created_at,updated_at
        FROM monthly_financial_briefs
        WHERE household_id=%s
        ORDER BY year_num DESC,month_num DESC
        LIMIT %s
    """, (household_id,limit_rows))


# ============================================================
# V2.8 — Objetivos e Plano Financeiro Familiar
# ============================================================

def get_recommended_category_limits(household_id, year, month, history_months=3):
    rows = fetch_all("""
        SELECT c.id AS category_id, c.name AS category_name,
               DATE_FORMAT(eo.occurrence_date,'%%Y-%%m') AS ym,
               SUM(eo.amount) AS total
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        JOIN categories c ON c.id=e.category_id
        WHERE eo.household_id=%s AND eo.is_active=1 AND e.is_active=1
          AND eo.occurrence_date >= DATE_SUB(
              STR_TO_DATE(CONCAT(%s,'-',LPAD(%s,2,'0'),'-01'),'%%Y-%%m-%%d'),
              INTERVAL %s MONTH
          )
        GROUP BY c.id,c.name,ym
        ORDER BY c.name,ym
    """, (household_id,year,month,history_months))
    by_category={}
    for r in rows:
        by_category.setdefault((r['category_id'],r['category_name']),[]).append(float(r['total'] or 0))
    result=[]
    for (category_id,category_name),values in by_category.items():
        if not values: continue
        avg=sum(values)/len(values)
        result.append({'category_id':category_id,'category_name':category_name,'historical_average':round(avg,2),'recommended_limit':round(max(0,avg*0.95),2),'months_considered':len(values)})
    return sorted(result,key=lambda x:x['recommended_limit'],reverse=True)

def get_weekly_spending_status(household_id, year, month):
    rows=fetch_all("""
        SELECT WEEK(eo.occurrence_date,1) AS week_num,
               MIN(eo.occurrence_date) AS week_start,
               MAX(eo.occurrence_date) AS week_end,
               SUM(eo.amount) AS total
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        WHERE eo.household_id=%s AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s AND eo.is_active=1 AND e.is_active=1
        GROUP BY WEEK(eo.occurrence_date,1) ORDER BY week_num
    """,(household_id,year,month))
    return [{'week_num':r['week_num'],'week_start':r['week_start'],'week_end':r['week_end'],'total':round(float(r['total'] or 0),2)} for r in rows]

def calculate_monthly_plan(household_id, year, month):
    summary=get_month_summary(household_id,year,month)
    forecast=get_financial_forecast(household_id,year,month)
    risk=get_financial_risk_score(household_id,year,month)
    category_limits=get_recommended_category_limits(household_id,year,month,3)
    actions=generate_next_month_actions(household_id,year,month,5)
    income=float(summary.get('income') or 0); expense=float(summary.get('expense') or 0)
    projected_expense=float(forecast.get('projected_expense') or expense)
    risk_score=float(risk.get('score') or 0)
    target_rate=0.05 if risk_score>=75 else 0.10 if risk_score>=50 else 0.15 if risk_score>=25 else 0.20
    target_saving=max(0.0,income*target_rate) if income>0 else 0.0
    spend_cap=max(0.0,income-target_saving) if income>0 else 0.0
    weekly_cap=spend_cap/4.345 if spend_cap>0 else 0.0
    return {'income':round(income,2),'current_expense':round(expense,2),'projected_expense':round(projected_expense,2),'target_savings_rate':round(target_rate*100,1),'target_saving':round(target_saving,2),'spend_cap':round(spend_cap,2),'weekly_cap':round(weekly_cap,2),'risk_score':round(risk_score,1),'risk_label':risk.get('label'),'category_limits':category_limits,'actions':actions}

def save_monthly_financial_plan(household_id, year, month):
    plan=calculate_monthly_plan(household_id,year,month)
    payload=json.dumps(plan,ensure_ascii=False,default=str)
    existing=fetch_one("SELECT id FROM monthly_financial_plans WHERE household_id=%s AND year_num=%s AND month_num=%s LIMIT 1",(household_id,year,month))
    if existing:
        execute("UPDATE monthly_financial_plans SET plan_json=%s,updated_at=NOW() WHERE id=%s",(payload,existing['id']))
        return existing['id']
    return execute("INSERT INTO monthly_financial_plans(household_id,year_num,month_num,plan_json) VALUES(%s,%s,%s,%s)",(household_id,year,month,payload))

def get_monthly_financial_plan(household_id, year, month):
    return fetch_one("SELECT * FROM monthly_financial_plans WHERE household_id=%s AND year_num=%s AND month_num=%s LIMIT 1",(household_id,year,month))

def create_savings_challenge(household_id,title,target_amount,start_date,end_date,category_id=None,notes=None):
    return execute("""INSERT INTO savings_challenges(household_id,title,target_amount,start_date,end_date,category_id,notes,status) VALUES(%s,%s,%s,%s,%s,%s,%s,'active')""",(household_id,title,target_amount,start_date,end_date,category_id,notes))

def list_savings_challenges(household_id,status=None):
    sql="""SELECT sc.id,sc.title,sc.target_amount,sc.start_date,sc.end_date,sc.category_id,c.name AS category_name,sc.notes,sc.status,sc.created_at,sc.updated_at FROM savings_challenges sc LEFT JOIN categories c ON c.id=sc.category_id WHERE sc.household_id=%s"""
    params=[household_id]
    if status:
        sql+=' AND sc.status=%s'; params.append(status)
    sql+=' ORDER BY sc.created_at DESC'
    return fetch_all(sql,tuple(params))

def update_savings_challenge_status(challenge_id,household_id,status):
    execute("UPDATE savings_challenges SET status=%s,updated_at=NOW() WHERE id=%s AND household_id=%s",(status,challenge_id,household_id))

def calculate_challenge_progress(challenge,household_id):
    target=float(challenge['target_amount'] or 0)
    if challenge.get('category_id'):
        row=fetch_one("""SELECT COALESCE(SUM(eo.amount),0) AS total FROM expense_occurrences eo JOIN expenses e ON e.id=eo.expense_id WHERE eo.household_id=%s AND e.category_id=%s AND eo.occurrence_date BETWEEN %s AND %s AND eo.is_active=1 AND e.is_active=1""",(household_id,challenge['category_id'],challenge['start_date'],challenge['end_date']))
        spent=float(row['total'] or 0)
        remaining=max(0.0,target-spent)
        progress=min(100.0,max(0.0,remaining/target*100)) if target>0 else 0
    else:
        spent=0.0; remaining=target; progress=0.0
    return {'spent':round(spent,2),'target':round(target,2),'remaining':round(remaining,2),'progress_pct':round(progress,1)}


# V2.9 — funções mantidas num módulo separado para preservar o db.py corrigido
from smart_finance import (
    detect_financial_habits, get_smart_notification_settings,
    list_financial_habit_snapshots, list_smart_financial_alerts,
    queue_smart_alert_emails, refresh_smart_financial_alerts,
    save_financial_habit_snapshot, save_smart_notification_settings,
    update_smart_financial_alert_status
)
