import json
from datetime import date

from db import (
    fetch_one, fetch_all, execute,
    get_month_summary, get_financial_risk_score,
    get_budget_deviation_forecast, get_market_savings_summary,
    list_switch_decisions, list_saving_goals, get_goal_projection,
    calculate_monthly_plan, get_financial_action_priorities,
)
from smart_finance import detect_financial_habits, list_smart_financial_alerts


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def calculate_family_financial_score(household_id, year, month):
    """Score 0-100, decomposed into 5 explainable components."""
    summary = get_month_summary(household_id, year, month)
    risk = get_financial_risk_score(household_id, year, month)
    budgets = get_budget_deviation_forecast(household_id, year, month)
    market = get_market_savings_summary(household_id)
    habits = detect_financial_habits(household_id, year, month)
    switches = [x for x in list_switch_decisions(household_id) if x]

    income = float(summary.get("income") or 0)
    expense = float(summary.get("expense") or 0)
    balance = float(summary.get("balance") or 0)
    savings_rate = float(summary.get("savings_rate") or 0)

    # 1) Liquidity/savings: 25 points.
    savings_component = _clamp(savings_rate / 20 * 100) if income > 0 else 0
    if balance < 0:
        savings_component = 0

    # 2) Budget discipline: 20 points.
    if budgets:
        over = sum(1 for b in budgets if b.get("projected_over_budget"))
        warning = sum(
            1 for b in budgets
            if not b.get("projected_over_budget")
            and float(b.get("percent") or 0) >= float(b.get("warning_percent") or 80)
        )
        budget_component = _clamp(100 - over * 25 - warning * 10)
    else:
        # Neutral score when there are no budgets configured.
        budget_component = 60.0

    # 3) Risk management: 25 points (inverse of risk score).
    risk_component = _clamp(100 - float(risk.get("score") or 0))

    # 4) Financial habits: 15 points.
    if habits:
        avg_habit_score = sum(float(h.get("score") or 0) for h in habits) / len(habits)
        habit_component = _clamp(100 - avg_habit_score * 0.70)
    else:
        habit_component = 100.0

    # 5) Market/contract optimization: 15 points.
    positive_switches = [
        s for s in switches
        if s.get("best_offer") and float(s.get("annual_saving") or 0) > 0
    ]
    annual_market_saving = max(0.0, float(market.get("potential_annual_saving") or 0))
    if positive_switches:
        urgent = sum(1 for s in positive_switches if s.get("recommendation") == "switch_now")
        market_component = _clamp(100 - min(70, annual_market_saving / 10) - urgent * 10)
    else:
        market_component = 100.0

    components = {
        "savings": {"label": "Liquidez e poupança", "score": round(savings_component, 1), "weight": 25},
        "budget": {"label": "Controlo orçamental", "score": round(budget_component, 1), "weight": 20},
        "risk": {"label": "Gestão de risco", "score": round(risk_component, 1), "weight": 25},
        "habits": {"label": "Hábitos financeiros", "score": round(habit_component, 1), "weight": 15},
        "market": {"label": "Contratos e mercado", "score": round(market_component, 1), "weight": 15},
    }

    score = sum(v["score"] * v["weight"] / 100 for v in components.values())
    score = round(_clamp(score), 1)

    if score >= 85:
        level, label = "excellent", "Excelente"
    elif score >= 70:
        level, label = "good", "Bom"
    elif score >= 50:
        level, label = "attention", "Atenção"
    elif score >= 30:
        level, label = "high_risk", "Risco elevado"
    else:
        level, label = "critical", "Crítico"

    strengths = sorted(components.values(), key=lambda x: x["score"], reverse=True)[:2]
    weaknesses = sorted(components.values(), key=lambda x: x["score"])[:2]

    return {
        "score": score,
        "level": level,
        "label": label,
        "components": components,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "summary": summary,
        "risk": risk,
        "market": market,
        "habits": habits,
        "switches": positive_switches,
    }


def get_executive_dashboard(household_id, year, month):
    score = calculate_family_financial_score(household_id, year, month)
    plan = calculate_monthly_plan(household_id, year, month)
    alerts = list_smart_financial_alerts(household_id, "new", 20)
    actions = get_financial_action_priorities(household_id)[:5]
    goals = list_saving_goals(household_id)

    goal_rows = []
    for goal in goals:
        if not goal.get("is_active"):
            continue
        projection = get_goal_projection(household_id, goal)
        target = float(goal.get("target_amount") or 0)
        current = float(goal.get("current_amount") or 0)
        pct = current / target * 100 if target > 0 else 0
        goal_rows.append({
            **goal,
            "progress_pct": round(_clamp(pct), 1),
            "projection": projection,
        })

    return {
        **score,
        "plan": plan,
        "alerts": alerts,
        "actions": actions,
        "goals": goal_rows,
    }


def save_executive_score_snapshot(household_id, year, month):
    data = calculate_family_financial_score(household_id, year, month)
    components_json = json.dumps(data["components"], ensure_ascii=False, default=str)
    details_json = json.dumps({
        "summary": data["summary"],
        "risk": data["risk"],
        "market": data["market"],
        "habits": data["habits"],
    }, ensure_ascii=False, default=str)

    existing = fetch_one("""
        SELECT id FROM executive_score_snapshots
        WHERE household_id=%s AND year_num=%s AND month_num=%s
        LIMIT 1
    """, (household_id, year, month))

    if existing:
        execute("""
            UPDATE executive_score_snapshots
            SET score=%s,level=%s,components_json=%s,details_json=%s,updated_at=NOW()
            WHERE id=%s
        """, (data["score"], data["level"], components_json, details_json, existing["id"]))
        return existing["id"]

    return execute("""
        INSERT INTO executive_score_snapshots(
            household_id,year_num,month_num,score,level,components_json,details_json
        ) VALUES(%s,%s,%s,%s,%s,%s,%s)
    """, (household_id, year, month, data["score"], data["level"], components_json, details_json))


def list_executive_score_snapshots(household_id, limit_rows=24):
    return fetch_all("""
        SELECT id,year_num,month_num,score,level,components_json,created_at,updated_at
        FROM executive_score_snapshots
        WHERE household_id=%s
        ORDER BY year_num DESC,month_num DESC
        LIMIT %s
    """, (household_id, limit_rows))


def build_executive_summary(household_id, year, month):
    d = get_executive_dashboard(household_id, year, month)
    s = d["summary"]
    weakest = d["weaknesses"][0]["label"] if d["weaknesses"] else "—"
    strongest = d["strengths"][0]["label"] if d["strengths"] else "—"
    alert_count = len(d["alerts"])
    potential = float(d["market"].get("potential_annual_saving") or 0)

    return (
        f"O Family Financial Score é {d['score']:.1f}/100 ({d['label']}). "
        f"O período apresenta um saldo de {float(s.get('balance') or 0):.2f} € e uma taxa de poupança "
        f"de {float(s.get('savings_rate') or 0):.1f}%. O ponto mais forte é {strongest}; "
        f"a área que mais precisa de atenção é {weakest}. Existem {alert_count} alertas inteligentes "
        f"ativos e uma poupança potencial de mercado estimada em {potential:.2f} €/ano."
    )
