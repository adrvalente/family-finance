
import hashlib
import re
from datetime import date

from db import (
    fetch_one, fetch_all, execute,
    generate_next_month_actions,
    get_financial_action_priorities,
)


STATUS_LABELS = {
    "todo": "Por fazer",
    "in_progress": "Em curso",
    "completed": "Concluída",
    "ignored": "Ignorada",
}


def _source_key(source_type, title, extra=""):
    raw = f"{source_type}|{title}|{extra}".strip().lower()
    raw = re.sub(r"\s+", " ", raw)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _normalize_action(item, year=None, month=None):
    title = (item.get("title") or "Ação financeira").strip()
    source_type = item.get("source") or item.get("type") or "assistant"
    impact_year = float(
        item.get("impact_year")
        or item.get("estimated_annual_saving")
        or item.get("annual_saving")
        or 0
    )
    impact_month = impact_year / 12 if impact_year > 0 else 0.0
    priority = int(item.get("priority") or 50)
    reason = item.get("reason") or ""
    extra = item.get("service_id") or item.get("expense_id") or f"{year}-{month}"
    return {
        "source_type": source_type,
        "source_key": _source_key(source_type, title, extra),
        "title": title,
        "reason": reason,
        "priority": max(0, min(100, priority)),
        "estimated_annual_impact": round(impact_year, 2),
        "estimated_monthly_impact": round(impact_month, 2),
        "origin_year": year,
        "origin_month": month,
    }


def sync_recommended_actions(household_id, year, month):
    """Materializa recomendações atuais em ações acompanháveis."""
    raw = []

    try:
        raw.extend(generate_next_month_actions(household_id, year, month, 5))
    except Exception:
        pass

    try:
        raw.extend(get_financial_action_priorities(household_id)[:10])
    except Exception:
        pass

    dedup = {}
    for item in raw:
        normalized = _normalize_action(item, year, month)
        dedup[normalized["source_key"]] = normalized

    created = 0
    updated = 0

    for action in dedup.values():
        existing = fetch_one("""
            SELECT id,status
            FROM financial_action_items
            WHERE household_id=%s AND source_key=%s
            LIMIT 1
        """, (household_id, action["source_key"]))

        if existing:
            if existing["status"] in ("todo", "in_progress"):
                execute("""
                    UPDATE financial_action_items
                    SET title=%s,
                        reason=%s,
                        priority=%s,
                        estimated_annual_impact=%s,
                        estimated_monthly_impact=%s,
                        origin_year=%s,
                        origin_month=%s,
                        updated_at=NOW()
                    WHERE id=%s AND household_id=%s
                """, (
                    action["title"], action["reason"], action["priority"],
                    action["estimated_annual_impact"],
                    action["estimated_monthly_impact"],
                    action["origin_year"], action["origin_month"],
                    existing["id"], household_id
                ))
                updated += 1
            continue

        execute("""
            INSERT INTO financial_action_items(
                household_id,source_type,source_key,title,reason,
                priority,estimated_annual_impact,estimated_monthly_impact,
                origin_year,origin_month,status
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'todo')
        """, (
            household_id, action["source_type"], action["source_key"],
            action["title"], action["reason"], action["priority"],
            action["estimated_annual_impact"],
            action["estimated_monthly_impact"],
            action["origin_year"], action["origin_month"]
        ))
        created += 1

    return {"created": created, "updated": updated, "total": len(dedup)}


def create_manual_action(
    household_id, title, reason=None, priority=50,
    estimated_annual_impact=0, notes=None
):
    source_key = _source_key("manual", title, date.today().isoformat())
    return execute("""
        INSERT INTO financial_action_items(
            household_id,source_type,source_key,title,reason,
            priority,estimated_annual_impact,estimated_monthly_impact,
            notes,status
        )
        VALUES(%s,'manual',%s,%s,%s,%s,%s,%s,%s,'todo')
    """, (
        household_id, source_key, title, reason,
        priority, estimated_annual_impact,
        float(estimated_annual_impact or 0)/12,
        notes
    ))


def list_financial_actions(household_id, status=None, limit_rows=200):
    sql = """
        SELECT
            a.id,a.household_id,a.source_type,a.source_key,
            a.title,a.reason,a.priority,
            a.estimated_annual_impact,a.estimated_monthly_impact,
            a.origin_year,a.origin_month,a.status,
            a.started_at,a.completed_at,a.ignored_at,
            a.notes,a.created_at,a.updated_at,
            COALESCE(SUM(m.amount),0) AS realized_saving,
            COUNT(m.id) AS measurement_count
        FROM financial_action_items a
        LEFT JOIN financial_action_savings m
          ON m.action_id=a.id AND m.household_id=a.household_id
        WHERE a.household_id=%s
    """
    params = [household_id]

    if status:
        sql += " AND a.status=%s"
        params.append(status)

    sql += """
        GROUP BY
            a.id,a.household_id,a.source_type,a.source_key,
            a.title,a.reason,a.priority,
            a.estimated_annual_impact,a.estimated_monthly_impact,
            a.origin_year,a.origin_month,a.status,
            a.started_at,a.completed_at,a.ignored_at,
            a.notes,a.created_at,a.updated_at
        ORDER BY
            FIELD(a.status,'in_progress','todo','completed','ignored'),
            a.priority DESC,a.updated_at DESC
        LIMIT %s
    """
    params.append(limit_rows)
    return fetch_all(sql, tuple(params))


def get_financial_action(action_id, household_id):
    rows = list_financial_actions(household_id, None, 500)
    for row in rows:
        if int(row["id"]) == int(action_id):
            return row
    return None


def update_financial_action_status(action_id, household_id, status):
    if status not in STATUS_LABELS:
        raise ValueError("Estado inválido.")

    if status == "in_progress":
        execute("""
            UPDATE financial_action_items
            SET status=%s,
                started_at=COALESCE(started_at,NOW()),
                updated_at=NOW()
            WHERE id=%s AND household_id=%s
        """, (status, action_id, household_id))
    elif status == "completed":
        execute("""
            UPDATE financial_action_items
            SET status=%s,
                started_at=COALESCE(started_at,NOW()),
                completed_at=NOW(),
                updated_at=NOW()
            WHERE id=%s AND household_id=%s
        """, (status, action_id, household_id))
    elif status == "ignored":
        execute("""
            UPDATE financial_action_items
            SET status=%s,
                ignored_at=NOW(),
                updated_at=NOW()
            WHERE id=%s AND household_id=%s
        """, (status, action_id, household_id))
    else:
        execute("""
            UPDATE financial_action_items
            SET status=%s,
                completed_at=NULL,
                ignored_at=NULL,
                updated_at=NOW()
            WHERE id=%s AND household_id=%s
        """, (status, action_id, household_id))


def update_financial_action_notes(action_id, household_id, notes):
    execute("""
        UPDATE financial_action_items
        SET notes=%s,updated_at=NOW()
        WHERE id=%s AND household_id=%s
    """, (notes, action_id, household_id))


def add_action_saving_measurement(
    action_id, household_id, amount,
    measured_date=None, notes=None
):
    measured_date = measured_date or date.today()
    return execute("""
        INSERT INTO financial_action_savings(
            action_id,household_id,measured_date,amount,notes
        )
        VALUES(%s,%s,%s,%s,%s)
    """, (
        action_id, household_id, measured_date,
        amount, notes
    ))


def list_action_saving_measurements(household_id, action_id=None, limit_rows=200):
    sql = """
        SELECT
            m.id,m.action_id,m.measured_date,m.amount,m.notes,m.created_at,
            a.title,a.status
        FROM financial_action_savings m
        JOIN financial_action_items a
          ON a.id=m.action_id
        WHERE m.household_id=%s
    """
    params = [household_id]

    if action_id:
        sql += " AND m.action_id=%s"
        params.append(action_id)

    sql += " ORDER BY m.measured_date DESC,m.id DESC LIMIT %s"
    params.append(limit_rows)
    return fetch_all(sql, tuple(params))


def get_action_plan_summary(household_id):
    actions = list_financial_actions(household_id, None, 500)

    counts = {k: 0 for k in STATUS_LABELS}
    estimated = 0.0
    realized = 0.0

    for action in actions:
        counts[action["status"]] = counts.get(action["status"], 0) + 1
        if action["status"] in ("todo", "in_progress"):
            estimated += float(action["estimated_annual_impact"] or 0)
        realized += float(action["realized_saving"] or 0)

    active = counts.get("todo", 0) + counts.get("in_progress", 0)

    return {
        "total_actions": len(actions),
        "active_actions": active,
        "todo": counts.get("todo", 0),
        "in_progress": counts.get("in_progress", 0),
        "completed": counts.get("completed", 0),
        "ignored": counts.get("ignored", 0),
        "estimated_annual_opportunity": round(estimated, 2),
        "realized_saving": round(realized, 2),
    }


def get_action_completion_rate(household_id):
    summary = get_action_plan_summary(household_id)
    denominator = summary["completed"] + summary["ignored"] + summary["active_actions"]
    if denominator <= 0:
        return 0.0
    return round(summary["completed"] / denominator * 100, 1)
