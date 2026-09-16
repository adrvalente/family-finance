
import os, platform, uuid, json, re
from datetime import date, datetime, timedelta

import pandas as pd
import altair as alt
import streamlit as st
from ui.theme import apply_family_finance_theme, render_brand_header, render_sidebar_brand, score_card, component_card, COLORS
from dotenv import load_dotenv

from document_extractor import extract_document_text, extract_fields, extract_line_items, file_sha256

from auth import (
    change_password, hash_password, init_session, is_admin,
    login, logout, require_admin, require_login
)
from action_tracker import (
    STATUS_LABELS,
    add_action_saving_measurement,
    create_manual_action,
    get_action_plan_summary,
    list_action_saving_measurements,
    list_financial_actions,
    sync_recommended_actions,
    update_financial_action_notes,
    update_financial_action_status,
)

from executive_finance import (
    build_executive_summary, get_executive_dashboard,
    list_executive_score_snapshots, save_executive_score_snapshot,
)

from db import (
    assign_user_to_household, create_document, create_expense, create_household, create_income, create_user,
    add_document_item, classify_document_with_history, create_expense_from_document, delete_budget, delete_document, delete_document_item, delete_expense, delete_income, detect_monthly_supplier_pattern, find_duplicate_document, get_auto_create_threshold, get_budget_alerts, get_categories, get_category_id_by_name, get_document_by_id, get_document_item_summary, get_document_stats, get_expense_categories,
    get_expense_history_monthly, get_expenses_by_category, get_fixed_variable_expenses,
    get_financial_history, get_income_categories,
    get_income_history_monthly, get_month_comparison, get_month_summary,
    get_monthly_expense_total, get_monthly_income_total, get_system_stats, get_database_environment, get_database_environment,
    get_top_expense_categories, get_top_suppliers, get_user_by_username,
    list_documents, list_expense_occurrences, list_expenses, list_expenses_for_document_link, list_households, list_income_occurrences,
    list_incomes, list_users, list_users_by_household, log_action,
    rebuild_expense_occurrences, rebuild_income_occurrences, set_document_active, set_expense_active,
    compare_service_offers, compare_service_offers_v24, create_household_service, create_household_service_v25, create_market_offer, create_market_provider, create_market_source, delete_household_service, delete_market_offer, delete_market_source, delete_scenario_preset, detect_expense_anomalies, get_annual_savings_projection, get_budget_deviation_forecast, get_calendar_events, get_cut_recommendations, get_financial_forecast, get_financial_risk_score, get_forecast_alerts, get_goal_projection, get_item_category_history, get_learning_rules_for_extractor, get_document_service_link, get_household_primary_email, get_market_freshness_summary, get_market_savings_summary, get_multi_month_forecast, get_recurring_expenses_for_scenarios, get_scenario_presets, get_upcoming_commitments, list_household_service_price_history, list_household_services, list_market_alerts, list_notification_settings, list_market_offer_history, list_market_offers, list_market_providers, list_market_sources, list_risk_snapshots, list_service_alerts, list_unlinked_service_documents, learn_document_correction, list_budgets, list_document_items, list_saving_goals, replace_document_items, save_auto_create_settings, create_saving_goal, delete_saving_goal, link_document_to_service, queue_household_alert_emails, refresh_contract_alerts, refresh_market_alerts, refresh_price_increase_alerts, save_document_extraction, save_document_extraction_v17, save_document_items_metadata, save_document_v18_intelligence, save_risk_snapshot, save_notification_settings, suggest_document_service_link, update_household_service, update_household_service_v25, update_market_alert_status, update_market_source, update_service_alert_status, update_market_offer, update_market_provider, save_scenario_preset, simulate_expense_reduction, set_income_active, set_user_active, suggest_budget_from_history, test_connection, update_document_hash, update_document_item, update_document_link, update_saving_goal, upsert_budget,
    update_document_notes, update_document_processing, mark_document_ocr_error,
    detect_financial_habits, get_smart_notification_settings, list_financial_habit_snapshots, list_smart_financial_alerts, queue_smart_alert_emails, refresh_smart_financial_alerts, save_financial_habit_snapshot, save_smart_notification_settings, update_smart_financial_alert_status,
    update_expense, update_income, build_monthly_financial_narrative, calculate_monthly_plan, calculate_challenge_progress, calculate_switch_decision, create_savings_challenge, get_monthly_financial_plan, get_recommended_category_limits, get_weekly_spending_status, list_savings_challenges, save_monthly_financial_plan, update_savings_challenge_status, generate_next_month_actions, get_monthly_financial_brief, list_monthly_financial_briefs, save_monthly_financial_brief, extract_contract_terms_from_document, get_contract_intelligence, get_financial_action_priorities, list_switch_decisions, save_contract_intelligence
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR,".env"))

APP_NAME = os.getenv("APP_NAME","Painel de Despesas Familiar")
APP_ENV = os.getenv("APP_ENV","development")

st.set_page_config(page_title="Family Finance",page_icon="💶",layout="wide")
apply_family_finance_theme()
init_session()

MONTHS_PT = {
    1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
    7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"
}

FREQ_LABELS = {
    "monthly":"Mensal",
    "quarterly":"Trimestral",
    "semiannual":"Semestral",
    "annual":"Anual",
    "none":"—"
}

def refresh_session_user():
    if st.session_state.get("user"):
        current = get_user_by_username(st.session_state.user["username"])
        if current:
            st.session_state.user.update({
                "full_name": current["full_name"],
                "email": current["email"],
                "role": current["role"],
                "must_change_password": bool(current["must_change_password"]),
                "household_id": current["household_id"],
                "household_name": current["household_name"],
            })

def page_login():
    # Segurança adicional:
    # nunca renderizar o formulário se a sessão já estiver autenticada.
    if st.session_state.get("authenticated", False):
        return

    render_brand_header(
        "Family Finance",
        "As finanças da família, num só lugar."
    )

    st.caption("V3.3.3 — Cloud Stabilization")

    c1, c2, c3 = st.columns([1, 1.2, 1])

    with c2:
        st.subheader("Iniciar sessão")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Utilizador",
                key="login_username"
            )

            password = st.text_input(
                "Palavra-passe",
                type="password",
                key="login_password"
            )

            submit = st.form_submit_button(
                "Entrar",
                use_container_width=True
            )

        if submit:
            ok, err = login(username, password)

            if ok:
                # Remove valores do formulário antes do rerun.
                st.session_state.pop("login_username", None)
                st.session_state.pop("login_password", None)

                st.rerun()

            else:
                st.error(err)

def sidebar():
    refresh_session_user()
    u = st.session_state.user
    with st.sidebar:
        render_sidebar_brand()
        st.write(f"**{u['full_name']}**")
        st.caption(f"@{u['username']}")
        st.write("**Perfil:** " + ("Administrador" if u["role"]=="admin" else "Utilizador"))
        if u.get("household_name"):
            st.write(f"**Agregado:** {u['household_name']}")
        st.divider()
        pages = ["Executivo","Ações","Dashboard","Rendimentos","Despesas","Documentos","Orçamentos","Planeamento","Calendário","Cenários","Risco","Mercado","Contratos","Assistente","Plano","Hábitos","Notificações","Metas","O meu perfil"]
        if is_admin():
            pages += ["Utilizadores","Agregados","Sistema"]
        page = st.radio("Navegação",pages)
        st.divider()
        if st.button("Terminar sessão",use_container_width=True):
            logout()
            st.rerun()
        st.caption("Family Finance V3.3.3")
    return page

def require_household():
    require_login()
    hid = st.session_state.user.get("household_id")
    if not hid:
        st.warning("O teu utilizador ainda não está associado a um agregado familiar.")
        if is_admin():
            st.info("Vai a **Agregados** e associa este utilizador a um agregado.")
        st.stop()
    return hid


def page_executive_dashboard():
    household_id = require_household()
    st.title("🏠 Dashboard Executivo Familiar")
    st.caption("V3.3.3 — Cloud Stabilization + Family Finance Design System")

    today = date.today()
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        years = list(range(today.year-5,today.year+2))
        year = st.selectbox("Ano",years,index=years.index(today.year),key="exec_year")
    with c2:
        month = st.selectbox(
            "Mês",list(MONTHS_PT),index=today.month-1,
            format_func=lambda x:MONTHS_PT[x],key="exec_month"
        )
    with c3:
        st.write("")
        st.write("")
        if st.button("Guardar score do mês",use_container_width=True):
            save_executive_score_snapshot(household_id,year,month)
            st.success("Family Financial Score guardado.")
            st.rerun()

    data = get_executive_dashboard(household_id,year,month)
    score = float(data["score"])

    st.subheader("Family Financial Score")
    st.markdown(
        '<div class="ff-section-subtitle">Uma visão rápida da saúde financeira da família.</div>',
        unsafe_allow_html=True
    )

    risk_score = float(data["risk"].get("score") or 0)
    savings_rate = float(data["summary"].get("savings_rate") or 0)

    a,b,c,d = st.columns(4)
    with a:
        score_card("Score global", f"{score:.1f}/100", "🎯", "Pontuação financeira global", "info")
    with b:
        tone = "success" if score >= 70 else "warning" if score >= 50 else "danger"
        score_card("Estado", str(data["label"]), "⚠️" if score < 70 else "✓", "Situação financeira atual", tone)
    with c:
        score_card("Risco", f"{risk_score:.0f}/100", "🛡️", "Score de risco financeiro", "success" if risk_score < 50 else "warning")
    with d:
        score_card("Poupança", f"{savings_rate:.1f}%", "🐷", "da receita mensal", "success")

    st.progress(min(1.0,max(0.0,score/100)))

    if score >= 85:
        st.success("Situação financeira global muito sólida.")
    elif score >= 70:
        st.success("Situação financeira saudável, com alguns pontos de otimização.")
    elif score >= 50:
        st.warning("Situação razoável, mas existem áreas que merecem atenção.")
    elif score >= 30:
        st.error("Risco financeiro elevado. Prioriza as ações recomendadas.")
    else:
        st.error("Situação crítica. O foco deve ser liquidez, despesas e compromissos fixos.")

    st.write(build_executive_summary(household_id,year,month))

    st.divider()
    st.subheader("Componentes do score")
    st.markdown(
        '<div class="ff-section-subtitle">Contribuição de cada área para o Family Financial Score.</div>',
        unsafe_allow_html=True
    )

    comps = data["components"]
    component_colors = ["#218CE0","#17A47B","#E7A11A","#168BD2","#1AAD7F"]

    cols = st.columns(5)
    for col, item, color in zip(cols, comps.values(), component_colors):
        with col:
            component_card(item["label"], float(item["score"]), int(item["weight"]), color)

    comp_df = pd.DataFrame([
        {"Área":v["label"],"Score":float(v["score"]),"Peso":int(v["weight"])}
        for v in comps.values()
    ])

    chart_order = comp_df["Área"].tolist()

    bars = (
        alt.Chart(comp_df)
        .mark_bar(cornerRadiusTopLeft=7, cornerRadiusTopRight=7, size=72)
        .encode(
            x=alt.X(
                "Área:N",
                sort=chart_order,
                title=None,
                axis=alt.Axis(
                    labelAngle=0,
                    labelColor="#526A82",
                    labelFontSize=11,
                    labelPadding=12,
                    labelLimit=170,
                    ticks=False,
                    domainColor="#DDE6EE"
                )
            ),
            y=alt.Y(
                "Score:Q",
                scale=alt.Scale(domain=[0,100]),
                title=None,
                axis=alt.Axis(
                    values=[0,20,40,60,80,100],
                    labelColor="#6B7C8F",
                    gridColor="#E8EEF4",
                    domain=False,
                    ticks=False
                )
            ),
            color=alt.Color(
                "Área:N",
                scale=alt.Scale(domain=chart_order, range=component_colors),
                legend=None
            ),
            tooltip=[
                alt.Tooltip("Área:N", title="Área"),
                alt.Tooltip("Score:Q", title="Score", format=".0f"),
                alt.Tooltip("Peso:Q", title="Peso", format=".0f")
            ]
        )
    )

    labels = (
        alt.Chart(comp_df)
        .mark_text(dy=-10, fontSize=13, fontWeight="bold", color="#17324D")
        .encode(
            x=alt.X("Área:N", sort=chart_order),
            y=alt.Y("Score:Q"),
            text=alt.Text("Score:Q", format=".0f")
        )
    )

    chart = (
        (bars + labels)
        .properties(height=320)
        .configure_view(strokeWidth=0)
        .configure(background="#FFFFFF")
    )

    st.markdown("#### 📊 Componentes do score")
    st.caption("Pontuação de cada área (0–100).")
    st.altair_chart(chart, use_container_width=True)

    st.divider()
    s = data["summary"]
    market = data["market"]
    plan = data["plan"]
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Saldo do mês",f"{float(s.get('balance') or 0):.2f} €")
    m2.metric("Meta de poupança",f"{float(plan.get('target_saving') or 0):.2f} €")
    m3.metric("Teto de despesa",f"{float(plan.get('spend_cap') or 0):.2f} €")
    m4.metric("Poupança mercado/ano",f"{float(market.get('potential_annual_saving') or 0):.2f} €")

    left,right = st.columns(2)
    with left:
        st.subheader("Pontos fortes")
        for item in data["strengths"]:
            st.success(f"{item['label']} — {float(item['score']):.0f}/100")
    with right:
        st.subheader("Áreas a melhorar")
        for item in data["weaknesses"]:
            st.warning(f"{item['label']} — {float(item['score']):.0f}/100")

    st.divider()
    action_summary = get_action_plan_summary(household_id)
    st.subheader("Execução do Plano de Ação")
    ac1,ac2,ac3,ac4 = st.columns(4)
    ac1.metric("Ações ativas", action_summary["active_actions"])
    ac2.metric("Em curso", action_summary["in_progress"])
    ac3.metric("Concluídas", action_summary["completed"])
    ac4.metric("Poupança real", f"{action_summary['realized_saving']:.2f} €")
    st.caption(
        f"Oportunidade anual ainda por executar: "
        f"{action_summary['estimated_annual_opportunity']:.2f} €"
    )

    st.divider()
    left,right = st.columns(2)
    with left:
        st.subheader("Top ações prioritárias")
        actions = data["actions"]
        if not actions:
            st.info("Sem ações estratégicas prioritárias neste momento.")
        for idx,action in enumerate(actions,1):
            with st.container(border=True):
                st.write(f"**{idx}. {action.get('title','Ação financeira')}**")
                st.caption(action.get("reason") or "")
                impact=float(action.get("impact_year") or 0)
                if impact>0:
                    st.write(f"Impacto anual estimado: **{impact:.2f} €**")

    with right:
        st.subheader("Alertas ativos")
        alerts = data["alerts"]
        if not alerts:
            st.success("Sem alertas inteligentes ativos.")
        for alert in alerts[:5]:
            severity=alert.get("severity")
            text=f"**{alert['title']}** — {alert['message']}"
            if severity in ("critical","high"):
                st.error(text)
            elif severity=="warning":
                st.warning(text)
            else:
                st.info(text)

    st.divider()
    left,right = st.columns(2)
    with left:
        st.subheader("Metas de poupança")
        if not data["goals"]:
            st.info("Não existem metas ativas.")
        for goal in data["goals"][:5]:
            st.write(f"**{goal['name']}**")
            st.progress(min(1.0,max(0.0,float(goal['progress_pct'])/100)))
            st.caption(
                f"{float(goal['current_amount']):.2f} € / {float(goal['target_amount']):.2f} € "
                f"({float(goal['progress_pct']):.1f}%)"
            )

    with right:
        st.subheader("Oportunidades de contratos")
        switches=data["switches"]
        if not switches:
            st.success("Sem oportunidades de mudança com poupança positiva registadas.")
        for item in switches[:5]:
            srv=item["service"]
            st.write(f"**{srv['service_type']} — {srv['provider_name']}**")
            st.caption(item["reason"])
            st.write(f"Poupança estimada: **{float(item.get('annual_saving') or 0):.2f} €/ano**")

    st.divider()
    st.subheader("Evolução do Family Financial Score")
    history=list_executive_score_snapshots(household_id,24)
    if history:
        df=pd.DataFrame(history)
        df["Período"]=df.apply(
            lambda r:f"{MONTHS_PT[int(r['month_num'])]} {int(r['year_num'])}",axis=1
        )
        df=df.iloc[::-1]
        st.line_chart(df.set_index("Período")[["score"]].rename(columns={"score":"Score"}))
        st.dataframe(
            df.iloc[::-1][["year_num","month_num","score","level"]].rename(columns={
                "year_num":"Ano","month_num":"Mês","score":"Score","level":"Nível"
            }),use_container_width=True,hide_index=True
        )
    else:
        st.info("Guarda o score de cada mês para construir o histórico executivo.")


def page_financial_actions():
    household_id = require_household()
    st.title("✅ Plano de Ação Financeiro")
    st.caption(
        "V3.3 — plano de ação integrado no Family Finance Design System"
    )

    today = date.today()
    f1,f2,f3 = st.columns([1,1,1.4])
    with f1:
        year = st.selectbox(
            "Ano",
            list(range(today.year-3,today.year+2)),
            index=3,
            key="actions_year"
        )
    with f2:
        month = st.selectbox(
            "Mês",
            list(range(1,13)),
            index=today.month-1,
            format_func=lambda x:MONTHS_PT[x],
            key="actions_month"
        )
    with f3:
        st.write("")
        st.write("")
        if st.button("Atualizar recomendações",use_container_width=True):
            result = sync_recommended_actions(household_id,year,month)
            st.success(
                f"Plano atualizado: {result['created']} nova(s), "
                f"{result['updated']} atualizada(s)."
            )
            st.rerun()

    summary = get_action_plan_summary(household_id)

    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Por fazer",summary["todo"])
    m2.metric("Em curso",summary["in_progress"])
    m3.metric("Concluídas",summary["completed"])
    m4.metric("Poupança real",f"{summary['realized_saving']:.2f} €")
    m5.metric(
        "Oportunidade/ano",
        f"{summary['estimated_annual_opportunity']:.2f} €"
    )

    tabs = st.tabs([
        "Plano de Ação",
        "Registar poupança",
        "Nova ação",
        "Histórico"
    ])

    with tabs[0]:
        status_filter = st.selectbox(
            "Estado",
            ["active","todo","in_progress","completed","ignored","all"],
            format_func=lambda x:{
                "active":"Ativas",
                "todo":"Por fazer",
                "in_progress":"Em curso",
                "completed":"Concluídas",
                "ignored":"Ignoradas",
                "all":"Todas"
            }[x],
            key="action_status_filter"
        )

        rows = list_financial_actions(
            household_id,
            None if status_filter in ("all","active") else status_filter,
            200
        )

        if status_filter == "active":
            rows = [
                r for r in rows
                if r["status"] in ("todo","in_progress")
            ]

        if not rows:
            st.info(
                "Ainda não existem ações neste filtro. "
                "Usa **Atualizar recomendações** para criar o plano."
            )

        for action in rows:
            with st.container(border=True):
                c1,c2,c3 = st.columns([5,1.3,1.5])
                with c1:
                    st.write(f"**{action['title']}**")
                    if action.get("reason"):
                        st.caption(action["reason"])
                    st.caption(
                        f"Origem: {action['source_type']} · "
                        f"Prioridade: {action['priority']}/100"
                    )
                with c2:
                    st.metric(
                        "Estimativa anual",
                        f"{float(action['estimated_annual_impact'] or 0):.2f} €"
                    )
                with c3:
                    st.metric(
                        "Poupança real",
                        f"{float(action['realized_saving'] or 0):.2f} €"
                    )

                sc1,sc2 = st.columns([2,4])
                with sc1:
                    new_status = st.selectbox(
                        "Estado",
                        list(STATUS_LABELS.keys()),
                        index=list(STATUS_LABELS.keys()).index(action["status"]),
                        format_func=lambda x:STATUS_LABELS[x],
                        key=f"action_status_{action['id']}"
                    )
                    if st.button(
                        "Guardar estado",
                        key=f"save_action_status_{action['id']}",
                        use_container_width=True
                    ):
                        update_financial_action_status(
                            action["id"],household_id,new_status
                        )
                        st.success("Estado atualizado.")
                        st.rerun()

                with sc2:
                    notes = st.text_area(
                        "Notas",
                        value=action.get("notes") or "",
                        key=f"action_notes_{action['id']}",
                        height=90
                    )
                    if st.button(
                        "Guardar notas",
                        key=f"save_action_notes_{action['id']}"
                    ):
                        update_financial_action_notes(
                            action["id"],household_id,notes
                        )
                        st.success("Notas guardadas.")
                        st.rerun()

    with tabs[1]:
        actions = list_financial_actions(household_id,None,500)
        eligible = [
            a for a in actions
            if a["status"] in ("in_progress","completed")
        ]

        if not eligible:
            st.info(
                "Coloca pelo menos uma ação em **Em curso** ou **Concluída** "
                "para registar a poupança obtida."
            )
        else:
            options = {
                f"#{a['id']} · {a['title']}":a
                for a in eligible
            }
            with st.form("saving_measurement_form"):
                label = st.selectbox("Ação",list(options.keys()))
                amount = st.number_input(
                    "Poupança efetivamente obtida (€)",
                    min_value=0.01,
                    value=10.0,
                    step=5.0
                )
                measured_date = st.date_input(
                    "Data",
                    value=date.today()
                )
                notes = st.text_area(
                    "Como foi calculada / observações"
                )
                submitted = st.form_submit_button(
                    "Registar poupança"
                )

            if submitted:
                action = options[label]
                add_action_saving_measurement(
                    action["id"],household_id,amount,
                    measured_date,notes.strip() or None
                )
                st.success("Poupança real registada.")
                st.rerun()

    with tabs[2]:
        with st.form("manual_financial_action"):
            title = st.text_input("Título")
            reason = st.text_area("Motivo / objetivo")
            priority = st.slider(
                "Prioridade",0,100,50
            )
            estimate = st.number_input(
                "Impacto anual estimado (€)",
                min_value=0.0,
                value=0.0,
                step=10.0
            )
            notes = st.text_area("Notas internas")
            submitted = st.form_submit_button("Criar ação")

        if submitted:
            if not title.strip():
                st.error("Indica um título.")
            else:
                create_manual_action(
                    household_id,title.strip(),
                    reason.strip() or None,
                    priority,estimate,
                    notes.strip() or None
                )
                st.success("Ação criada.")
                st.rerun()

    with tabs[3]:
        measurements = list_action_saving_measurements(
            household_id,None,200
        )
        if measurements:
            df = pd.DataFrame(measurements)
            st.dataframe(
                df[[
                    "measured_date","title","amount","notes"
                ]].rename(columns={
                    "measured_date":"Data",
                    "title":"Ação",
                    "amount":"Poupança (€)",
                    "notes":"Notas"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Ainda não existem medições de poupança.")

        completed = list_financial_actions(
            household_id,"completed",200
        )
        if completed:
            st.subheader("Ações concluídas")
            st.dataframe(
                pd.DataFrame([{
                    "Ação":a["title"],
                    "Estimado/ano (€)":float(a["estimated_annual_impact"] or 0),
                    "Real (€)":float(a["realized_saving"] or 0),
                    "Concluída em":a["completed_at"]
                } for a in completed]),
                use_container_width=True,
                hide_index=True
            )

def page_dashboard():
    require_login()
    u=st.session_state.user
    st.title("📊 Dashboard Financeiro")
    st.caption("V1.4 — Análise financeira avançada")

    hid=u.get("household_id")
    if not hid:
        st.warning("O utilizador ainda não está associado a um agregado familiar.")
        st.stop()

    today=date.today()
    f1,f2=st.columns(2)
    with f1:
        years=list(range(today.year-5,today.year+2))
        year=st.selectbox("Ano",years,index=years.index(today.year),key="dash_year")
    with f2:
        month=st.selectbox("Mês",list(MONTHS_PT),index=today.month-1,format_func=lambda x:MONTHS_PT[x],key="dash_month")

    s=get_month_summary(hid,year,month)
    c=get_month_comparison(hid,year,month)

    def euro(v): return f"{v:,.2f} €".replace(",","X").replace(".",",").replace("X",".")
    def delta(v): return None if v is None else f"{v:+.1f}%".replace(".",",")

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Rendimentos",euro(s["income"]),delta(c["income_change_pct"]))
    m2.metric("Despesas",euro(s["expense"]),delta(c["expense_change_pct"]),delta_color="inverse")
    m3.metric("Saldo",euro(s["balance"]),delta(c["balance_change_pct"]))
    m4.metric("Taxa de poupança",f"{s['savings_rate']:.1f}%".replace(".",","))

    st.caption(f"Comparação com {MONTHS_PT[c['previous_month']]} {c['previous_year']}.")

    st.divider()
    left,right=st.columns(2)
    hist=get_financial_history(hid,12)

    with left:
        st.subheader("Rendimentos vs. Despesas")
        if hist:
            df=pd.DataFrame(hist)
            df["Mês"]=df.apply(lambda r:f"{MONTHS_PT[int(r['month_num'])]} {int(r['year_num'])}",axis=1)
            st.line_chart(df.set_index("Mês")[["income","expense"]].rename(columns={"income":"Rendimentos","expense":"Despesas"}))
        else:
            st.info("Ainda não existem dados suficientes.")

    with right:
        st.subheader("Saldo mensal")
        if hist:
            df=pd.DataFrame(hist)
            df["Mês"]=df.apply(lambda r:f"{MONTHS_PT[int(r['month_num'])]} {int(r['year_num'])}",axis=1)
            st.bar_chart(df.set_index("Mês")[["balance"]].rename(columns={"balance":"Saldo"}))
        else:
            st.info("Ainda não existem dados suficientes.")

    st.divider()
    left,right=st.columns(2)

    with left:
        st.subheader("Top categorias")
        rows=get_top_expense_categories(hid,year,month,5)
        if rows:
            df=pd.DataFrame([{"Categoria":r["category_name"],"Total":float(r["total"])} for r in rows])
            st.bar_chart(df.set_index("Categoria")["Total"])
            st.dataframe(df,use_container_width=True,hide_index=True)
        else:
            st.info("Sem despesas neste período.")

    with right:
        st.subheader("Top fornecedores")
        rows=get_top_suppliers(hid,year,month,5)
        if rows:
            df=pd.DataFrame([{"Fornecedor":r["supplier"],"Total":float(r["total"]),"Movimentos":int(r["occurrences"])} for r in rows])
            st.bar_chart(df.set_index("Fornecedor")["Total"])
            st.dataframe(df,use_container_width=True,hide_index=True)
        else:
            st.info("Sem fornecedores neste período.")

    st.divider()
    left,right=st.columns(2)

    with left:
        st.subheader("Despesas fixas vs. variáveis")
        rows=get_fixed_variable_expenses(hid,year,month)
        if rows:
            df=pd.DataFrame([{"Tipo":r["expense_kind"],"Total":float(r["total"])} for r in rows])
            st.bar_chart(df.set_index("Tipo")["Total"])
            total=df["Total"].sum()
            for _,row in df.iterrows():
                pct=(row["Total"]/total*100) if total else 0
                st.write(f"**{row['Tipo']}** — {euro(row['Total'])} ({pct:.1f}%)".replace(".",","))
        else:
            st.info("Sem despesas neste período.")

    with right:
        st.subheader("Peso das despesas no rendimento")
        if s["income"]>0:
            weight=s["expense_weight"]
            st.metric("Despesas / Rendimentos",f"{weight:.1f}%".replace(".",","))
            st.progress(min(max(weight/100,0),1))
            if weight<70:
                st.success("As despesas estão abaixo de 70% dos rendimentos.")
            elif weight<90:
                st.warning("As despesas já consomem uma parte elevada dos rendimentos.")
            else:
                st.error("As despesas consomem praticamente todo o rendimento disponível.")
        else:
            st.info("Sem rendimentos registados para este período.")

    st.divider()
    st.subheader("Indicadores de tendência")

    if c["income_change_pct"] is None and c["expense_change_pct"] is None:
        st.info("Ainda não existem dados suficientes no mês anterior para calcular tendências.")
    else:
        if c["income_change_pct"] is not None:
            v=c["income_change_pct"]
            (st.success if v>=0 else st.warning)(f"**Rendimentos:** {delta(v)} face ao mês anterior.")
        if c["expense_change_pct"] is not None:
            v=c["expense_change_pct"]
            (st.success if v<=0 else st.warning)(f"**Despesas:** {delta(v)} face ao mês anterior.")
        if c["balance_change_pct"] is not None:
            v=c["balance_change_pct"]
            (st.success if v>=0 else st.warning)(f"**Saldo:** {delta(v)} face ao mês anterior.")

    st.divider()
    st.markdown("""
    ### Estado do desenvolvimento
    - ✅ V1.0 — Infraestrutura
    - ✅ V1.1 — Login, perfis e controlo de acesso
    - ✅ V1.2 — Rendimentos
    - ✅ V1.3 — Despesas
    - ✅ V1.4 — Dashboard Financeiro Avançado
    - ✅ V1.5 — Upload de faturas e recibos
    - ✅ V1.6 — OCR e extração automática
    - ✅ V1.7 — Duplicados, NIF, confiança por campo e aprendizagem
    - ✅ V1.8 — Classificação por histórico, padrões mensais e automação
    - ✅ V1.9 — Produtos, orçamentos inteligentes e alertas
    - ✅ V2.0 — Previsão financeira, compromissos e metas
    - ✅ V2.1 — Calendário visual, previsões 3/6/12 meses e cenários
    - ✅ V2.2 — Scoring de risco, anomalias e recomendações
    - ✅ V2.3 — Market Intelligence e comparação de fornecedores
    - ✅ V2.4 — Recolha automática, histórico, validade e alertas
    - ✅ V2.5 — Email, fidelização, preço e ligação documental
    - ✅ V2.6 — Inteligência de contratos e decisão de mudança
    - ✅ V2.7 — Assistente financeiro familiar e resumo mensal
    - ✅ V2.8 — Plano financeiro, limites, semanas e desafios
    - ✅ V2.9 — Hábitos e alertas inteligentes
    - ✅ V3.0 — Dashboard Executivo e Family Financial Score
    - ✅ V3.1 — Plano de Ação, execução e medição da poupança real
    - ✅ V3.2 — Resultados automáticos, ROI e recomendações adaptativas\n    - ✅ V3.3 — Identidade visual, logótipo e Family Finance Design System
    """)

def page_incomes():
    household_id = require_household()
    u = st.session_state.user

    st.title("💰 Rendimentos")
    st.caption(f"Agregado: {u['household_name']}")

    tab1,tab2,tab3 = st.tabs(["Novo rendimento","Rendimentos registados","Histórico mensal"])

    categories = get_income_categories()
    members = list_users_by_household(household_id)

    cat_opts = {c["name"]:c["id"] for c in categories}
    member_opts = {m["full_name"]:m["id"] for m in members}

    with tab1:
        st.subheader("Adicionar rendimento")

        if not categories:
            st.error("Não existem categorias de rendimento configuradas.")
        elif not members:
            st.error("Não existem membros ativos neste agregado.")
        else:
            with st.form("new_income"):
                c1,c2 = st.columns(2)
                with c1:
                    description = st.text_input("Descrição *", placeholder="Ex.: Salário Adriano")
                    category_label = st.selectbox("Tipo de rendimento *", list(cat_opts))
                    owner_label = st.selectbox("Titular *", list(member_opts))
                    amount = st.number_input("Valor (€) *", min_value=0.0, step=10.0, format="%.2f")
                with c2:
                    recurrence_label = st.radio("Natureza",["Recorrente","Pontual"],horizontal=True)
                    if recurrence_label == "Pontual":
                        income_date = st.date_input("Data do rendimento", value=date.today())
                        frequency = "none"
                        start_date = None
                        end_date = None
                    else:
                        income_date = None
                        freq_label = st.selectbox("Periodicidade",["Mensal","Trimestral","Semestral","Anual"])
                        freq_map = {
                            "Mensal":"monthly","Trimestral":"quarterly",
                            "Semestral":"semiannual","Anual":"annual"
                        }
                        frequency = freq_map[freq_label]
                        start_date = st.date_input("Início", value=date.today())
                        has_end = st.checkbox("Definir data de fim")
                        end_date = st.date_input("Fim", value=date.today()) if has_end else None

                notes = st.text_area("Notas")
                submit = st.form_submit_button("Guardar rendimento",use_container_width=True)

            if submit:
                if not description.strip():
                    st.error("A descrição é obrigatória.")
                elif amount <= 0:
                    st.error("O valor tem de ser superior a 0 €.")
                elif recurrence_label == "Recorrente" and end_date and end_date < start_date:
                    st.error("A data de fim não pode ser anterior à data de início.")
                else:
                    try:
                        income_id = create_income(
                            household_id=household_id,
                            category_id=cat_opts[category_label],
                            owner_user_id=member_opts[owner_label],
                            description=description.strip(),
                            amount=amount,
                            income_date=income_date,
                            recurrence_type="recurring" if recurrence_label=="Recorrente" else "one_time",
                            frequency=frequency,
                            start_date=start_date,
                            end_date=end_date,
                            notes=notes.strip() or None,
                            created_by=u["id"]
                        )
                        rebuild_income_occurrences(income_id,household_id)
                        log_action(u["id"],"create_income","income",income_id,description.strip())
                        st.success("Rendimento registado com sucesso.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao guardar rendimento: {e}")

    with tab2:
        incomes = list_incomes(household_id)
        if not incomes:
            st.info("Ainda não existem rendimentos registados.")
        else:
            table = []
            for item in incomes:
                table.append({
                    "ID": item["id"],
                    "Descrição": item["description"],
                    "Categoria": item["category_name"],
                    "Titular": item["owner_name"] or "—",
                    "Valor (€)": float(item["amount"]),
                    "Natureza": "Recorrente" if item["recurrence_type"]=="recurring" else "Pontual",
                    "Periodicidade": FREQ_LABELS.get(item["frequency"],item["frequency"]),
                    "Data": item["income_date"],
                    "Início": item["start_date"],
                    "Fim": item["end_date"],
                    "Ativo": "Sim" if item["is_active"] else "Não",
                })
            st.dataframe(pd.DataFrame(table),use_container_width=True,hide_index=True)

            st.subheader("Gerir rendimento")
            options = {
                f"#{i['id']} — {i['description']} — {float(i['amount']):.2f} €":i
                for i in incomes
            }
            label = st.selectbox("Selecionar rendimento",list(options))
            selected = options[label]

            c1,c2 = st.columns(2)
            with c1:
                active = st.checkbox("Rendimento ativo",value=bool(selected["is_active"]))
                if st.button("Guardar estado"):
                    set_income_active(selected["id"],household_id,active)
                    log_action(u["id"],"set_income_active","income",selected["id"],str(active))
                    st.success("Estado atualizado.")
                    st.rerun()
            with c2:
                confirm_delete = st.checkbox("Confirmo que pretendo eliminar este rendimento")
                if st.button("Eliminar rendimento",type="secondary",disabled=not confirm_delete):
                    delete_income(selected["id"],household_id)
                    log_action(u["id"],"delete_income","income",selected["id"],selected["description"])
                    st.success("Rendimento eliminado.")
                    st.rerun()

            with st.expander("Editar rendimento selecionado"):
                current_cat = selected["category_name"]
                current_owner = selected["owner_name"]
                cat_names = list(cat_opts)
                member_names = list(member_opts)
                with st.form("edit_income"):
                    e_description = st.text_input("Descrição",selected["description"])
                    e_category = st.selectbox("Categoria",cat_names,index=cat_names.index(current_cat) if current_cat in cat_names else 0)
                    e_owner = st.selectbox("Titular",member_names,index=member_names.index(current_owner) if current_owner in member_names else 0)
                    e_amount = st.number_input("Valor (€)",min_value=0.0,value=float(selected["amount"]),step=10.0,format="%.2f")

                    recurring = selected["recurrence_type"]=="recurring"
                    e_nature = st.radio("Natureza",["Recorrente","Pontual"],index=0 if recurring else 1,horizontal=True)

                    if e_nature=="Pontual":
                        default_date = selected["income_date"] or selected["start_date"] or date.today()
                        e_income_date = st.date_input("Data",value=default_date)
                        e_frequency = "none"
                        e_start = None
                        e_end = None
                    else:
                        e_income_date = None
                        freq_labels = ["Mensal","Trimestral","Semestral","Anual"]
                        reverse_freq = {
                            "monthly":"Mensal","quarterly":"Trimestral",
                            "semiannual":"Semestral","annual":"Anual"
                        }
                        default_freq = reverse_freq.get(selected["frequency"],"Mensal")
                        e_freq_label = st.selectbox("Periodicidade",freq_labels,index=freq_labels.index(default_freq))
                        e_frequency = {"Mensal":"monthly","Trimestral":"quarterly","Semestral":"semiannual","Anual":"annual"}[e_freq_label]
                        e_start = st.date_input("Início",value=selected["start_date"] or date.today())
                        e_has_end = st.checkbox("Definir data de fim",value=selected["end_date"] is not None)
                        e_end = st.date_input("Fim",value=selected["end_date"] or date.today()) if e_has_end else None

                    e_notes = st.text_area("Notas",value=selected["notes"] or "")
                    save_edit = st.form_submit_button("Guardar alterações")

                if save_edit:
                    if not e_description.strip():
                        st.error("A descrição é obrigatória.")
                    elif e_amount <= 0:
                        st.error("O valor tem de ser superior a 0 €.")
                    elif e_nature=="Recorrente" and e_end and e_end<e_start:
                        st.error("A data de fim não pode ser anterior ao início.")
                    else:
                        update_income(
                            selected["id"],household_id,
                            cat_opts[e_category],member_opts[e_owner],
                            e_description.strip(),e_amount,e_income_date,
                            "recurring" if e_nature=="Recorrente" else "one_time",
                            e_frequency,e_start,e_end,e_notes.strip() or None
                        )
                        rebuild_income_occurrences(selected["id"],household_id)
                        log_action(u["id"],"update_income","income",selected["id"],e_description.strip())
                        st.success("Rendimento atualizado.")
                        st.rerun()

    with tab3:
        today = date.today()
        c1,c2 = st.columns(2)
        with c1:
            year = st.selectbox("Ano",list(range(today.year-5,today.year+2)),index=5)
        with c2:
            month = st.selectbox("Mês",list(MONTHS_PT.keys()),index=today.month-1,format_func=lambda x:MONTHS_PT[x])

        total = get_monthly_income_total(household_id,year,month)
        st.metric(f"Total de rendimentos — {MONTHS_PT[month]} {year}",
                  f"{total:,.2f} €".replace(",", "X").replace(".", ",").replace("X","."))

        occurrences = list_income_occurrences(household_id,year,month)
        if occurrences:
            hist = pd.DataFrame([{
                "Data":x["occurrence_date"],
                "Descrição":x["description"],
                "Categoria":x["category_name"],
                "Titular":x["owner_name"] or "—",
                "Valor (€)":float(x["amount"]),
            } for x in occurrences])
            st.dataframe(hist,use_container_width=True,hide_index=True)
        else:
            st.info("Sem rendimentos neste mês.")

        st.subheader("Evolução dos últimos 12 meses")
        history = get_income_history_monthly(household_id,12)
        if history:
            dfh = pd.DataFrame(history)
            dfh["Mês"] = dfh.apply(lambda r:f"{MONTHS_PT[int(r['month_num'])]} {int(r['year_num'])}",axis=1)
            dfh["Total"] = dfh["total"].astype(float)
            dfh = dfh.sort_values(["year_num","month_num"])
            st.line_chart(dfh.set_index("Mês")["Total"])

def page_expenses():
    household_id = require_household()
    u = st.session_state.user

    st.title("💸 Despesas")
    st.caption(f"Agregado: {u['household_name']}")

    tab1,tab2,tab3 = st.tabs(["Nova despesa","Despesas registadas","Histórico mensal"])

    categories = get_expense_categories()
    members = list_users_by_household(household_id)
    cat_opts = {c["name"]:c["id"] for c in categories}
    member_opts = {m["full_name"]:m["id"] for m in members}

    payment_methods = [
        "Cartão de débito",
        "Cartão de crédito",
        "Débito direto",
        "Transferência",
        "MB WAY",
        "Dinheiro",
        "Outro"
    ]

    with tab1:
        st.subheader("Adicionar despesa")

        if not categories:
            st.error("Não existem categorias de despesa configuradas.")
        elif not members:
            st.error("Não existem membros ativos neste agregado.")
        else:
            with st.form("new_expense"):
                c1,c2 = st.columns(2)

                with c1:
                    supplier = st.text_input("Fornecedor", placeholder="Ex.: Continente, EDP, MEO")
                    description = st.text_input("Descrição *", placeholder="Ex.: Compras supermercado")
                    category_label = st.selectbox("Categoria *", list(cat_opts))
                    owner_label = st.selectbox("Titular *", list(member_opts))
                    amount = st.number_input("Valor (€) *", min_value=0.0, step=5.0, format="%.2f")

                with c2:
                    payment_method = st.selectbox("Método de pagamento", payment_methods)
                    recurrence_label = st.radio("Natureza",["Pontual","Recorrente"],horizontal=True)

                    if recurrence_label == "Pontual":
                        expense_date = st.date_input("Data da despesa", value=date.today())
                        frequency = "none"
                        start_date = None
                        end_date = None
                    else:
                        expense_date = None
                        freq_label = st.selectbox("Periodicidade",["Mensal","Trimestral","Semestral","Anual"])
                        frequency = {
                            "Mensal":"monthly",
                            "Trimestral":"quarterly",
                            "Semestral":"semiannual",
                            "Anual":"annual"
                        }[freq_label]
                        start_date = st.date_input("Início", value=date.today())
                        has_end = st.checkbox("Definir data de fim")
                        end_date = st.date_input("Fim", value=date.today()) if has_end else None

                notes = st.text_area("Notas")
                submit = st.form_submit_button("Guardar despesa",use_container_width=True)

            if submit:
                if not description.strip():
                    st.error("A descrição é obrigatória.")
                elif amount <= 0:
                    st.error("O valor tem de ser superior a 0 €.")
                elif recurrence_label=="Recorrente" and end_date and end_date<start_date:
                    st.error("A data de fim não pode ser anterior à data de início.")
                else:
                    try:
                        expense_id = create_expense(
                            household_id=household_id,
                            category_id=cat_opts[category_label],
                            owner_user_id=member_opts[owner_label],
                            supplier=supplier.strip() or None,
                            description=description.strip(),
                            amount=amount,
                            expense_date=expense_date,
                            recurrence_type="recurring" if recurrence_label=="Recorrente" else "one_time",
                            frequency=frequency,
                            start_date=start_date,
                            end_date=end_date,
                            payment_method=payment_method,
                            notes=notes.strip() or None,
                            created_by=u["id"]
                        )
                        rebuild_expense_occurrences(expense_id,household_id)
                        log_action(u["id"],"create_expense","expense",expense_id,description.strip())
                        st.success("Despesa registada com sucesso.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao guardar despesa: {e}")

    with tab2:
        expenses = list_expenses(household_id)

        if not expenses:
            st.info("Ainda não existem despesas registadas.")
        else:
            table = []
            for item in expenses:
                table.append({
                    "ID":item["id"],
                    "Fornecedor":item["supplier"] or "—",
                    "Descrição":item["description"],
                    "Categoria":item["category_name"],
                    "Titular":item["owner_name"] or "—",
                    "Valor (€)":float(item["amount"]),
                    "Natureza":"Recorrente" if item["recurrence_type"]=="recurring" else "Pontual",
                    "Periodicidade":FREQ_LABELS.get(item["frequency"],item["frequency"]),
                    "Pagamento":item["payment_method"] or "—",
                    "Data":item["expense_date"],
                    "Início":item["start_date"],
                    "Fim":item["end_date"],
                    "Ativa":"Sim" if item["is_active"] else "Não"
                })

            st.dataframe(pd.DataFrame(table),use_container_width=True,hide_index=True)

            st.subheader("Gerir despesa")
            options = {
                f"#{e['id']} — {e['description']} — {float(e['amount']):.2f} €":e
                for e in expenses
            }
            label = st.selectbox("Selecionar despesa",list(options))
            selected = options[label]

            c1,c2 = st.columns(2)
            with c1:
                active = st.checkbox("Despesa ativa",value=bool(selected["is_active"]))
                if st.button("Guardar estado da despesa"):
                    set_expense_active(selected["id"],household_id,active)
                    log_action(u["id"],"set_expense_active","expense",selected["id"],str(active))
                    st.success("Estado atualizado.")
                    st.rerun()

            with c2:
                confirm_delete = st.checkbox("Confirmo que pretendo eliminar esta despesa")
                if st.button("Eliminar despesa",disabled=not confirm_delete):
                    delete_expense(selected["id"],household_id)
                    log_action(u["id"],"delete_expense","expense",selected["id"],selected["description"])
                    st.success("Despesa eliminada.")
                    st.rerun()

            with st.expander("Editar despesa selecionada"):
                cat_names = list(cat_opts)
                member_names = list(member_opts)
                current_cat = selected["category_name"]
                current_owner = selected["owner_name"]

                with st.form("edit_expense"):
                    e_supplier = st.text_input("Fornecedor",selected["supplier"] or "")
                    e_description = st.text_input("Descrição",selected["description"])
                    e_category = st.selectbox(
                        "Categoria",cat_names,
                        index=cat_names.index(current_cat) if current_cat in cat_names else 0
                    )
                    e_owner = st.selectbox(
                        "Titular",member_names,
                        index=member_names.index(current_owner) if current_owner in member_names else 0
                    )
                    e_amount = st.number_input(
                        "Valor (€)",min_value=0.0,value=float(selected["amount"]),
                        step=5.0,format="%.2f"
                    )

                    default_pm = selected["payment_method"] if selected["payment_method"] in payment_methods else "Outro"
                    e_payment = st.selectbox(
                        "Método de pagamento",
                        payment_methods,
                        index=payment_methods.index(default_pm)
                    )

                    recurring = selected["recurrence_type"]=="recurring"
                    e_nature = st.radio(
                        "Natureza",["Pontual","Recorrente"],
                        index=1 if recurring else 0,horizontal=True
                    )

                    if e_nature=="Pontual":
                        default_date = selected["expense_date"] or selected["start_date"] or date.today()
                        e_expense_date = st.date_input("Data",value=default_date)
                        e_frequency = "none"
                        e_start = None
                        e_end = None
                    else:
                        e_expense_date = None
                        freq_labels = ["Mensal","Trimestral","Semestral","Anual"]
                        reverse_freq = {
                            "monthly":"Mensal","quarterly":"Trimestral",
                            "semiannual":"Semestral","annual":"Anual"
                        }
                        default_freq = reverse_freq.get(selected["frequency"],"Mensal")
                        e_freq_label = st.selectbox(
                            "Periodicidade",freq_labels,
                            index=freq_labels.index(default_freq)
                        )
                        e_frequency = {
                            "Mensal":"monthly",
                            "Trimestral":"quarterly",
                            "Semestral":"semiannual",
                            "Anual":"annual"
                        }[e_freq_label]
                        e_start = st.date_input("Início",value=selected["start_date"] or date.today())
                        e_has_end = st.checkbox("Definir data de fim",value=selected["end_date"] is not None)
                        e_end = st.date_input("Fim",value=selected["end_date"] or date.today()) if e_has_end else None

                    e_notes = st.text_area("Notas",value=selected["notes"] or "")
                    save = st.form_submit_button("Guardar alterações")

                if save:
                    if not e_description.strip():
                        st.error("A descrição é obrigatória.")
                    elif e_amount <= 0:
                        st.error("O valor tem de ser superior a 0 €.")
                    elif e_nature=="Recorrente" and e_end and e_end<e_start:
                        st.error("A data de fim não pode ser anterior ao início.")
                    else:
                        update_expense(
                            selected["id"],household_id,
                            cat_opts[e_category],member_opts[e_owner],
                            e_supplier.strip() or None,e_description.strip(),
                            e_amount,e_expense_date,
                            "recurring" if e_nature=="Recorrente" else "one_time",
                            e_frequency,e_start,e_end,e_payment,e_notes.strip() or None
                        )
                        rebuild_expense_occurrences(selected["id"],household_id)
                        log_action(u["id"],"update_expense","expense",selected["id"],e_description.strip())
                        st.success("Despesa atualizada.")
                        st.rerun()

    with tab3:
        today = date.today()
        c1,c2 = st.columns(2)
        with c1:
            years = list(range(today.year-5,today.year+2))
            year = st.selectbox("Ano",years,index=years.index(today.year),key="expense_year")
        with c2:
            month = st.selectbox(
                "Mês",list(MONTHS_PT.keys()),index=today.month-1,
                format_func=lambda x:MONTHS_PT[x],key="expense_month"
            )

        total = get_monthly_expense_total(household_id,year,month)
        st.metric(
            f"Total de despesas — {MONTHS_PT[month]} {year}",
            f"{total:,.2f} €".replace(",", "X").replace(".", ",").replace("X",".")
        )

        occurrences = list_expense_occurrences(household_id,year,month)

        if occurrences:
            hist = pd.DataFrame([{
                "Data":x["occurrence_date"],
                "Fornecedor":x["supplier"] or "—",
                "Descrição":x["description"],
                "Categoria":x["category_name"],
                "Titular":x["owner_name"] or "—",
                "Pagamento":x["payment_method"] or "—",
                "Valor (€)":float(x["amount"]),
            } for x in occurrences])
            st.dataframe(hist,use_container_width=True,hide_index=True)

            cat = get_expenses_by_category(household_id,year,month)
            if cat:
                st.subheader("Distribuição por categoria")
                dfc = pd.DataFrame([{
                    "Categoria":r["category_name"],
                    "Total":float(r["total"])
                } for r in cat])
                st.bar_chart(dfc.set_index("Categoria")["Total"])
        else:
            st.info("Sem despesas neste mês.")

        st.subheader("Evolução dos últimos 12 meses")
        history = get_expense_history_monthly(household_id,12)
        if history:
            dfh = pd.DataFrame(history)
            dfh["Mês"] = dfh.apply(
                lambda r:f"{MONTHS_PT[int(r['month_num'])]} {int(r['year_num'])}",axis=1
            )
            dfh["Total"] = dfh["total"].astype(float)
            dfh = dfh.sort_values(["year_num","month_num"])
            st.line_chart(dfh.set_index("Mês")["Total"])

def page_documents():
    household_id = require_household()
    u = st.session_state.user

    st.title("📄 Faturas e Recibos")
    st.caption("V1.5 — Upload e gestão documental")

    BASE_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "documents")

    def safe_ext(filename):
        name = filename.lower()
        if "." not in name:
            return ""
        return "." + name.rsplit(".",1)[1]

    def document_folder(document_type, d):
        type_dir = "faturas" if document_type == "Fatura" else "recibos"
        return os.path.join(
            BASE_UPLOAD_DIR,
            str(household_id),
            str(d.year),
            f"{d.month:02d}",
            type_dir
        )

    def human_size(size):
        if size is None:
            return "—"
        size = float(size)
        if size < 1024:
            return f"{size:.0f} B"
        if size < 1024**2:
            return f"{size/1024:.1f} KB"
        return f"{size/(1024**2):.1f} MB"

    stats = get_document_stats(household_id)

    with st.expander("Automação inteligente"):
        ai_cfg = get_auto_create_threshold(household_id)

        auto_enabled = st.checkbox(
            "Permitir criação automática quando a confiança for elevada",
            value=ai_cfg["enabled"],
            help="Só será elegível quando não houver duplicado e existirem fornecedor, data e total."
        )

        auto_threshold = st.slider(
            "Confiança mínima para criação automática",
            min_value=85,
            max_value=100,
            value=int(ai_cfg["threshold"]),
            step=1
        )

        if st.button("Guardar definições de automação"):
            save_auto_create_settings(
                household_id,
                auto_enabled,
                auto_threshold
            )
            st.success("Definições guardadas.")
            st.rerun()

    s1,s2,s3,s4 = st.columns(4)
    s1.metric("Documentos", stats["total"])
    s2.metric("Ligados a despesas", stats["linked"])
    s3.metric("Por associar", stats["unlinked"])
    s4.metric("OCR pendente", stats["pending_ocr"])

    upload_tab, library_tab, detail_tab = st.tabs([
        "Upload",
        "Biblioteca",
        "Detalhe / Associação"
    ])

    expenses = list_expenses_for_document_link(household_id)

    expense_options = {"Sem associação": None}
    for e in expenses:
        supplier = e["supplier"] or "Sem fornecedor"
        ref = e["reference_date"] or "—"
        label = f"#{e['id']} — {supplier} — {e['description']} — {float(e['amount']):.2f} € — {ref}"
        expense_options[label] = e["id"]

    with upload_tab:
        st.subheader("Adicionar documento")

        with st.form("document_upload", clear_on_submit=True):
            document_type = st.selectbox(
                "Tipo de documento",
                ["Fatura","Recibo"]
            )

            uploaded_file = st.file_uploader(
                "Selecionar ficheiro",
                type=["pdf","jpg","jpeg","png"],
                help="Formatos permitidos: PDF, JPG, JPEG e PNG."
            )

            expense_label = st.selectbox(
                "Associar a uma despesa",
                list(expense_options.keys())
            )

            notes = st.text_area(
                "Notas",
                placeholder="Ex.: Fatura de eletricidade de setembro."
            )

            st.info(
                "Na V1.5 o documento é armazenado e associado à despesa. "
                "Na V1.6 o mesmo documento poderá ser enviado para OCR "
                "para extrair automaticamente fornecedor, data, total e outros campos."
            )

            submit_upload = st.form_submit_button(
                "Guardar documento",
                use_container_width=True
            )

        if submit_upload:
            if uploaded_file is None:
                st.error("Seleciona um ficheiro.")
            else:
                ext = safe_ext(uploaded_file.name)
                allowed = [".pdf",".jpg",".jpeg",".png"]

                if ext not in allowed:
                    st.error("Formato não permitido.")
                else:
                    file_bytes = uploaded_file.getvalue()
                    max_size = 10 * 1024 * 1024

                    if len(file_bytes) > max_size:
                        st.error("O ficheiro não pode ultrapassar 10 MB.")
                    else:
                        now = datetime.now()
                        folder = document_folder(document_type, now)
                        os.makedirs(folder, exist_ok=True)

                        stored_name = f"{uuid.uuid4().hex}{ext}"
                        abs_path = os.path.join(folder, stored_name)

                        with open(abs_path, "wb") as f:
                            f.write(file_bytes)

                        relative_path = os.path.relpath(abs_path, BASE_DIR)

                        mime_type = uploaded_file.type or {
                            ".pdf":"application/pdf",
                            ".jpg":"image/jpeg",
                            ".jpeg":"image/jpeg",
                            ".png":"image/png"
                        }.get(ext,"application/octet-stream")

                        try:
                            document_id = create_document(
                                household_id=household_id,
                                uploaded_by=u["id"],
                                original_name=uploaded_file.name,
                                stored_name=stored_name,
                                storage_path=relative_path,
                                mime_type=mime_type,
                                file_extension=ext,
                                file_size=len(file_bytes),
                                document_type=document_type.lower(),
                                expense_id=expense_options[expense_label],
                                notes=notes.strip() or None,
                                processing_status="stored"
                            )

                            log_action(
                                u["id"],
                                "upload_document",
                                "document",
                                document_id,
                                uploaded_file.name
                            )

                            st.success(
                                f"Documento guardado com sucesso. ID #{document_id}"
                            )
                            st.rerun()

                        except Exception as e:
                            try:
                                if os.path.exists(abs_path):
                                    os.remove(abs_path)
                            except Exception:
                                pass
                            st.error(f"Erro ao guardar documento: {e}")

    with library_tab:
        st.subheader("Biblioteca documental")

        docs = list_documents(household_id)

        if not docs:
            st.info("Ainda não existem documentos.")
        else:
            table = []
            for d in docs:
                table.append({
                    "ID": d["id"],
                    "Tipo": (d["document_type"] or "").capitalize(),
                    "Ficheiro": d["original_name"],
                    "Tamanho": human_size(d["file_size"]),
                    "Despesa": d["expense_description"] or "Sem associação",
                    "Fornecedor": d["expense_supplier"] or "—",
                    "Estado": d["processing_status"],
                    "OCR": d["ocr_status"],
                    "Enviado por": d["uploaded_by_name"] or "—",
                    "Data": d["created_at"],
                    "Ativo": "Sim" if d["is_active"] else "Não",
                })

            st.dataframe(
                pd.DataFrame(table),
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                "A coluna OCR já existe nesta versão, mas o processamento real "
                "será implementado na V1.6."
            )

    with detail_tab:
        docs = list_documents(household_id)

        if not docs:
            st.info("Não existem documentos para consultar.")
        else:
            opts = {
                f"#{d['id']} — {d['original_name']}": d["id"]
                for d in docs
            }

            chosen = st.selectbox(
                "Selecionar documento",
                list(opts.keys()),
                key="document_detail_select"
            )

            doc = get_document_by_id(opts[chosen], household_id)

            if doc:
                abs_path = os.path.join(BASE_DIR, doc["storage_path"])

                c1,c2 = st.columns([1.15,0.85])

                with c1:
                    st.subheader("Preview")

                    if not os.path.exists(abs_path):
                        st.error("O ficheiro físico não foi encontrado.")
                    else:
                        ext = (doc["file_extension"] or "").lower()

                        if ext in [".jpg",".jpeg",".png"]:
                            st.image(abs_path, use_container_width=True)

                        elif ext == ".pdf":
                            st.info(
                                "Preview PDF disponível através do browser. "
                                "Usa o botão abaixo para abrir/descarregar o ficheiro."
                            )

                            with open(abs_path,"rb") as f:
                                pdf_bytes = f.read()

                            st.download_button(
                                "Abrir / descarregar PDF",
                                data=pdf_bytes,
                                file_name=doc["original_name"],
                                mime="application/pdf",
                                use_container_width=True
                            )

                        else:
                            st.warning("Formato sem preview.")

                        if ext in [".jpg",".jpeg",".png"]:
                            with open(abs_path,"rb") as f:
                                file_bytes = f.read()

                            st.download_button(
                                "Descarregar original",
                                data=file_bytes,
                                file_name=doc["original_name"],
                                mime=doc["mime_type"] or "application/octet-stream",
                                use_container_width=True
                            )

                with c2:
                    st.subheader("Metadados")

                    st.write(f"**ID:** {doc['id']}")
                    st.write(f"**Tipo:** {(doc['document_type'] or '').capitalize()}")
                    st.write(f"**Nome original:** {doc['original_name']}")
                    st.write(f"**Tamanho:** {human_size(doc['file_size'])}")
                    st.write(f"**MIME:** {doc['mime_type']}")
                    st.write(f"**Estado:** {doc['processing_status']}")
                    st.write(f"**OCR:** {doc['ocr_status']}")
                    st.write(f"**Upload:** {doc['created_at']}")
                    st.write(f"**Enviado por:** {doc['uploaded_by_name'] or '—'}")

                    st.divider()

                    current_expense_id = doc["expense_id"]
                    expense_labels = list(expense_options.keys())

                    current_index = 0
                    if current_expense_id is not None:
                        for idx, label in enumerate(expense_labels):
                            if expense_options[label] == current_expense_id:
                                current_index = idx
                                break

                    link_label = st.selectbox(
                        "Despesa associada",
                        expense_labels,
                        index=current_index,
                        key=f"doc_link_{doc['id']}"
                    )

                    if st.button(
                        "Guardar associação",
                        key=f"save_link_{doc['id']}",
                        use_container_width=True
                    ):
                        update_document_link(
                            doc["id"],
                            household_id,
                            expense_options[link_label]
                        )
                        log_action(
                            u["id"],
                            "link_document_expense",
                            "document",
                            doc["id"],
                            str(expense_options[link_label])
                        )
                        st.success("Associação atualizada.")
                        st.rerun()

                    new_notes = st.text_area(
                        "Notas",
                        value=doc["notes"] or "",
                        key=f"doc_notes_{doc['id']}"
                    )

                    if st.button(
                        "Guardar notas",
                        key=f"save_notes_{doc['id']}",
                        use_container_width=True
                    ):
                        update_document_notes(
                            doc["id"],
                            household_id,
                            new_notes.strip() or None
                        )
                        st.success("Notas atualizadas.")
                        st.rerun()

                    st.divider()

                    active = st.checkbox(
                        "Documento ativo",
                        value=bool(doc["is_active"]),
                        key=f"doc_active_{doc['id']}"
                    )

                    if st.button(
                        "Guardar estado",
                        key=f"save_doc_state_{doc['id']}",
                        use_container_width=True
                    ):
                        set_document_active(
                            doc["id"],
                            household_id,
                            active
                        )
                        st.success("Estado atualizado.")
                        st.rerun()

                    confirm_delete = st.checkbox(
                        "Confirmo a eliminação definitiva",
                        key=f"doc_delete_confirm_{doc['id']}"
                    )

                    if st.button(
                        "Eliminar documento",
                        key=f"delete_doc_{doc['id']}",
                        disabled=not confirm_delete,
                        use_container_width=True
                    ):
                        stored_path = os.path.join(BASE_DIR, doc["storage_path"])

                        delete_document(doc["id"], household_id)

                        try:
                            if os.path.exists(stored_path):
                                os.remove(stored_path)
                        except Exception:
                            pass

                        log_action(
                            u["id"],
                            "delete_document",
                            "document",
                            doc["id"],
                            doc["original_name"]
                        )

                        st.success("Documento eliminado.")
                        st.rerun()

                    st.divider()
                    st.subheader("OCR / Extração automática")

                    if st.button(
                        "Processar documento",
                        key=f"process_doc_{doc['id']}",
                        use_container_width=True
                    ):
                        try:
                            update_document_processing(
                                doc["id"], household_id,
                                "processing", "processing"
                            )

                            file_hash = file_sha256(abs_path)
                            update_document_hash(
                                doc["id"],
                                household_id,
                                file_hash
                            )

                            duplicate = find_duplicate_document(
                                household_id=household_id,
                                file_hash=file_hash
                            )

                            text, method = extract_document_text(
                                abs_path,
                                doc["file_extension"] or ""
                            )

                            learned_rules = get_learning_rules_for_extractor(
                                household_id
                            )

                            fields = extract_fields(
                                text,
                                learned_rules=learned_rules
                            )

                            if not duplicate:
                                duplicate = find_duplicate_document(
                                    household_id=household_id,
                                    tax_id=fields["tax_id"],
                                    document_number=fields["document_number"],
                                    total=fields["total"],
                                    document_date=fields["document_date"]
                                )

                            if duplicate and duplicate.get("id") == doc["id"]:
                                duplicate = None

                            category_id = get_category_id_by_name(
                                fields["category"]
                            )

                            history_result = classify_document_with_history(
                                household_id=household_id,
                                supplier_name=fields["supplier"],
                                suggested_category_id=category_id,
                                amount=fields["total"]
                            )

                            final_category_id = (
                                history_result["category_id"]
                                if history_result["history_confidence"] >= 60
                                else category_id
                            )

                            monthly_pattern = detect_monthly_supplier_pattern(
                                household_id,
                                fields["supplier"]
                            )

                            ai_settings = get_auto_create_threshold(household_id)

                            blended_confidence = fields["confidence"]
                            if history_result["history_confidence"] > 0:
                                blended_confidence = round(
                                    (fields["confidence"] * 0.7) +
                                    (history_result["history_confidence"] * 0.3),
                                    1
                                )

                            auto_create_eligible = (
                                ai_settings["enabled"]
                                and blended_confidence >= ai_settings["threshold"]
                                and fields["total"] is not None
                                and fields["document_date"] is not None
                                and fields["supplier"] is not None
                                and not duplicate
                            )

                            save_document_extraction_v17(
                                document_id=doc["id"],
                                household_id=household_id,
                                ocr_text=text,
                                extracted_supplier=fields["supplier"],
                                extracted_tax_id=fields["tax_id"],
                                extracted_document_number=fields["document_number"],
                                extracted_document_date=fields["document_date"],
                                extracted_total=fields["total"],
                                extracted_vat=fields["vat"],
                                extracted_category_id=final_category_id,
                                extraction_confidence=blended_confidence,
                                field_confidence_json=json.dumps(
                                    fields["field_confidence"],
                                    ensure_ascii=False
                                ),
                                nif_valid=fields["tax_id_valid"],
                                extraction_method=method,
                                duplicate_document_id=duplicate["id"] if duplicate else None,
                                duplicate_match_type=duplicate["match_type"] if duplicate else None
                            )

                            save_document_v18_intelligence(
                                document_id=doc["id"],
                                household_id=household_id,
                                final_category_id=final_category_id,
                                history_confidence=history_result["history_confidence"],
                                history_reason=history_result["history_reason"],
                                monthly_pattern=monthly_pattern,
                                auto_create_eligible=auto_create_eligible
                            )

                            line_result = extract_line_items(
                                text,
                                document_total=fields["total"]
                            )

                            category_lookup = {
                                c["name"]: c["id"]
                                for c in get_expense_categories()
                            }

                            prepared_items = []
                            for item in line_result["items"]:
                                hist = get_item_category_history(
                                    household_id,
                                    item["description"]
                                )

                                if hist:
                                    item_category_id = hist[0]["category_id"]
                                    item_confidence = min(
                                        99.0,
                                        80.0 + float(hist[0]["usage_count"])
                                    )
                                else:
                                    item_category_id = category_lookup.get(
                                        item["suggested_category"],
                                        category_lookup.get("Outros")
                                    )
                                    item_confidence = item["category_confidence"]

                                prepared_items.append({
                                    **item,
                                    "category_id": item_category_id,
                                    "category_confidence": item_confidence
                                })

                            replace_document_items(
                                doc["id"],
                                household_id,
                                prepared_items
                            )

                            save_document_items_metadata(
                                doc["id"],
                                household_id,
                                line_result["items_total"],
                                line_result["coverage_percent"]
                            )

                            log_action(
                                u["id"],
                                "process_document",
                                "document",
                                doc["id"],
                                method
                            )

                            st.success("Documento processado.")

                            if auto_create_eligible:
                                st.info(
                                    "O documento ficou elegível para criação automática. "
                                    "Abre novamente o detalhe para rever os dados antes da criação."
                                )

                            st.rerun()

                        except Exception as e:
                            mark_document_ocr_error(
                                doc["id"],
                                household_id,
                                str(e)
                            )
                            st.error(f"Erro no processamento: {e}")

                    if doc.get("extraction_method"):
                        st.write(f"**Método:** {doc['extraction_method']}")

                    if doc.get("extraction_confidence") is not None:
                        st.metric(
                            "Confiança da extração",
                            f"{float(doc['extraction_confidence']):.0f}%"
                        )

                    if doc.get("field_confidence_json"):
                        try:
                            fc = json.loads(doc["field_confidence_json"])
                        except Exception:
                            fc = {}

                        if fc:
                            with st.expander("Confiança por campo"):
                                field_labels = {
                                    "supplier":"Fornecedor",
                                    "tax_id":"NIF",
                                    "document_number":"N.º documento",
                                    "document_date":"Data",
                                    "total":"Total",
                                    "vat":"IVA",
                                    "category":"Categoria"
                                }
                                for key,label in field_labels.items():
                                    if key in fc:
                                        st.write(f"**{label}:** {float(fc[key]):.0f}%")

                    if doc.get("extracted_tax_id"):
                        if doc.get("nif_valid") == 1:
                            st.success("NIF português validado.")
                        elif doc.get("nif_valid") == 0:
                            st.warning("NIF extraído, mas não passou a validação portuguesa.")

                    if doc.get("duplicate_document_id"):
                        st.warning(
                            f"Possível duplicado do documento "
                            f"#{doc['duplicate_document_id']} "
                            f"({doc.get('duplicate_match_type')})."
                        )


                    if doc.get("history_confidence") is not None:
                        st.metric(
                            "Confiança pelo histórico",
                            f"{float(doc['history_confidence']):.0f}%"
                        )
                        if doc.get("history_reason"):
                            st.caption(doc["history_reason"])

                    if doc.get("monthly_pattern_json"):
                        try:
                            mp = json.loads(doc["monthly_pattern_json"])
                        except Exception:
                            mp = None

                        if mp and mp.get("is_monthly_pattern"):
                            st.info(
                                f"Padrão mensal detetado: "
                                f"{mp.get('distinct_months')} meses com histórico, "
                                f"média aproximada de {float(mp.get('average_amount',0)):.2f} €."
                            )

                    if doc.get("auto_create_eligible"):
                        st.success(
                            "Este documento cumpre os critérios para criação automática."
                        )


                    st.divider()
                    st.subheader("Serviço associado")

                    current_service_link = get_document_service_link(
                        doc["id"],
                        household_id
                    )

                    if current_service_link:
                        st.success(
                            f"{current_service_link['service_type']} — "
                            f"{current_service_link['provider_name']}"
                        )
                        st.caption(
                            f"Método: {current_service_link['method']} | "
                            f"Confiança: {float(current_service_link['confidence'] or 0):.0f}%"
                        )
                    else:
                        suggestion = suggest_document_service_link(
                            doc["id"],
                            household_id
                        )
                        if suggestion:
                            st.info(
                                f"Sugestão: {suggestion['service_type']} | "
                                f"Confiança: {suggestion['confidence']:.0f}%"
                            )

                    st.subheader("Linhas / Produtos")

                items = list_document_items(doc["id"], household_id)

                if doc.get("items_extracted"):
                    cov = doc.get("items_coverage_percent")
                    c_it1, c_it2 = st.columns(2)
                    c_it1.metric(
                        "Total das linhas",
                        f"{float(doc.get('items_total') or 0):.2f} €"
                    )
                    c_it2.metric(
                        "Cobertura do total",
                        f"{float(cov or 0):.0f}%" if cov is not None else "—"
                    )

                if not items:
                    st.info(
                        "Não foram detetadas linhas de produto. "
                        "Podes adicioná-las manualmente."
                    )
                else:
                    summary = get_document_item_summary(
                        doc["id"],
                        household_id
                    )

                    if summary:
                        st.write("**Distribuição por categoria**")
                        sum_df = pd.DataFrame([
                            {
                                "Categoria": r["category_name"],
                                "Itens": r["item_count"],
                                "Total (€)": float(r["total"])
                            }
                            for r in summary
                        ])
                        st.dataframe(
                            sum_df,
                            use_container_width=True,
                            hide_index=True
                        )

                    categories = get_expense_categories()
                    category_names = [c["name"] for c in categories]
                    category_map = {c["name"]: c["id"] for c in categories}

                    for item in items:
                        with st.expander(
                            f"#{item['line_no']} — "
                            f"{item['description']} — "
                            f"{float(item['line_total']):.2f} €"
                        ):
                            current_cat = item["category_name"]
                            cat_index = (
                                category_names.index(current_cat)
                                if current_cat in category_names else 0
                            )

                            desc_value = st.text_input(
                                "Descrição",
                                value=item["description"],
                                key=f"item_desc_{item['id']}"
                            )

                            cc1,cc2,cc3 = st.columns(3)

                            qty_value = cc1.number_input(
                                "Quantidade",
                                min_value=0.001,
                                value=float(item["quantity"] or 1),
                                step=1.0,
                                key=f"item_qty_{item['id']}"
                            )

                            unit_value = cc2.number_input(
                                "Preço unitário (€)",
                                min_value=0.0,
                                value=float(item["unit_price"] or 0),
                                step=0.1,
                                format="%.2f",
                                key=f"item_unit_{item['id']}"
                            )

                            total_value = cc3.number_input(
                                "Total linha (€)",
                                min_value=0.0,
                                value=float(item["line_total"] or 0),
                                step=0.1,
                                format="%.2f",
                                key=f"item_total_{item['id']}"
                            )

                            cat_value = st.selectbox(
                                "Categoria",
                                category_names,
                                index=cat_index,
                                key=f"item_cat_{item['id']}"
                            )

                            st.caption(
                                f"Confiança categoria: "
                                f"{float(item['category_confidence'] or 0):.0f}% "
                                f"• Origem: {item['source']}"
                            )

                            ib1, ib2 = st.columns(2)

                            if ib1.button(
                                "Guardar linha",
                                key=f"save_item_{item['id']}",
                                use_container_width=True
                            ):
                                update_document_item(
                                    item["id"],
                                    doc["id"],
                                    household_id,
                                    desc_value.strip(),
                                    qty_value,
                                    unit_value,
                                    total_value,
                                    category_map[cat_value],
                                    True
                                )
                                st.success("Linha atualizada.")
                                st.rerun()

                            if ib2.button(
                                "Eliminar linha",
                                key=f"del_item_{item['id']}",
                                use_container_width=True
                            ):
                                delete_document_item(
                                    item["id"],
                                    doc["id"],
                                    household_id
                                )
                                st.success("Linha eliminada.")
                                st.rerun()

                with st.expander("Adicionar linha manualmente"):
                    categories = get_expense_categories()
                    category_names = [c["name"] for c in categories]
                    category_map = {c["name"]: c["id"] for c in categories}

                    with st.form(f"add_item_form_{doc['id']}"):
                        new_desc = st.text_input("Produto / descrição")
                        nc1,nc2,nc3 = st.columns(3)
                        new_qty = nc1.number_input(
                            "Quantidade",
                            min_value=0.001,
                            value=1.0,
                            step=1.0
                        )
                        new_unit = nc2.number_input(
                            "Preço unitário",
                            min_value=0.0,
                            value=0.0,
                            step=0.1
                        )
                        new_total = nc3.number_input(
                            "Total",
                            min_value=0.0,
                            value=0.0,
                            step=0.1
                        )
                        new_cat = st.selectbox(
                            "Categoria",
                            category_names
                        )
                        add_item_submit = st.form_submit_button(
                            "Adicionar linha"
                        )

                    if add_item_submit:
                        if not new_desc.strip():
                            st.error("Indica a descrição do produto.")
                        else:
                            if new_total <= 0 and new_unit > 0:
                                new_total = new_qty * new_unit

                            add_document_item(
                                doc["id"],
                                household_id,
                                new_desc.strip(),
                                new_qty,
                                new_unit,
                                new_total,
                                category_map[new_cat]
                            )
                            st.success("Linha adicionada.")
                            st.rerun()

                if doc.get("ocr_text"):
                    with st.expander("Texto extraído"):
                        st.text_area(
                            "Conteúdo",
                            value=doc["ocr_text"],
                            height=260,
                            disabled=True,
                            key=f"ocr_text_{doc['id']}"
                        )

                if doc.get("processing_status") == "error":
                    st.error(doc.get("ocr_error") or "Erro de processamento.")

                st.divider()
                st.subheader("Dados extraídos")

                categories = get_expense_categories()
                members = list_users_by_household(household_id)

                category_names = [c["name"] for c in categories]
                category_map = {c["name"]: c["id"] for c in categories}
                member_names = [m["full_name"] for m in members]
                member_map = {m["full_name"]: m["id"] for m in members}

                extracted_cat_name = "Outros"
                if doc.get("extracted_category_id"):
                    for c in categories:
                        if c["id"] == doc["extracted_category_id"]:
                            extracted_cat_name = c["name"]
                            break

                if not category_names:
                    st.warning("Sem categorias de despesa disponíveis.")
                elif not member_names:
                    st.warning("Sem membros ativos no agregado.")
                else:
                    default_cat_index = (
                        category_names.index(extracted_cat_name)
                        if extracted_cat_name in category_names else 0
                    )

                    with st.form(f"create_from_doc_{doc['id']}"):
                        supplier = st.text_input(
                            "Fornecedor",
                            value=doc.get("extracted_supplier") or ""
                        )

                        tax_id = st.text_input(
                            "NIF",
                            value=doc.get("extracted_tax_id") or "",
                            disabled=True
                        )

                        document_number = st.text_input(
                            "N.º documento",
                            value=doc.get("extracted_document_number") or "",
                            disabled=True
                        )

                        amount = st.number_input(
                            "Total (€)",
                            min_value=0.0,
                            value=float(doc.get("extracted_total") or 0),
                            step=1.0,
                            format="%.2f"
                        )

                        vat = st.number_input(
                            "IVA (€)",
                            min_value=0.0,
                            value=float(doc.get("extracted_vat") or 0),
                            step=0.5,
                            format="%.2f",
                            disabled=True
                        )

                        expense_date = st.date_input(
                            "Data",
                            value=doc.get("extracted_document_date") or date.today()
                        )

                        category_name = st.selectbox(
                            "Categoria sugerida",
                            category_names,
                            index=default_cat_index
                        )

                        owner_name = st.selectbox(
                            "Titular",
                            member_names
                        )

                        payment_method = st.selectbox(
                            "Método de pagamento",
                            [
                                "Cartão de débito",
                                "Cartão de crédito",
                                "Débito direto",
                                "Transferência",
                                "MB WAY",
                                "Dinheiro",
                                "Outro"
                            ]
                        )

                        description = st.text_input(
                            "Descrição",
                            value=(
                                f"{doc.get('document_type','Documento').capitalize()} "
                                f"{supplier or doc.get('extracted_supplier') or ''}"
                            ).strip()
                        )

                        create_submit = st.form_submit_button(
                            "Criar despesa a partir do documento",
                            use_container_width=True
                        )

                    if create_submit:
                        if doc.get("expense_id"):
                            st.warning(
                                "Este documento já está associado a uma despesa."
                            )
                        elif amount <= 0:
                            st.error("Confirma um valor total superior a 0 €.")
                        elif not description.strip():
                            st.error("A descrição é obrigatória.")
                        else:
                            try:
                                expense_id = create_expense_from_document(
                                    document_id=doc["id"],
                                    household_id=household_id,
                                    owner_user_id=member_map[owner_name],
                                    category_id=category_map[category_name],
                                    supplier=supplier.strip() or None,
                                    description=description.strip(),
                                    amount=amount,
                                    expense_date=expense_date,
                                    payment_method=payment_method,
                                    created_by=u["id"]
                                )

                                log_action(
                                    u["id"],
                                    "create_expense_from_document",
                                    "expense",
                                    expense_id,
                                    f"document={doc['id']}"
                                )

                                original_supplier = (doc.get("extracted_supplier") or "").strip()
                                confirmed_supplier = supplier.strip()
                                original_category_id = doc.get("extracted_category_id")
                                confirmed_category_id = category_map[category_name]

                                if confirmed_supplier:
                                    tokens = [
                                        token.lower()
                                        for token in re.findall(
                                            r"[A-Za-zÀ-ÿ0-9]{3,}",
                                            confirmed_supplier
                                        )
                                    ][:5]

                                    if (
                                        confirmed_supplier != original_supplier
                                        or confirmed_category_id != original_category_id
                                    ):
                                        learn_document_correction(
                                            household_id=household_id,
                                            supplier_name=confirmed_supplier,
                                            category_id=confirmed_category_id,
                                            match_tokens=tokens
                                        )

                                st.success(
                                    f"Despesa #{expense_id} criada e documento associado."
                                )
                                st.rerun()

                            except Exception as e:
                                st.error(f"Erro ao criar despesa: {e}")


def page_budgets():
    household_id = require_household()

    st.title("🎯 Orçamentos")
    st.caption("V1.9 — Orçamentos inteligentes e alertas de desvio")

    today = date.today()

    c1,c2 = st.columns(2)
    year = c1.selectbox(
        "Ano",
        list(range(today.year - 2, today.year + 2)),
        index=2,
        key="budget_year"
    )

    month = c2.selectbox(
        "Mês",
        list(range(1,13)),
        index=today.month - 1,
        format_func=lambda x: MONTHS_PT[x],
        key="budget_month"
    )

    categories = get_expense_categories()
    category_names = [c["name"] for c in categories]
    category_map = {c["name"]: c["id"] for c in categories}

    st.subheader("Definir orçamento")

    if categories:
        with st.form("budget_form"):
            category_name = st.selectbox(
                "Categoria",
                category_names
            )

            suggested = suggest_budget_from_history(
                household_id,
                category_map[category_name],
                3
            )

            st.caption(
                f"Sugestão com base nos últimos meses: "
                f"{suggested:.2f} €"
                if suggested > 0
                else "Ainda não existe histórico suficiente para sugerir um orçamento."
            )

            amount_limit = st.number_input(
                "Limite mensal (€)",
                min_value=0.0,
                value=float(suggested or 0),
                step=10.0,
                format="%.2f"
            )

            warning_percent = st.slider(
                "Avisar a partir de",
                min_value=50,
                max_value=100,
                value=80,
                step=5
            )

            budget_submit = st.form_submit_button(
                "Guardar orçamento",
                use_container_width=True
            )

        if budget_submit:
            if amount_limit <= 0:
                st.error("O limite deve ser superior a 0 €.")
            else:
                upsert_budget(
                    household_id,
                    category_map[category_name],
                    year,
                    month,
                    amount_limit,
                    warning_percent
                )
                st.success("Orçamento guardado.")
                st.rerun()

    st.divider()
    st.subheader("Estado dos orçamentos")

    alerts = get_budget_alerts(
        household_id,
        year,
        month
    )

    if not alerts:
        st.info("Ainda não existem orçamentos para este período.")
    else:
        for row in alerts:
            with st.container(border=True):
                b1,b2,b3,b4 = st.columns(4)

                b1.metric(
                    row["category_name"],
                    f"{float(row['spent']):.2f} €"
                )

                b2.metric(
                    "Limite",
                    f"{float(row['amount_limit']):.2f} €"
                )

                b3.metric(
                    "Utilização",
                    f"{float(row['percent']):.0f}%"
                )

                b4.metric(
                    "Disponível",
                    f"{float(row['remaining']):.2f} €"
                )

                progress = min(
                    1.0,
                    max(0.0, float(row["percent"]) / 100)
                )
                st.progress(progress)

                if row["level"] == "exceeded":
                    st.error(
                        f"Orçamento ultrapassado em "
                        f"{abs(float(row['remaining'])):.2f} €."
                    )
                elif row["level"] == "warning":
                    st.warning(
                        f"Já utilizaste {float(row['percent']):.0f}% "
                        f"do orçamento desta categoria."
                    )
                else:
                    st.success("Dentro do orçamento definido.")

                if st.button(
                    "Eliminar orçamento",
                    key=f"delete_budget_{row['id']}"
                ):
                    delete_budget(row["id"], household_id)
                    st.rerun()

    st.divider()
    st.subheader("Como são calculados os valores")

    st.info(
        "Na V1.9, o consumo por orçamento usa as linhas/produtos extraídos "
        "dos documentos. Assim, uma compra de supermercado pode contribuir "
        "simultaneamente para Alimentação, Higiene, Bebé, Casa, etc."
    )


def page_planning():
    household_id = require_household()

    st.title("📅 Planeamento Financeiro")
    st.caption("V2.0 — previsão de saldo, compromissos futuros e alertas")

    today = date.today()

    c1,c2 = st.columns(2)
    year = c1.selectbox(
        "Ano",
        list(range(today.year - 1, today.year + 2)),
        index=1,
        key="forecast_year"
    )
    month = c2.selectbox(
        "Mês",
        list(range(1,13)),
        index=today.month - 1,
        format_func=lambda x: MONTHS_PT[x],
        key="forecast_month"
    )

    forecast = get_financial_forecast(
        household_id,
        year,
        month,
        today
    )

    f1,f2,f3,f4 = st.columns(4)
    f1.metric("Saldo atual", f"{forecast['current_balance']:.2f} €")
    f2.metric("Entradas futuras", f"{forecast['future_income']:.2f} €")
    f3.metric("Despesas futuras", f"{forecast['future_expense']:.2f} €")
    f4.metric("Saldo previsto", f"{forecast['projected_balance']:.2f} €")

    if forecast["projected_balance"] < 0:
        st.error(
            f"Se nada mudar, o mês termina com saldo previsto de "
            f"{forecast['projected_balance']:.2f} €."
        )
    elif forecast["projected_balance"] < 300:
        st.warning(
            f"O saldo previsto no final do mês é baixo: "
            f"{forecast['projected_balance']:.2f} €."
        )
    else:
        st.success(
            f"Saldo previsto no final do mês: "
            f"{forecast['projected_balance']:.2f} €."
        )

    st.divider()
    st.subheader("Compromissos futuros")

    commitments = get_upcoming_commitments(
        household_id,
        today,
        45
    )

    if not commitments:
        st.info("Sem compromissos futuros registados nos próximos 45 dias.")
    else:
        rows = []
        for r in commitments:
            rows.append({
                "Data": r["occurrence_date"],
                "Tipo": "Entrada" if r["kind"] == "income" else "Saída",
                "Descrição": r["description"],
                "Fornecedor": r.get("supplier") or "",
                "Valor (€)": float(r["amount"])
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

    st.divider()
    st.subheader("Alertas antecipados")

    alerts = get_forecast_alerts(
        household_id,
        today,
        45
    )

    if not alerts:
        st.success("Sem alertas financeiros relevantes no horizonte analisado.")
    else:
        for alert in alerts:
            text = (
                f"{alert['date']} — {alert['title']}: "
                f"{alert['message']}"
            )
            if alert["level"] == "warning":
                st.warning(text)
            else:
                st.info(text)


def page_goals():
    household_id = require_household()

    st.title("🎯 Metas de Poupança")
    st.caption("V2.0 — objetivos, progresso e previsão de conclusão")

    with st.expander("Criar nova meta", expanded=True):
        with st.form("new_goal"):
            name = st.text_input("Nome da meta", placeholder="Ex.: Fundo de emergência")
            target_amount = st.number_input(
                "Objetivo (€)",
                min_value=1.0,
                value=1000.0,
                step=50.0,
                format="%.2f"
            )
            current_amount = st.number_input(
                "Já poupado (€)",
                min_value=0.0,
                value=0.0,
                step=25.0,
                format="%.2f"
            )
            use_date = st.checkbox("Definir data objetivo")
            target_date = st.date_input(
                "Data objetivo",
                value=date.today(),
                disabled=not use_date
            )
            submit_goal = st.form_submit_button(
                "Criar meta",
                use_container_width=True
            )

        if submit_goal:
            if not name.strip():
                st.error("Indica o nome da meta.")
            elif current_amount > target_amount:
                st.error("O valor já poupado não pode ultrapassar o objetivo.")
            else:
                create_saving_goal(
                    household_id,
                    name.strip(),
                    target_amount,
                    target_date if use_date else None,
                    current_amount
                )
                st.success("Meta criada.")
                st.rerun()

    goals = list_saving_goals(household_id)

    if not goals:
        st.info("Ainda não existem metas de poupança.")
        return

    for goal in goals:
        target = float(goal["target_amount"])
        current = float(goal["current_amount"])
        percent = (current / target * 100) if target > 0 else 0
        projection = get_goal_projection(household_id, goal)

        with st.container(border=True):
            g1,g2,g3 = st.columns(3)

            g1.metric(goal["name"], f"{current:.2f} €")
            g2.metric("Objetivo", f"{target:.2f} €")
            g3.metric("Progresso", f"{percent:.0f}%")

            st.progress(min(1.0, max(0.0, percent / 100)))

            if goal["target_date"]:
                st.caption(f"Data objetivo: {goal['target_date']}")

            if projection["months_needed"] is not None:
                st.caption(
                    f"Com uma poupança média de "
                    f"{projection['average_monthly_saving']:.2f} €/mês, "
                    f"faltam cerca de {projection['months_needed']:.1f} meses."
                )
            else:
                st.caption(
                    "Ainda não existe histórico de poupança positiva suficiente "
                    "para estimar a conclusão."
                )

            with st.form(f"goal_update_{goal['id']}"):
                new_current = st.number_input(
                    "Atualizar valor poupado",
                    min_value=0.0,
                    value=current,
                    max_value=target,
                    step=25.0,
                    key=f"goal_current_{goal['id']}"
                )
                goal_save = st.form_submit_button("Guardar progresso")

            if goal_save:
                update_saving_goal(
                    goal["id"],
                    household_id,
                    current_amount=new_current
                )
                st.success("Progresso atualizado.")
                st.rerun()

            if st.button(
                "Eliminar meta",
                key=f"delete_goal_{goal['id']}"
            ):
                delete_saving_goal(goal["id"], household_id)
                st.rerun()


def page_financial_calendar():
    household_id = require_household()

    st.title("🗓️ Calendário Financeiro")
    st.caption("V2.1 — visão mensal de entradas e saídas")

    today = date.today()

    c1,c2 = st.columns(2)
    year = c1.selectbox(
        "Ano",
        list(range(today.year - 1, today.year + 2)),
        index=1,
        key="calendar_year"
    )
    month = c2.selectbox(
        "Mês",
        list(range(1,13)),
        index=today.month - 1,
        format_func=lambda x: MONTHS_PT[x],
        key="calendar_month"
    )

    import calendar as _calendar

    first_day = date(year, month, 1)
    last_day = date(
        year,
        month,
        _calendar.monthrange(year, month)[1]
    )

    events = get_calendar_events(
        household_id,
        first_day,
        last_day
    )

    by_day = {}
    for event in events:
        day = event["event_date"].day
        by_day.setdefault(day, []).append(event)

    st.subheader(f"{MONTHS_PT[month]} {year}")

    weeks = _calendar.monthcalendar(year, month)

    for week in weeks:
        cols = st.columns(7)
        for idx, day_num in enumerate(week):
            with cols[idx]:
                if day_num == 0:
                    st.write("")
                    continue

                with st.container(border=True):
                    st.markdown(f"**{day_num}**")

                    day_events = by_day.get(day_num, [])

                    if not day_events:
                        st.caption("—")
                    else:
                        for ev in day_events[:4]:
                            amount = float(ev["amount"])
                            if ev["kind"] == "income":
                                st.success(
                                    f"+ {amount:.2f} €\n\n{ev['title']}"
                                )
                            else:
                                label = ev["supplier"] or ev["title"]
                                st.error(
                                    f"- {amount:.2f} €\n\n{label}"
                                )

                        if len(day_events) > 4:
                            st.caption(
                                f"+ {len(day_events)-4} movimento(s)"
                            )

    st.divider()
    st.subheader("Lista do mês")

    if events:
        df = pd.DataFrame([
            {
                "Data": e["event_date"],
                "Tipo": "Entrada" if e["kind"] == "income" else "Saída",
                "Descrição": e["title"],
                "Fornecedor": e.get("supplier") or "",
                "Valor (€)": float(e["amount"])
            }
            for e in events
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Sem movimentos previstos neste mês.")


def page_scenarios():
    household_id = require_household()

    st.title("🧮 Cenários 'E se?'")
    st.caption("V2.1 — simular cortes de custos e projeções de poupança")

    today = date.today()

    st.subheader("Previsão 3 / 6 / 12 meses")

    horizon = st.segmented_control(
        "Horizonte",
        options=[3,6,12],
        default=6,
        format_func=lambda x: f"{x} meses"
    )

    if horizon is None:
        horizon = 6

    forecast_rows = get_multi_month_forecast(
        household_id,
        today.year,
        today.month,
        horizon
    )

    if forecast_rows:
        fdf = pd.DataFrame([
            {
                "Período": f"{MONTHS_PT[r['month']]} {r['year']}",
                "Rendimentos": r["income"],
                "Despesas": r["expense"],
                "Saldo": r["balance"]
            }
            for r in forecast_rows
        ])

        st.line_chart(
            fdf.set_index("Período")[["Rendimentos","Despesas","Saldo"]]
        )

        projected_total = sum(float(r["balance"]) for r in forecast_rows)

        st.metric(
            f"Saldo acumulado projetado ({horizon} meses)",
            f"{projected_total:.2f} €"
        )

    st.divider()
    st.subheader("Simular redução de despesas")

    recurring = get_recurring_expenses_for_scenarios(household_id)

    reductions = {}

    if not recurring:
        st.info("Não existem despesas recorrentes ativas.")
    else:
        st.caption(
            "Define uma percentagem de redução para cada despesa recorrente."
        )

        for exp in recurring:
            label = (
                f"{exp['supplier'] or exp['description']} "
                f"— {float(exp['amount']):.2f} € "
                f"({exp['frequency']})"
            )

            reductions[exp["id"]] = st.slider(
                label,
                min_value=0,
                max_value=100,
                value=0,
                step=5,
                key=f"scenario_red_{exp['id']}"
            )

        simulation = simulate_expense_reduction(
            household_id,
            reductions,
            months=horizon
        )

        s1,s2,s3 = st.columns(3)
        s1.metric(
            "Poupança mensal",
            f"{simulation['monthly_saving']:.2f} €"
        )
        s2.metric(
            "Poupança anual",
            f"{simulation['annual_saving']:.2f} €"
        )
        s3.metric(
            f"Poupança em {horizon} meses",
            f"{simulation['period_saving']:.2f} €"
        )

        if simulation["details"]:
            st.dataframe(
                pd.DataFrame(simulation["details"]),
                use_container_width=True,
                hide_index=True
            )

        st.subheader("Guardar cenário")

        with st.form("save_scenario_form"):
            scenario_name = st.text_input(
                "Nome do cenário",
                placeholder="Ex.: Cortar telecom + subscrições"
            )
            save_scenario = st.form_submit_button("Guardar cenário")

        if save_scenario:
            if not scenario_name.strip():
                st.error("Indica um nome para o cenário.")
            else:
                payload = json.dumps({
                    "horizon_months": horizon,
                    "reductions": reductions
                }, ensure_ascii=False)

                save_scenario_preset(
                    household_id,
                    scenario_name.strip(),
                    payload
                )
                st.success("Cenário guardado.")
                st.rerun()

    st.divider()
    st.subheader("Cenários guardados")

    presets = get_scenario_presets(household_id)

    if not presets:
        st.info("Ainda não existem cenários guardados.")
    else:
        for preset in presets:
            with st.container(border=True):
                st.write(f"**{preset['name']}**")

                try:
                    data = json.loads(preset["scenario_json"])
                except Exception:
                    data = {}

                st.caption(
                    f"Horizonte: {data.get('horizon_months','—')} meses"
                )

                if st.button(
                    "Eliminar cenário",
                    key=f"delete_scenario_{preset['id']}"
                ):
                    delete_scenario_preset(
                        preset["id"],
                        household_id
                    )
                    st.rerun()

    st.divider()
    st.subheader("Projeção anual de poupança")

    projection = get_annual_savings_projection(
        household_id,
        today.year
    )

    a1,a2,a3,a4 = st.columns(4)
    a1.metric(
        "Rendimentos anuais",
        f"{projection['total_income']:.2f} €"
    )
    a2.metric(
        "Despesas anuais",
        f"{projection['total_expense']:.2f} €"
    )
    a3.metric(
        "Poupança anual",
        f"{projection['total_saving']:.2f} €"
    )
    a4.metric(
        "Taxa de poupança",
        f"{projection['savings_rate']:.1f}%"
    )

    pdf = pd.DataFrame([
        {
            "Mês": MONTHS_PT[r["month"]],
            "Rendimentos": r["income"],
            "Despesas": r["expense"],
            "Saldo": r["balance"]
        }
        for r in projection["months"]
    ])

    st.bar_chart(
        pdf.set_index("Mês")[["Saldo"]]
    )


def page_risk():
    household_id = require_household()

    st.title("🛡️ Risco Financeiro")
    st.caption("V2.2 — scoring, anomalias, desvios e recomendações")

    today = date.today()

    c1,c2 = st.columns(2)
    year = c1.selectbox(
        "Ano",
        list(range(today.year - 1, today.year + 2)),
        index=1,
        key="risk_year"
    )
    month = c2.selectbox(
        "Mês",
        list(range(1,13)),
        index=today.month - 1,
        format_func=lambda x: MONTHS_PT[x],
        key="risk_month"
    )

    risk = get_financial_risk_score(
        household_id,
        year,
        month
    )

    save_risk_snapshot(
        household_id,
        year,
        month,
        risk
    )

    r1,r2,r3,r4 = st.columns(4)
    r1.metric("Score de risco", f"{risk['score']:.0f}/100")
    r2.metric("Nível", risk["label"])
    r3.metric("Saldo projetado", f"{risk['projected_balance']:.2f} €")
    r4.metric("Taxa poupança", f"{risk['savings_rate']:.1f}%")

    if risk["level"] == "critical":
        st.error("Risco financeiro crítico.")
    elif risk["level"] == "high":
        st.warning("Risco financeiro elevado.")
    elif risk["level"] == "moderate":
        st.info("Risco financeiro moderado.")
    else:
        st.success("Risco financeiro baixo.")

    if risk["reasons"]:
        st.write("**Porque foi atribuído este score:**")
        for reason in risk["reasons"]:
            st.write(f"• {reason}")

    st.divider()
    st.subheader("Deteção de anomalias")

    anomalies = detect_expense_anomalies(household_id)

    if not anomalies:
        st.success("Não foram detetadas anomalias relevantes.")
    else:
        for a in anomalies:
            with st.container(border=True):
                a1,a2,a3 = st.columns(3)
                a1.metric(
                    a["category_name"],
                    f"{a['current_total']:.2f} €"
                )
                a2.metric(
                    "Média recente",
                    f"{a['baseline']:.2f} €"
                )
                a3.metric(
                    "Desvio",
                    f"+{a['deviation_pct']:.1f}%"
                )

                st.warning(
                    f"A categoria {a['category_name']} está "
                    f"{a['deviation_pct']:.1f}% acima da média recente."
                )

    st.divider()
    st.subheader("Previsão de desvios ao orçamento")

    deviations = get_budget_deviation_forecast(
        household_id,
        year,
        month
    )

    if not deviations:
        st.info("Não existem orçamentos definidos para este período.")
    else:
        for d in deviations:
            with st.container(border=True):
                d1,d2,d3,d4 = st.columns(4)

                d1.metric(
                    d["category_name"],
                    f"{float(d['spent']):.2f} €"
                )
                d2.metric(
                    "Orçamento",
                    f"{float(d['amount_limit']):.2f} €"
                )
                d3.metric(
                    "Projeção",
                    f"{float(d['projected_spend']):.2f} €"
                )
                d4.metric(
                    "Desvio projetado",
                    f"{float(d['projected_deviation']):.2f} €"
                )

                if d["projected_over_budget"]:
                    st.warning(
                        f"Se o ritmo atual se mantiver, esta categoria "
                        f"ultrapassa o orçamento em "
                        f"{abs(float(d['projected_deviation'])):.2f} €."
                    )
                else:
                    st.success("Projeção ainda dentro do orçamento.")

    st.divider()
    st.subheader("Onde cortar primeiro")

    recommendations = get_cut_recommendations(
        household_id,
        year,
        month
    )

    if not recommendations:
        st.info("Sem despesas recorrentes suficientes para gerar recomendações.")
    else:
        for idx, rec in enumerate(recommendations, start=1):
            with st.container(border=True):
                title = rec["supplier"] or rec["description"]
                st.write(f"**#{idx} — {title}**")

                c1,c2,c3,c4 = st.columns(4)
                c1.metric(
                    "Custo mensal",
                    f"{rec['monthly_equivalent']:.2f} €"
                )
                c2.metric(
                    "Corte sugerido",
                    f"{rec['suggested_reduction_pct']}%"
                )
                c3.metric(
                    "Poupança/mês",
                    f"{rec['estimated_monthly_saving']:.2f} €"
                )
                c4.metric(
                    "Poupança/ano",
                    f"{rec['estimated_annual_saving']:.2f} €"
                )

                st.caption(
                    f"Categoria: {rec['category_name'] or 'Sem categoria'}"
                )

                for reason in rec["reasons"]:
                    st.write(f"• {reason}")

    st.divider()
    st.subheader("Histórico do risco")

    snapshots = list_risk_snapshots(
        household_id,
        12
    )

    if snapshots:
        sdf = pd.DataFrame([
            {
                "Período": f"{MONTHS_PT[int(s['month_num'])]} {s['year_num']}",
                "Score": float(s["score"]),
                "Nível": s["level"]
            }
            for s in reversed(snapshots)
        ])

        st.line_chart(
            sdf.set_index("Período")[["Score"]]
        )
    else:
        st.info("Ainda não existe histórico suficiente de scoring.")


def page_market():
    household_id = require_household()

    st.title("📡 Market Intelligence")
    st.caption("V2.3 — comparar serviços atuais com ofertas alternativas")

    service_types = [
        "Eletricidade",
        "Gás",
        "Telecomunicações",
        "Internet",
        "Telemóvel",
        "Seguros",
        "Streaming",
        "Crédito",
        "Outros"
    ]

    summary = get_market_savings_summary(household_id)

    m1,m2,m3,m4 = st.columns(4)
    m1.metric(
        "Custo atual/mês",
        f"{summary['current_monthly_total']:.2f} €"
    )
    m2.metric(
        "Melhor cenário/mês",
        f"{summary['best_monthly_total']:.2f} €"
    )
    m3.metric(
        "Poupança potencial/mês",
        f"{summary['potential_monthly_saving']:.2f} €"
    )
    m4.metric(
        "Poupança potencial/ano",
        f"{summary['potential_annual_saving']:.2f} €"
    )

    tabs = st.tabs([
        "Os meus serviços",
        "Comparar",
        "Ofertas de mercado",
        "Fontes automáticas",
        "Alertas",
        "Fornecedores"
    ])

    with tabs[0]:
        st.subheader("Serviços atuais do agregado")

        services = list_household_services(household_id)

        if services:
            for srv in services:
                with st.container(border=True):
                    s1,s2,s3 = st.columns(3)
                    s1.metric(
                        srv["service_type"],
                        f"{float(srv['monthly_cost'] or 0):.2f} €/mês"
                    )
                    s2.write(f"**Fornecedor:** {srv['provider_name']}")
                    s2.caption(srv["plan_name"] or "Sem plano definido")

                    if srv["contract_end_date"]:
                        s3.write("**Fim de contrato**")
                        s3.caption(str(srv["contract_end_date"]))
                    else:
                        s3.caption("Sem data de fidelização definida")

                    with st.expander("Editar serviço"):
                        provider_name = st.text_input(
                            "Fornecedor",
                            value=srv["provider_name"],
                            key=f"srv_provider_{srv['id']}"
                        )
                        plan_name = st.text_input(
                            "Plano",
                            value=srv["plan_name"] or "",
                            key=f"srv_plan_{srv['id']}"
                        )
                        monthly_cost = st.number_input(
                            "Custo mensal (€)",
                            min_value=0.0,
                            value=float(srv["monthly_cost"] or 0),
                            step=1.0,
                            format="%.2f",
                            key=f"srv_monthly_{srv['id']}"
                        )
                        unit_price = st.number_input(
                            "Preço unitário (€)",
                            min_value=0.0,
                            value=float(srv["unit_price"] or 0),
                            step=0.001,
                            format="%.6f",
                            key=f"srv_unit_{srv['id']}"
                        )
                        daily_price = st.number_input(
                            "Preço diário (€)",
                            min_value=0.0,
                            value=float(srv["daily_price"] or 0),
                            step=0.001,
                            format="%.6f",
                            key=f"srv_daily_{srv['id']}"
                        )

                        if st.button(
                            "Guardar serviço",
                            key=f"save_srv_{srv['id']}"
                        ):
                            update_household_service(
                                srv["id"],
                                household_id,
                                provider_name.strip(),
                                plan_name.strip() or None,
                                monthly_cost,
                                unit_price or None,
                                daily_price or None,
                                srv["contract_end_date"],
                                srv["notes"],
                                True
                            )
                            st.success("Serviço atualizado.")
                            st.rerun()

                        if st.button(
                            "Eliminar serviço",
                            key=f"delete_srv_{srv['id']}"
                        ):
                            delete_household_service(
                                srv["id"],
                                household_id
                            )
                            st.rerun()
        else:
            st.info("Ainda não existem serviços atuais registados.")

        st.subheader("Adicionar serviço")

        with st.form("new_household_service"):
            srv_type = st.selectbox("Tipo de serviço", service_types)
            provider_name = st.text_input("Fornecedor atual")
            plan_name = st.text_input("Plano / produto")
            monthly_cost = st.number_input(
                "Custo mensal médio (€)",
                min_value=0.0,
                value=0.0,
                step=1.0
            )
            c1,c2 = st.columns(2)
            unit_price = c1.number_input(
                "Preço unitário (€)",
                min_value=0.0,
                value=0.0,
                step=0.001,
                format="%.6f"
            )
            daily_price = c2.number_input(
                "Preço diário (€)",
                min_value=0.0,
                value=0.0,
                step=0.001,
                format="%.6f"
            )
            has_start = st.checkbox("Definir início de contrato")
            contract_start = st.date_input(
                "Início de contrato",
                value=date.today(),
                disabled=not has_start
            )
            has_end = st.checkbox("Tem data de fim de contrato")
            contract_end = st.date_input(
                "Fim de contrato",
                value=date.today(),
                disabled=not has_end
            )
            has_fidelity = st.checkbox("Tem fidelização")
            fidelity_end = st.date_input(
                "Fim da fidelização",
                value=date.today(),
                disabled=not has_fidelity
            )
            contract_reference = st.text_input(
                "Referência / nº contrato"
            )
            notes = st.text_area("Notas")
            submit_service = st.form_submit_button("Adicionar serviço")

        if submit_service:
            if not provider_name.strip():
                st.error("Indica o fornecedor atual.")
            elif monthly_cost <= 0:
                st.error("Indica um custo mensal superior a 0 €.")
            else:
                create_household_service_v25(
                    household_id,
                    srv_type,
                    provider_name.strip(),
                    plan_name.strip() or None,
                    monthly_cost,
                    unit_price or None,
                    daily_price or None,
                    contract_start if has_start else None,
                    contract_end if has_end else None,
                    fidelity_end if has_fidelity else None,
                    contract_reference.strip() or None,
                    None,
                    notes.strip() or None
                )
                st.success("Serviço adicionado.")
                st.rerun()

    with tabs[1]:
        st.subheader("Comparar alternativas")

        services = list_household_services(household_id)

        if not services:
            st.info("Adiciona primeiro pelo menos um serviço atual.")
        else:
            labels = {
                s["id"]: (
                    f"{s['service_type']} — "
                    f"{s['provider_name']} — "
                    f"{float(s['monthly_cost'] or 0):.2f} €/mês"
                )
                for s in services
            }

            selected_id = st.selectbox(
                "Serviço a comparar",
                list(labels.keys()),
                format_func=lambda x: labels[x]
            )

            selected = next(
                s for s in services
                if s["id"] == selected_id
            )

            comparisons = compare_service_offers_v24(selected)

            if not comparisons:
                st.info(
                    "Ainda não existem ofertas de mercado compatíveis "
                    "com este tipo de serviço."
                )
            else:
                useful = [
                    c for c in comparisons
                    if c["estimated_monthly_cost"] is not None
                ]

                if useful:
                    best = useful[0]

                    b1,b2,b3,b4 = st.columns(4)
                    b1.metric(
                        "Atual",
                        f"{float(selected['monthly_cost']):.2f} €/mês"
                    )
                    b2.metric(
                        "Melhor alternativa",
                        f"{best['estimated_monthly_cost']:.2f} €/mês"
                    )
                    b3.metric(
                        "Poupa/mês",
                        f"{best['saving_month']:.2f} €"
                    )
                    b4.metric(
                        "Poupa/ano",
                        f"{best['saving_year']:.2f} €"
                    )

                rows = []
                for c in comparisons:
                    rows.append({
                        "Fornecedor": c["provider_name"],
                        "Plano": c["plan_name"],
                        "Custo estimado/mês": c["estimated_monthly_cost"],
                        "Poupança/mês": c["saving_month"],
                        "Poupança/ano": c["saving_year"],
                        "Poupança %": c["saving_pct"],
                        "Fidelização (meses)": c["contract_months"],
                        "Verificado em": c["date_checked"],
                        "Fonte": c["source"]
                    })

                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True
                )

                for c in comparisons[:5]:
                    if c["saving_year"] is None:
                        continue

                    with st.expander(
                        f"{c['provider_name']} — {c['plan_name']}"
                    ):
                        st.write(
                            f"**Poupança anual estimada:** "
                            f"{c['saving_year']:.2f} €"
                        )
                        st.caption(
                            f"Método de comparação: "
                            f"{c['comparison_method']}"
                        )
                        if c["conditions"]:
                            st.write(c["conditions"])
                        if c["date_checked"]:
                            st.caption(
                                f"Dados verificados em {c['date_checked']}"
                            )

    with tabs[2]:
        st.subheader("Ofertas de mercado")

        providers = list_market_providers(active_only=False)

        if providers:
            provider_map = {
                p["name"] + " | " + p["service_type"]: p["id"]
                for p in providers
                if p["is_active"]
            }

            with st.form("new_market_offer"):
                provider_label = st.selectbox(
                    "Fornecedor",
                    list(provider_map.keys())
                )
                plan_name = st.text_input("Nome do plano")
                monthly_price = st.number_input(
                    "Preço mensal (€)",
                    min_value=0.0,
                    value=0.0,
                    step=1.0
                )
                c1,c2 = st.columns(2)
                unit_price = c1.number_input(
                    "Preço unitário (€)",
                    min_value=0.0,
                    value=0.0,
                    step=0.001,
                    format="%.6f"
                )
                daily_price = c2.number_input(
                    "Preço diário (€)",
                    min_value=0.0,
                    value=0.0,
                    step=0.001,
                    format="%.6f"
                )
                contract_months = st.number_input(
                    "Fidelização (meses)",
                    min_value=0,
                    value=0,
                    step=1
                )
                conditions = st.text_area("Condições")
                source = st.text_input("Fonte")
                source_url = st.text_input("URL da fonte")
                checked = st.date_input(
                    "Data de verificação",
                    value=date.today()
                )
                submit_offer = st.form_submit_button("Adicionar oferta")

            if submit_offer:
                if not plan_name.strip():
                    st.error("Indica o nome do plano.")
                else:
                    create_market_offer(
                        provider_map[provider_label],
                        plan_name.strip(),
                        monthly_price or None,
                        unit_price or None,
                        daily_price or None,
                        int(contract_months) or None,
                        conditions.strip() or None,
                        source.strip() or None,
                        source_url.strip() or None,
                        checked
                    )
                    st.success("Oferta adicionada.")
                    st.rerun()
        else:
            st.info("Cria primeiro um fornecedor.")

        offers = list_market_offers(active_only=False)

        if offers:
            st.dataframe(
                pd.DataFrame([
                    {
                        "ID": o["id"],
                        "Serviço": o["service_type"],
                        "Fornecedor": o["provider_name"],
                        "Plano": o["plan_name"],
                        "Mensal (€)": float(o["monthly_price"]) if o["monthly_price"] is not None else None,
                        "Unitário (€)": float(o["unit_price"]) if o["unit_price"] is not None else None,
                        "Diário (€)": float(o["daily_price"]) if o["daily_price"] is not None else None,
                        "Verificado": o["date_checked"],
                        "Válida até": o.get("valid_until"),
                        "Ativa": bool(o["is_active"])
                    }
                    for o in offers
                ]),
                use_container_width=True,
                hide_index=True
            )

    with tabs[5]:
        st.subheader("Fornecedores de mercado")

        with st.form("new_market_provider"):
            provider_name = st.text_input("Nome do fornecedor")
            service_type = st.selectbox(
                "Tipo de serviço",
                service_types,
                key="provider_service_type"
            )
            website = st.text_input("Website")
            notes = st.text_area("Notas", key="provider_notes")
            submit_provider = st.form_submit_button("Adicionar fornecedor")

        if submit_provider:
            if not provider_name.strip():
                st.error("Indica o nome do fornecedor.")
            else:
                create_market_provider(
                    provider_name.strip(),
                    service_type,
                    website.strip() or None,
                    notes.strip() or None
                )
                st.success("Fornecedor criado.")
                st.rerun()

        providers = list_market_providers(active_only=False)

        if providers:
            st.dataframe(
                pd.DataFrame([
                    {
                        "ID": p["id"],
                        "Fornecedor": p["name"],
                        "Serviço": p["service_type"],
                        "Website": p["website"],
                        "Ativo": bool(p["is_active"])
                    }
                    for p in providers
                ]),
                use_container_width=True,
                hide_index=True
            )

    st.divider()
    st.info(
        "Nesta V2.3 os dados de mercado são introduzidos e verificados "
        "manualmente. A estrutura já guarda fonte, URL e data de verificação, "
        "preparando a recolha automática da V2.4."
    )



def page_contracts():
    household_id = require_household()

    st.title("📑 Inteligência de Contratos")
    st.caption("V2.6 — extrair termos, calcular custo de saída e decidir quando mudar")

    tabs = st.tabs(["Contratos", "Mudar agora vs esperar", "Prioridades"])

    with tabs[0]:
        services = list_household_services(household_id)
        if not services:
            st.info("Regista primeiro os serviços atuais em Mercado.")
        else:
            labels = {
                s["id"]: f"{s['service_type']} — {s['provider_name']}"
                for s in services
            }
            sid = st.selectbox(
                "Serviço",
                list(labels.keys()),
                format_func=lambda x: labels[x],
                key="contract_service"
            )
            service = next(s for s in services if s["id"] == sid)
            intel = get_contract_intelligence(sid, household_id) or {}

            linked_docs = [
                d for d in list_documents(household_id)
                if (get_document_service_link(d["id"], household_id) or {}).get("household_service_id") == sid
            ]

            if linked_docs:
                doc_labels = {d["id"]: d["original_filename"] for d in linked_docs}
                doc_id = st.selectbox(
                    "Contrato/fatura associado",
                    list(doc_labels.keys()),
                    format_func=lambda x: doc_labels[x]
                )
                if st.button("Extrair termos do documento", use_container_width=True):
                    terms = extract_contract_terms_from_document(doc_id, household_id)
                    st.session_state["contract_terms_preview"] = terms
            else:
                doc_id = None
                st.info("Não existem documentos associados a este serviço.")

            preview = st.session_state.get("contract_terms_preview") or {}
            if preview:
                st.info(
                    f"Extração sugerida — confiança {float(preview.get('confidence') or 0):.0f}%. "
                    "Confirma os dados antes de guardar."
                )

            c1,c2,c3 = st.columns(3)
            commitment = c1.number_input(
                "Fidelização (meses)",
                min_value=0,
                value=int(preview.get("commitment_months") or intel.get("commitment_months") or 0)
            )
            notice_days = c2.number_input(
                "Pré-aviso (dias)",
                min_value=0,
                value=int(preview.get("notice_days") or intel.get("notice_days") or 0)
            )
            exit_fee = c3.number_input(
                "Penalização de saída (€)",
                min_value=0.0,
                value=float(preview.get("early_exit_fee") or intel.get("early_exit_fee") or 0),
                step=5.0
            )

            renewal = st.selectbox(
                "Renovação",
                ["unknown","automatic","manual","none"],
                index=["unknown","automatic","manual","none"].index(
                    preview.get("renewal_type") or intel.get("renewal_type") or "unknown"
                )
            )

            extracted_fidelity = preview.get("extracted_fidelity_end") or intel.get("extracted_fidelity_end")
            has_fidelity = st.checkbox(
                "Guardar fim de fidelização extraído",
                value=bool(extracted_fidelity)
            )
            fidelity_date = st.date_input(
                "Fim da fidelização",
                value=extracted_fidelity or service.get("fidelity_end_date") or date.today(),
                disabled=not has_fidelity
            )

            if st.button("Guardar inteligência do contrato", use_container_width=True):
                save_contract_intelligence(
                    sid, household_id, doc_id,
                    commitment or None, renewal, notice_days or None,
                    exit_fee or None, None,
                    fidelity_date if has_fidelity else None,
                    preview.get("confidence") or intel.get("extraction_confidence"),
                    "Confirmado pelo utilizador na V2.6"
                )
                st.success("Dados contratuais guardados.")
                st.session_state.pop("contract_terms_preview", None)
                st.rerun()

    with tabs[1]:
        decisions = [d for d in list_switch_decisions(household_id) if d]
        if not decisions:
            st.info("Sem serviços suficientes para simular.")
        for d in decisions:
            srv = d["service"]
            with st.container(border=True):
                st.write(f"**{srv['service_type']} — {srv['provider_name']}**")
                if not d.get("best_offer"):
                    st.caption(d["reason"])
                    continue

                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Poupa/mês", f"{d['monthly_saving']:.2f} €")
                c2.metric("Custo de saída", f"{d['switch_cost']:.2f} €")
                c3.metric(
                    "Break-even",
                    f"{d['break_even_months']:.1f} meses" if d["break_even_months"] is not None else "—"
                )
                c4.metric("Poupança líquida 12m", f"{d['net_12m_saving']:.2f} €")

                if d["recommendation"] == "switch_now":
                    st.success("Recomendação: **mudar agora**")
                else:
                    st.warning("Recomendação: **esperar**")

                st.write(d["reason"])
                if d.get("ideal_switch_date"):
                    st.caption(f"Data sugerida para mudança: {d['ideal_switch_date']}")

    with tabs[2]:
        actions = get_financial_action_priorities(household_id)
        if not actions:
            st.info("Ainda não existem ações prioritárias calculáveis.")
        else:
            for idx, action in enumerate(actions[:10], start=1):
                with st.container(border=True):
                    c1,c2 = st.columns([1,4])
                    c1.metric("Prioridade", f"{action['priority']}/100")
                    c2.write(f"**{idx}. {action['title']}**")
                    c2.caption(action["reason"])
                    st.write(f"Impacto anual estimado: **{action['impact_year']:.2f} €**")



def page_financial_assistant():
    household_id = require_household()

    st.title("🤖 Assistente Financeiro Familiar")
    st.caption(
        "V2.7 — resumo mensal, explicação de variações, riscos e ações prioritárias"
    )

    today = date.today()

    c1,c2 = st.columns(2)
    year = c1.selectbox(
        "Ano",
        list(range(today.year-2,today.year+2)),
        index=2,
        key="assistant_year"
    )
    month = c2.selectbox(
        "Mês",
        list(range(1,13)),
        index=today.month-1,
        format_func=lambda x: MONTHS_PT[x],
        key="assistant_month"
    )

    narrative, snapshot = build_monthly_financial_narrative(
        household_id,
        year,
        month
    )
    actions = generate_next_month_actions(
        household_id,
        year,
        month,
        5
    )

    if st.button(
        "Guardar / atualizar resumo mensal",
        use_container_width=True
    ):
        save_monthly_financial_brief(
            household_id,
            year,
            month
        )
        st.success("Resumo mensal guardado.")
        st.rerun()

    st.subheader("Resumo do mês")
    st.write(narrative)

    summary = snapshot["summary"]
    risk = snapshot["risk"]
    market = snapshot["market"]

    m1,m2,m3,m4 = st.columns(4)
    m1.metric(
        "Rendimentos",
        f"{float(summary.get('income') or 0):.2f} €"
    )
    m2.metric(
        "Despesas",
        f"{float(summary.get('expense') or 0):.2f} €"
    )
    m3.metric(
        "Saldo",
        f"{float(summary.get('balance') or 0):.2f} €"
    )
    m4.metric(
        "Risco",
        f"{float(risk['score']):.0f}/100"
    )

    st.divider()
    st.subheader("Onde mudaram as despesas")

    changes = snapshot["category_changes"]
    if not changes:
        st.info("Sem comparação suficiente entre categorias.")
    else:
        df = pd.DataFrame([
            {
                "Categoria": c["category_name"],
                "Atual (€)": c["current_total"],
                "Anterior (€)": c["previous_total"],
                "Diferença (€)": c["difference"],
                "Diferença (%)": c["difference_pct"],
            }
            for c in changes
        ])

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

    st.divider()
    st.subheader("Riscos e desvios")

    if risk["reasons"]:
        for reason in risk["reasons"]:
            st.write(f"• {reason}")
    else:
        st.success("Não foram identificados fatores relevantes de risco.")

    if snapshot["anomalies"]:
        for anomaly in snapshot["anomalies"][:3]:
            st.warning(
                f"{anomaly['category_name']}: "
                f"{anomaly['deviation_pct']:.1f}% acima da média recente."
            )

    st.divider()
    st.subheader("Poupança potencial")

    p1,p2 = st.columns(2)
    p1.metric(
        "Mercado / mês",
        f"{market['potential_monthly_saving']:.2f} €"
    )
    p2.metric(
        "Mercado / ano",
        f"{market['potential_annual_saving']:.2f} €"
    )

    st.divider()
    st.subheader("Top ações para o próximo mês")

    if not actions:
        st.info("Ainda não existem ações prioritárias suficientes.")
    else:
        for action in actions:
            with st.container(border=True):
                a1,a2 = st.columns([1,5])
                a1.metric(
                    f"#{action['rank']}",
                    f"{action['priority']}/100"
                )
                a2.write(f"**{action['title']}**")
                a2.write(action["reason"])

                if action["impact_year"] > 0:
                    a2.caption(
                        f"Impacto anual estimado: "
                        f"{action['impact_year']:.2f} €"
                    )

    st.divider()
    st.subheader("Histórico de resumos")

    briefs = list_monthly_financial_briefs(
        household_id,
        12
    )

    if not briefs:
        st.info("Ainda não existem resumos mensais guardados.")
    else:
        for brief in briefs:
            label = (
                f"{MONTHS_PT[int(brief['month_num'])]} "
                f"{brief['year_num']}"
            )
            with st.expander(label):
                st.write(brief["narrative"])


def page_financial_plan():
    household_id=require_household()
    st.title("🎯 Plano Financeiro Familiar")
    st.caption("V2.8 — metas, limites recomendados, acompanhamento semanal e desafios")
    today=date.today()
    c1,c2=st.columns(2)
    year=c1.selectbox("Ano",list(range(today.year-2,today.year+2)),index=2,key="plan_year")
    month=c2.selectbox("Mês",list(range(1,13)),index=today.month-1,format_func=lambda x:MONTHS_PT[x],key="plan_month")
    tabs=st.tabs(["Plano mensal","Limites por categoria","Semanas","Desafios"])
    with tabs[0]:
        plan=calculate_monthly_plan(household_id,year,month)
        p1,p2,p3,p4=st.columns(4)
        p1.metric("Rendimento",f"{plan['income']:.2f} €")
        p2.metric("Meta de poupança",f"{plan['target_saving']:.2f} €")
        p3.metric("Teto de despesa",f"{plan['spend_cap']:.2f} €")
        p4.metric("Limite semanal",f"{plan['weekly_cap']:.2f} €")
        st.info(f"Meta sugerida: poupar {plan['target_savings_rate']:.1f}% do rendimento, ajustada ao risco financeiro atual.")
        if st.button("Guardar / atualizar plano mensal",use_container_width=True):
            save_monthly_financial_plan(household_id,year,month); st.success("Plano mensal guardado."); st.rerun()
        st.subheader("Ações recomendadas")
        if plan['actions']:
            for action in plan['actions']:
                with st.container(border=True): st.write(f"**{action['title']}**"); st.caption(action['reason'])
        else: st.info("Sem ações prioritárias suficientes.")
    with tabs[1]:
        limits=get_recommended_category_limits(household_id,year,month,3)
        if not limits: st.info("Ainda não existe histórico suficiente.")
        else:
            st.dataframe(pd.DataFrame([{'Categoria':x['category_name'],'Média histórica (€)':x['historical_average'],'Limite recomendado (€)':x['recommended_limit'],'Meses usados':x['months_considered']} for x in limits]),use_container_width=True,hide_index=True)
            st.caption("O limite recomendado corresponde a cerca de 95% da média histórica recente.")
    with tabs[2]:
        weeks=get_weekly_spending_status(household_id,year,month); plan=calculate_monthly_plan(household_id,year,month)
        if not weeks: st.info("Sem movimentos para este período.")
        else:
            cap=float(plan['weekly_cap'] or 0)
            df=pd.DataFrame([{'Semana':w['week_num'],'Início':w['week_start'],'Fim':w['week_end'],'Despesa (€)':w['total'],'Limite (€)':round(cap,2),'Diferença (€)':round(cap-w['total'],2)} for w in weeks])
            st.dataframe(df,use_container_width=True,hide_index=True); st.line_chart(df.set_index('Semana')[["Despesa (€)","Limite (€)"]])
    with tabs[3]:
        categories=get_expense_categories(); cat_map={c['id']:c['name'] for c in categories}
        with st.form('new_savings_challenge'):
            title=st.text_input('Nome do desafio',placeholder='Ex.: Poupar 100 € em restauração'); target=st.number_input('Meta (€)',min_value=1.0,value=100.0,step=10.0)
            start=st.date_input('Data de início',value=date.today()); end=st.date_input('Data de fim',value=date.today()+timedelta(days=30))
            opts=[0]+list(cat_map.keys()); cat=st.selectbox('Categoria opcional',opts,format_func=lambda x:'Objetivo geral' if x==0 else cat_map[x]); notes=st.text_area('Notas'); submit=st.form_submit_button('Criar desafio')
        if submit:
            if not title.strip(): st.error('Indica um nome para o desafio.')
            elif end<start: st.error('A data de fim deve ser posterior à data de início.')
            else:
                create_savings_challenge(household_id,title.strip(),target,start,end,cat if cat else None,notes.strip() or None); st.success('Desafio criado.'); st.rerun()
        challenges=list_savings_challenges(household_id)
        if not challenges: st.info('Ainda não existem desafios.')
        else:
            for challenge in challenges:
                progress=calculate_challenge_progress(challenge,household_id)
                with st.container(border=True):
                    st.write(f"**{challenge['title']}**"); st.caption(f"{challenge['start_date']} → {challenge['end_date']}")
                    if challenge['category_name']: st.caption(f"Categoria: {challenge['category_name']}")
                    st.progress(min(1.0,max(0.0,progress['progress_pct']/100))); st.write(f"Progresso: {progress['progress_pct']:.1f}% | Meta: {progress['target']:.2f} €")
                    if challenge['status']=='active':
                        cc1,cc2=st.columns(2)
                        if cc1.button('Concluir',key=f"done_{challenge['id']}"): update_savings_challenge_status(challenge['id'],household_id,'completed'); st.rerun()
                        if cc2.button('Cancelar',key=f"cancel_{challenge['id']}"): update_savings_challenge_status(challenge['id'],household_id,'cancelled'); st.rerun()


def page_financial_habits():
    household_id=require_household()
    st.title("🧠 Hábitos e Alertas Inteligentes")
    st.caption("V2.9 — deteção de padrões, ritmo de despesa e intervenção preventiva")
    today=date.today()
    c1,c2=st.columns(2)
    year=c1.selectbox("Ano",list(range(today.year-2,today.year+2)),index=2,key="habit_year")
    month=c2.selectbox("Mês",list(range(1,13)),index=today.month-1,format_func=lambda x:MONTHS_PT[x],key="habit_month")
    tabs=st.tabs(["Hábitos","Alertas inteligentes","Definições","Histórico"])
    with tabs[0]:
        habits=detect_financial_habits(household_id,year,month)
        if st.button("Atualizar análise de hábitos",use_container_width=True):
            save_financial_habit_snapshot(household_id,year,month,habits); st.success("Análise guardada.")
        if not habits: st.info("Ainda não existem dados suficientes para identificar hábitos relevantes.")
        for h in habits:
            with st.container(border=True):
                a,b=st.columns([1,4]); a.metric("Score",f"{float(h['score']):.0f}/100")
                b.write(f"**{h['title']}**"); b.write(h['description']); b.caption("Sugestão: "+h['suggestion'])
                if float(h.get('impact') or 0)>0: b.caption(f"Valor associado: {float(h['impact']):.2f} €")
    with tabs[1]:
        if st.button("Recalcular alertas agora",use_container_width=True):
            n=refresh_smart_financial_alerts(household_id); st.success(f"{n} novo(s) alerta(s)."); st.rerun()
        alerts=list_smart_financial_alerts(household_id,None,100)
        if not alerts: st.success("Sem alertas inteligentes.")
        for al in alerts:
            with st.container(border=True):
                badge={"critical":"🔴","high":"🟠","warning":"🟡","info":"🔵"}.get(al['severity'],"🔵")
                st.write(f"{badge} **{al['title']}**"); st.write(al['message'])
                if al.get('action_text'): st.info(al['action_text'])
                st.caption(f"Origem: {al['source_type']} | Estado: {al['status']}")
                if al['status']=='new':
                    x,y=st.columns(2)
                    if x.button("Marcar visto",key=f"seen_{al['id']}"): update_smart_financial_alert_status(al['id'],household_id,'seen'); st.rerun()
                    if y.button("Ignorar",key=f"dismiss_{al['id']}"): update_smart_financial_alert_status(al['id'],household_id,'dismissed'); st.rerun()
    with tabs[2]:
        cfg=get_smart_notification_settings(household_id)
        with st.form("smart_settings"):
            enabled=st.checkbox("Ativar alertas inteligentes",value=bool(cfg.get('smart_alerts_enabled',1)))
            email=st.checkbox("Enviar por email",value=bool(cfg.get('email_smart_alerts',1)))
            pace=st.number_input("Ritmo de despesa (%)",100.0,200.0,float(cfg.get('weekly_pace_warning_pct') or 110),5.0)
            cat=st.number_input("Limite da categoria (%)",80.0,200.0,float(cfg.get('category_limit_warning_pct') or 100),5.0)
            days=st.number_input("Avisar desafio a terminar (dias)",1,30,int(cfg.get('challenge_warning_days') or 7))
            score=st.number_input("Score mínimo do hábito",0.0,100.0,float(cfg.get('habit_min_score') or 60),5.0)
            save=st.form_submit_button("Guardar definições",use_container_width=True)
        if save: save_smart_notification_settings(household_id,enabled,email,pace,cat,days,score); st.success("Definições guardadas."); st.rerun()
        st.caption("O email usa a configuração SMTP já existente na página Notificações.")
    with tabs[3]:
        rows=list_financial_habit_snapshots(household_id,12)
        if not rows: st.info("Ainda não existem snapshots guardados.")
        for row in rows:
            with st.expander(f"{MONTHS_PT[int(row['month_num'])]} {row['year_num']}"):
                try: items=json.loads(row['habits_json'] or '[]')
                except Exception: items=[]
                if not items: st.caption("Sem hábitos relevantes registados.")
                for h in items: st.write(f"• **{h.get('title','Hábito')}** — {h.get('description','')}")

def page_notifications():
    household_id = require_household()

    st.title("🔔 Notificações e Contratos")
    st.caption(
        "V2.5 — email, fidelização, aumentos de preço e ligação documento-serviço"
    )

    tabs = st.tabs([
        "Definições",
        "Alertas",
        "Documentos ↔ Serviços",
        "Histórico de preços"
    ])

    with tabs[0]:
        st.subheader("Definições de email")

        settings = list_notification_settings(household_id)
        default_email = get_household_primary_email(household_id) or ""

        email_enabled = st.checkbox(
            "Ativar notificações por email",
            value=bool(settings["email_enabled"]) if settings else False
        )
        email_to = st.text_input(
            "Email de destino",
            value=(settings["email_to"] if settings and settings["email_to"] else default_email)
        )

        c1,c2,c3 = st.columns(3)
        notify_market = c1.checkbox(
            "Melhores ofertas",
            value=bool(settings["notify_market_better_offer"]) if settings else True
        )
        notify_contract = c2.checkbox(
            "Fim de fidelização",
            value=bool(settings["notify_contract_end"]) if settings else True
        )
        notify_price = c3.checkbox(
            "Aumentos de preço",
            value=bool(settings["notify_price_increase"]) if settings else True
        )

        c1,c2,c3 = st.columns(3)
        warning_days = c1.number_input(
            "Avisar antes do fim de contrato (dias)",
            min_value=1,
            value=int(settings["contract_warning_days"]) if settings else 30
        )
        min_saving = c2.number_input(
            "Poupança anual mínima para alerta (€)",
            min_value=0.0,
            value=float(settings["minimum_market_annual_saving"]) if settings else 60.0,
            step=10.0
        )
        min_increase = c3.number_input(
            "Aumento mínimo para alerta (%)",
            min_value=0.0,
            value=float(settings["minimum_price_increase_pct"]) if settings else 5.0,
            step=1.0
        )

        if st.button("Guardar definições", use_container_width=True):
            save_notification_settings(
                household_id,
                email_enabled,
                email_to.strip() or None,
                notify_market,
                notify_contract,
                notify_price,
                int(warning_days),
                min_saving,
                min_increase
            )
            st.success("Definições guardadas.")
            st.rerun()

        st.info(
            "O envio usa SMTP configurado no `.env`. "
            "Os emails pendentes são enviados pelo timer `family-finance-email.timer`."
        )

    with tabs[1]:
        st.subheader("Alertas ativos")

        if st.button("Atualizar todos os alertas agora", use_container_width=True):
            settings = list_notification_settings(household_id) or {}
            market_min = float(
                settings.get("minimum_market_annual_saving") or 60
            )

            m = refresh_market_alerts(
                household_id,
                minimum_annual_saving=market_min
            )
            c = refresh_contract_alerts(household_id)
            p = refresh_price_increase_alerts(household_id)
            q = queue_household_alert_emails(household_id)

            st.success(
                f"Atualização concluída: mercado={m}, contratos={c}, "
                f"preços={p}, emails em fila={q}."
            )
            st.rerun()

        market_alerts = list_market_alerts(household_id, status=None)
        service_alerts = list_service_alerts(household_id, status=None)

        if not market_alerts and not service_alerts:
            st.info("Sem alertas neste momento.")

        for alert in market_alerts:
            with st.container(border=True):
                st.write("**Melhor oferta de mercado**")
                st.write(alert["message"])
                st.caption(
                    f"{alert['service_type']} • "
                    f"{alert['current_provider']} → {alert['alternative_provider']}"
                )
                st.metric(
                    "Poupança anual",
                    f"{float(alert['potential_annual_saving'] or 0):.2f} €"
                )

        for alert in service_alerts:
            with st.container(border=True):
                st.write(f"**{alert['title']}**")
                st.write(alert["message"])
                st.caption(
                    f"{alert['service_type']} • {alert['provider_name']}"
                )

                if alert["status"] == "new":
                    c1,c2 = st.columns(2)
                    if c1.button(
                        "Marcar como visto",
                        key=f"svc_seen_{alert['id']}"
                    ):
                        update_service_alert_status(
                            alert["id"],
                            household_id,
                            "seen"
                        )
                        st.rerun()

                    if c2.button(
                        "Ignorar",
                        key=f"svc_dismiss_{alert['id']}"
                    ):
                        update_service_alert_status(
                            alert["id"],
                            household_id,
                            "dismissed"
                        )
                        st.rerun()

    with tabs[2]:
        st.subheader("Associar documentos a serviços")

        docs = list_unlinked_service_documents(
            household_id,
            100
        )
        services = list_household_services(household_id)

        if not docs:
            st.success("Todos os documentos elegíveis já estão associados.")
        elif not services:
            st.info(
                "Ainda não existem serviços do agregado. "
                "Cria-os primeiro em Mercado → Os meus serviços."
            )
        else:
            service_labels = {
                s["id"]: (
                    f"{s['service_type']} — {s['provider_name']}"
                    + (f" — {s['plan_name']}" if s["plan_name"] else "")
                )
                for s in services
            }

            for doc in docs:
                suggestion = suggest_document_service_link(
                    doc["id"],
                    household_id
                )

                with st.container(border=True):
                    st.write(f"**{doc['original_filename']}**")
                    st.caption(
                        f"Fornecedor detetado: "
                        f"{doc['extracted_supplier'] or '—'}"
                    )

                    if suggestion:
                        st.info(
                            f"Tipo sugerido: {suggestion['service_type']} | "
                            f"Confiança: {suggestion['confidence']:.0f}%"
                        )

                    default_service_id = (
                        suggestion["suggested_service_id"]
                        if suggestion and suggestion["suggested_service_id"] in service_labels
                        else next(iter(service_labels.keys()))
                    )

                    service_ids = list(service_labels.keys())
                    default_index = service_ids.index(default_service_id)

                    selected_service_id = st.selectbox(
                        "Serviço",
                        service_ids,
                        index=default_index,
                        format_func=lambda x: service_labels[x],
                        key=f"doc_service_{doc['id']}"
                    )

                    if st.button(
                        "Associar",
                        key=f"link_doc_{doc['id']}"
                    ):
                        confidence = (
                            suggestion["confidence"]
                            if suggestion and selected_service_id == suggestion["suggested_service_id"]
                            else 100
                        )
                        method = (
                            "suggested"
                            if suggestion and selected_service_id == suggestion["suggested_service_id"]
                            else "manual"
                        )
                        link_document_to_service(
                            doc["id"],
                            household_id,
                            selected_service_id,
                            confidence,
                            method
                        )
                        st.success("Documento associado.")
                        st.rerun()

    with tabs[3]:
        st.subheader("Histórico de preços dos serviços")

        services = list_household_services(household_id)

        if not services:
            st.info("Sem serviços registados.")
        else:
            labels = {
                s["id"]: f"{s['service_type']} — {s['provider_name']}"
                for s in services
            }

            service_id = st.selectbox(
                "Serviço",
                list(labels.keys()),
                format_func=lambda x: labels[x],
                key="price_history_service"
            )

            history = list_household_service_price_history(
                service_id,
                household_id,
                24
            )

            if not history:
                st.info("Ainda não existe histórico de preço.")
            else:
                hdf = pd.DataFrame([
                    {
                        "Data": h["observed_at"],
                        "Mensal (€)": float(h["monthly_cost"]) if h["monthly_cost"] is not None else None,
                        "Unitário (€)": float(h["unit_price"]) if h["unit_price"] is not None else None,
                        "Diário (€)": float(h["daily_price"]) if h["daily_price"] is not None else None,
                        "Fonte": h["source"]
                    }
                    for h in history
                ])

                st.dataframe(
                    hdf,
                    use_container_width=True,
                    hide_index=True
                )

                chart_df = hdf.dropna(subset=["Mensal (€)"])
                if not chart_df.empty:
                    st.line_chart(
                        chart_df.set_index("Data")[["Mensal (€)"]]
                    )


def page_profile():
    require_login()
    u = st.session_state.user
    st.title("👤 O meu perfil")
    a,b = st.columns(2)
    with a:
        st.text_input("Nome",u["full_name"],disabled=True)
        st.text_input("Utilizador",u["username"],disabled=True)
        st.text_input("Email",u["email"] or "",disabled=True)
    with b:
        st.text_input("Perfil","Administrador" if u["role"]=="admin" else "Utilizador",disabled=True)
        st.text_input("Agregado",u.get("household_name") or "Não definido",disabled=True)
    st.divider()
    st.subheader("Alterar palavra-passe")
    with st.form("pwd"):
        current = st.text_input("Palavra-passe atual",type="password")
        new = st.text_input("Nova palavra-passe",type="password")
        confirm = st.text_input("Confirmar nova palavra-passe",type="password")
        submit = st.form_submit_button("Alterar palavra-passe")
    if submit:
        if new != confirm:
            st.error("As novas palavras-passe não coincidem.")
        else:
            ok,msg = change_password(u["id"],current,new)
            st.success(msg) if ok else st.error(msg)

def page_users():
    require_admin()
    st.title("👥 Gestão de utilizadores")
    households = list_households()
    opts = {"Sem agregado":None, **{h["name"]:h["id"] for h in households}}
    with st.expander("Criar novo utilizador"):
        with st.form("newuser"):
            full_name = st.text_input("Nome completo")
            username = st.text_input("Utilizador")
            email = st.text_input("Email")
            password = st.text_input("Palavra-passe temporária",type="password")
            role_label = st.selectbox("Perfil",["Utilizador","Administrador"])
            household_label = st.selectbox("Agregado",list(opts.keys()))
            submit = st.form_submit_button("Criar utilizador")
        if submit:
            if not full_name or not username or not password:
                st.error("Nome, utilizador e palavra-passe são obrigatórios.")
            elif len(password)<8:
                st.error("A palavra-passe deve ter pelo menos 8 caracteres.")
            else:
                try:
                    uid = create_user(
                        username.strip(), full_name.strip(), email.strip() or None,
                        hash_password(password),
                        "admin" if role_label=="Administrador" else "user",
                        opts[household_label]
                    )
                    log_action(st.session_state.user["id"],"create_user","user",uid,username)
                    st.success("Utilizador criado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    users = list_users()
    if users:
        df = pd.DataFrame(users)
        df["role"] = df["role"].map({"admin":"Administrador","user":"Utilizador"})
        df["is_active"] = df["is_active"].map({1:"Sim",0:"Não",True:"Sim",False:"Não"})
        st.dataframe(df.rename(columns={
            "id":"ID","username":"Utilizador","full_name":"Nome","email":"Email",
            "role":"Perfil","is_active":"Ativo","last_login_at":"Último login",
            "household_name":"Agregado"
        }),use_container_width=True,hide_index=True)

        st.subheader("Ativar / desativar conta")
        selectable = {
            f"{u['full_name']} (@{u['username']})":u
            for u in users if u["id"] != st.session_state.user["id"]
        }
        if selectable:
            label = st.selectbox("Utilizador",list(selectable.keys()))
            selected = selectable[label]
            active = st.checkbox("Conta ativa",value=bool(selected["is_active"]))
            if st.button("Guardar estado"):
                set_user_active(selected["id"],active)
                st.success("Estado atualizado.")
                st.rerun()

def page_households():
    require_admin()
    st.title("🏡 Agregados familiares")
    with st.form("newhouse"):
        name = st.text_input("Nome do agregado")
        submit = st.form_submit_button("Criar agregado")
    if submit:
        if name.strip():
            hid = create_household(name.strip(),st.session_state.user["id"])
            log_action(st.session_state.user["id"],"create_household","household",hid,name)
            st.success("Agregado criado.")
            st.rerun()
        else:
            st.error("Indica um nome.")

    households = list_households()
    users = list_users()

    if households:
        st.dataframe(pd.DataFrame(households).rename(columns={"id":"ID","name":"Agregado"}),
                     use_container_width=True,hide_index=True)

    if households and users:
        st.subheader("Associar utilizador")
        uopts = {f"{u['full_name']} (@{u['username']})":u["id"] for u in users}
        hopts = {h["name"]:h["id"] for h in households}
        with st.form("assign"):
            ul = st.selectbox("Utilizador",list(uopts))
            hl = st.selectbox("Agregado",list(hopts))
            rl = st.selectbox("Papel no agregado",["Membro","Responsável"])
            submit2 = st.form_submit_button("Associar")
        if submit2:
            assign_user_to_household(uopts[ul],hopts[hl],"owner" if rl=="Responsável" else "member")
            st.success("Associação atualizada.")
            st.rerun()

def page_system():
    require_admin()

    st.title("🛠 Sistema")
    st.caption("Diagnóstico da aplicação, base de dados e ambiente de execução.")

    try:
        # --------------------------------------------------
        # Diagnóstico
        # --------------------------------------------------
        info = test_connection()
        stats = get_system_stats()
        db_environment = get_database_environment()

        version = str(info.get("version") or "")
        database_name = str(info.get("db_name") or "—")

        if "MariaDB" in version:
            database_engine = "MariaDB"
        elif version:
            database_engine = "MySQL"
        else:
            database_engine = "Desconhecido"

        if db_environment == "CLOUD":
            environment_icon = "☁️"
            environment_label = "CLOUD"
        else:
            environment_icon = "🖥️"
            environment_label = "LOCAL"

        # --------------------------------------------------
        # Estado da ligação
        # --------------------------------------------------
        st.success(
            f"✅ Base de dados ligada — "
            f"{environment_icon} **{environment_label}** | "
            f"**{database_engine}** | "
            f"BD: **{database_name}**"
        )

        # --------------------------------------------------
        # Informação principal
        # --------------------------------------------------
        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Ambiente",
            f"{environment_icon} {environment_label}"
        )

        c2.metric(
            "Motor BD",
            database_engine
        )

        c3.metric(
            "Base de dados",
            database_name
        )

        c4.metric(
            "Estado",
            "Online"
        )

        st.caption(f"Servidor de base de dados: {version}")

        st.divider()

        # --------------------------------------------------
        # Estatísticas
        # --------------------------------------------------
        st.subheader("📊 Estatísticas do sistema")

        a, b, c, d = st.columns(4)

        a.metric("Utilizadores", stats["users"])
        b.metric("Agregados", stats["households"])
        c.metric("Rendimentos", stats["incomes"])
        d.metric("Despesas", stats["expenses"])

        e, f, g, h = st.columns(4)

        e.metric("Documentos", stats["documents"])
        f.metric("Categorias", stats["categories"])
        g.metric("Configurações", stats["settings"])
        h.metric("Migrações", stats["migrations"])

        st.divider()

        # --------------------------------------------------
        # Categorias
        # --------------------------------------------------
        st.subheader("📁 Categorias")

        st.dataframe(
            pd.DataFrame(get_categories()),
            use_container_width=True,
            hide_index=True
        )

        # --------------------------------------------------
        # Informação técnica
        # --------------------------------------------------
        with st.expander("⚙️ Informação técnica"):

            st.code(
                f"""Aplicação: {APP_NAME}
Versão: 3.3.3
Ambiente da aplicação: {APP_ENV}
Ambiente da base de dados: {environment_label}
Motor da base de dados: {database_engine}
Base de dados: {database_name}
Servidor BD: {version}
Python: {platform.python_version()}
Sistema: {platform.system()} {platform.release()}
Data/Hora: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}"""
            )

            st.caption(
                "Por segurança, host, utilizador e credenciais da base de dados "
                "não são apresentados."
            )

    except Exception as e:

        st.error("❌ Erro de ligação à base de dados.")

        with st.expander("Detalhes técnicos"):
            st.code(str(e))


# ==========================================================
# FAMILY FINANCE V3.3.3
# Router principal da aplicação
# ==========================================================

if not st.session_state.get("authenticated", False):
    page_login()

else:
    p = sidebar()

    pages = {
        "Executivo": page_executive_dashboard,
        "Ações": page_financial_actions,
        "Dashboard": page_dashboard,
        "Rendimentos": page_incomes,
        "Despesas": page_expenses,
        "Documentos": page_documents,
        "Orçamentos": page_budgets,
        "Planeamento": page_planning,
        "Calendário": page_financial_calendar,
        "Cenários": page_scenarios,
        "Risco": page_risk,
        "Mercado": page_market,
        "Contratos": page_contracts,
        "Assistente": page_financial_assistant,
        "Plano": page_financial_plan,
        "Hábitos": page_financial_habits,
        "Notificações": page_notifications,
        "Metas": page_goals,
        "O meu perfil": page_profile,
        "Utilizadores": page_users,
        "Agregados": page_households,
        "Sistema": page_system,
    }

    page_function = pages.get(p)

    if page_function:
        page_function()
    else:
        st.error(f"Página desconhecida: {p}")
