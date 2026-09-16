import json
import calendar
from datetime import date

from db import (
    fetch_one, fetch_all, execute,
    calculate_monthly_plan, get_monthly_expense_total,
    get_recommended_category_limits, list_savings_challenges,
    list_notification_settings, create_email_notification,
)


def get_smart_notification_settings(household_id):
    row = fetch_one("""
        SELECT * FROM household_smart_settings
        WHERE household_id=%s LIMIT 1
    """, (household_id,))
    if row:
        return row
    return {
        "household_id": household_id,
        "smart_alerts_enabled": 1,
        "email_smart_alerts": 1,
        "weekly_pace_warning_pct": 110.0,
        "category_limit_warning_pct": 100.0,
        "challenge_warning_days": 7,
        "habit_min_score": 60.0,
    }


def save_smart_notification_settings(
    household_id, smart_alerts_enabled=True, email_smart_alerts=True,
    weekly_pace_warning_pct=110, category_limit_warning_pct=100,
    challenge_warning_days=7, habit_min_score=60
):
    existing = fetch_one(
        "SELECT household_id FROM household_smart_settings WHERE household_id=%s",
        (household_id,)
    )
    values = (
        1 if smart_alerts_enabled else 0,
        1 if email_smart_alerts else 0,
        weekly_pace_warning_pct, category_limit_warning_pct,
        challenge_warning_days, habit_min_score, household_id
    )
    if existing:
        execute("""
            UPDATE household_smart_settings
            SET smart_alerts_enabled=%s,email_smart_alerts=%s,
                weekly_pace_warning_pct=%s,category_limit_warning_pct=%s,
                challenge_warning_days=%s,habit_min_score=%s,updated_at=NOW()
            WHERE household_id=%s
        """, values)
    else:
        execute("""
            INSERT INTO household_smart_settings(
                smart_alerts_enabled,email_smart_alerts,
                weekly_pace_warning_pct,category_limit_warning_pct,
                challenge_warning_days,habit_min_score,household_id
            ) VALUES(%s,%s,%s,%s,%s,%s,%s)
        """, values)


def detect_financial_habits(household_id, year, month):
    rows = fetch_all("""
        SELECT eo.occurrence_date,eo.amount,e.supplier,e.recurrence_type,
               c.id AS category_id,c.name AS category_name
        FROM expense_occurrences eo
        JOIN expenses e ON e.id=eo.expense_id
        JOIN categories c ON c.id=e.category_id
        WHERE eo.household_id=%s
          AND YEAR(eo.occurrence_date)=%s
          AND MONTH(eo.occurrence_date)=%s
          AND eo.is_active=1 AND e.is_active=1
        ORDER BY eo.occurrence_date
    """, (household_id,year,month))
    if not rows:
        return []

    total=sum(float(r['amount'] or 0) for r in rows)
    habits=[]

    weekend_total=sum(float(r['amount'] or 0) for r in rows if r['occurrence_date'].weekday()>=5)
    weekend_share=weekend_total/total*100 if total>0 else 0
    if weekend_share>=30:
        habits.append({
            'habit_key':'weekend_spending','title':'Despesa concentrada ao fim de semana',
            'description':f'{weekend_share:.1f}% da despesa mensal ocorreu ao sábado ou domingo.',
            'score':round(min(100,45+weekend_share),1),'impact':round(weekend_total,2),
            'suggestion':'Define um limite específico para lazer e compras de fim de semana.'
        })

    small=[r for r in rows if 0<float(r['amount'] or 0)<=15]
    small_total=sum(float(r['amount'] or 0) for r in small)
    if len(small)>=6 and small_total>=40:
        habits.append({
            'habit_key':'small_frequent_purchases','title':'Muitas pequenas compras',
            'description':f'Foram registadas {len(small)} compras até 15 €, num total de {small_total:.2f} €.',
            'score':round(min(100,45+len(small)*3),1),'impact':round(small_total,2),
            'suggestion':'Agrupa compras pequenas e acompanha um teto semanal para gastos ocasionais.'
        })

    by_supplier={}
    for r in rows:
        supplier=(r.get('supplier') or '').strip()
        if not supplier: continue
        x=by_supplier.setdefault(supplier,{'count':0,'total':0.0})
        x['count']+=1; x['total']+=float(r['amount'] or 0)
    for supplier,x in by_supplier.items():
        if x['count']>=4:
            habits.append({
                'habit_key':f'supplier_frequency:{supplier.lower()}',
                'title':f'Compras frequentes em {supplier}',
                'description':f"{x['count']} movimentos no mês, totalizando {x['total']:.2f} €.",
                'score':min(100,50+x['count']*5),'impact':round(x['total'],2),
                'suggestion':'Revê se parte destas compras pode ser planeada ou agrupada.'
            })

    by_category={}
    for r in rows:
        name=r['category_name']; by_category[name]=by_category.get(name,0)+float(r['amount'] or 0)
    if total>0 and by_category:
        name,value=max(by_category.items(),key=lambda x:x[1]); share=value/total*100
        if share>=35:
            habits.append({
                'habit_key':f'category_concentration:{name.lower()}','title':f'Forte concentração em {name}',
                'description':f'A categoria representa {share:.1f}% da despesa mensal ({value:.2f} €).',
                'score':min(100,45+share),'impact':round(value,2),
                'suggestion':'Confirma se esta concentração é esperada ou se existe margem de redução.'
            })

    recurring=sum(float(r['amount'] or 0) for r in rows if r.get('recurrence_type')=='recurring')
    recurring_share=recurring/total*100 if total>0 else 0
    if recurring_share>=65:
        habits.append({
            'habit_key':'high_fixed_commitments','title':'Peso elevado de despesas recorrentes',
            'description':f'{recurring_share:.1f}% da despesa está associada a compromissos recorrentes.',
            'score':min(100,40+recurring_share),'impact':round(recurring,2),
            'suggestion':'Revê contratos, subscrições e serviços fixos antes de cortar despesas essenciais.'
        })
    return sorted(habits,key=lambda x:(-float(x['score']),-float(x['impact'])))


def save_financial_habit_snapshot(household_id,year,month,habits=None):
    habits=habits if habits is not None else detect_financial_habits(household_id,year,month)
    payload=json.dumps(habits,ensure_ascii=False,default=str)
    row=fetch_one("SELECT id FROM financial_habit_snapshots WHERE household_id=%s AND year_num=%s AND month_num=%s LIMIT 1",(household_id,year,month))
    if row:
        execute("UPDATE financial_habit_snapshots SET habits_json=%s,updated_at=NOW() WHERE id=%s",(payload,row['id']))
        return row['id']
    return execute("INSERT INTO financial_habit_snapshots(household_id,year_num,month_num,habits_json) VALUES(%s,%s,%s,%s)",(household_id,year,month,payload))


def list_financial_habit_snapshots(household_id,limit_rows=12):
    return fetch_all("SELECT * FROM financial_habit_snapshots WHERE household_id=%s ORDER BY year_num DESC,month_num DESC LIMIT %s",(household_id,limit_rows))


def _upsert_alert(household_id,alert_key,period_key,severity,title,message,action_text,source_type,metric_value=None,threshold_value=None,expires_at=None):
    row=fetch_one("SELECT id,status FROM smart_financial_alerts WHERE household_id=%s AND alert_key=%s AND period_key=%s LIMIT 1",(household_id,alert_key,period_key))
    if row:
        execute("""UPDATE smart_financial_alerts SET severity=%s,title=%s,message=%s,action_text=%s,source_type=%s,metric_value=%s,threshold_value=%s,expires_at=%s,updated_at=NOW() WHERE id=%s""",(severity,title,message,action_text,source_type,metric_value,threshold_value,expires_at,row['id']))
        return False
    execute("""INSERT INTO smart_financial_alerts(household_id,alert_key,period_key,severity,title,message,action_text,source_type,metric_value,threshold_value,expires_at,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'new')""",(household_id,alert_key,period_key,severity,title,message,action_text,source_type,metric_value,threshold_value,expires_at))
    return True


def refresh_smart_financial_alerts(household_id,reference_date=None):
    reference_date=reference_date or date.today()
    settings=get_smart_notification_settings(household_id)
    if not settings.get('smart_alerts_enabled'): return 0
    year,month=reference_date.year,reference_date.month
    period=f'{year:04d}-{month:02d}'
    days=calendar.monthrange(year,month)[1]
    end=date(year,month,days)
    plan=calculate_monthly_plan(household_id,year,month)
    created=0

    actual=float(get_monthly_expense_total(household_id,year,month) or 0)
    cap=float(plan.get('spend_cap') or 0)
    expected=cap*(reference_date.day/days) if cap>0 else 0
    pace=actual/expected*100 if expected>0 else 0
    pace_limit=float(settings.get('weekly_pace_warning_pct') or 110)
    if expected>0 and pace>=pace_limit:
        created+=int(_upsert_alert(household_id,'spending_pace',period,'warning','Ritmo de despesa acima do plano',f'Até hoje foram gastos {actual:.2f} €, cerca de {pace:.0f}% do ritmo previsto para esta altura do mês.','Revê as despesas discricionárias desta semana e ajusta o plano antes do fim do mês.','spending_pace',actual,expected,end))

    projected=float(plan.get('projected_expense') or 0)
    if cap>0 and projected>cap:
        created+=int(_upsert_alert(household_id,'projected_over_cap',period,'high','Previsão acima do teto mensal',f'A despesa projetada é {projected:.2f} €, acima do teto de {cap:.2f} €.',f'Procura reduzir pelo menos {projected-cap:.2f} € no restante mês.','monthly_plan',projected,cap,end))

    threshold=float(settings.get('category_limit_warning_pct') or 100)
    current={int(r['category_id']):float(r['total'] or 0) for r in fetch_all("""SELECT e.category_id,SUM(eo.amount) AS total FROM expense_occurrences eo JOIN expenses e ON e.id=eo.expense_id WHERE eo.household_id=%s AND YEAR(eo.occurrence_date)=%s AND MONTH(eo.occurrence_date)=%s AND eo.is_active=1 AND e.is_active=1 GROUP BY e.category_id""",(household_id,year,month))}
    for lim in get_recommended_category_limits(household_id,year,month,3):
        lcap=float(lim['recommended_limit'] or 0); spent=current.get(int(lim['category_id']),0)
        pct=spent/lcap*100 if lcap>0 else 0
        if lcap>0 and pct>=threshold:
            severity='high' if pct>=120 else 'warning'
            created+=int(_upsert_alert(household_id,f"category_limit:{lim['category_id']}",period,severity,f"Limite recomendado atingido — {lim['category_name']}",f'A categoria está em {spent:.2f} € ({pct:.0f}% do limite recomendado de {lcap:.2f} €).','Reduz ou adia novas despesas desta categoria até ao próximo mês.','category_limit',spent,lcap,end))

    warning_days=int(settings.get('challenge_warning_days') or 7)
    for ch in list_savings_challenges(household_id,'active'):
        left=(ch['end_date']-reference_date).days
        if 0<=left<=warning_days:
            created+=int(_upsert_alert(household_id,f"challenge_end:{ch['id']}",period,'info',f"Desafio a terminar — {ch['title']}",f'Faltam {left} dia(s) para terminar este desafio.','Consulta o progresso e decide se precisas de ajustar a meta ou o comportamento desta semana.','savings_challenge',left,warning_days,ch['end_date']))

    habits=detect_financial_habits(household_id,year,month)
    save_financial_habit_snapshot(household_id,year,month,habits)
    min_score=float(settings.get('habit_min_score') or 60)
    for h in habits:
        if float(h['score'])>=min_score:
            created+=int(_upsert_alert(household_id,f"habit:{h['habit_key']}",period,'info',h['title'],h['description'],h['suggestion'],'financial_habit',h['score'],min_score,end))
    return created


def list_smart_financial_alerts(household_id,status=None,limit_rows=100):
    sql='SELECT * FROM smart_financial_alerts WHERE household_id=%s'; params=[household_id]
    if status: sql+=' AND status=%s'; params.append(status)
    sql+=" ORDER BY CASE severity WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'warning' THEN 2 ELSE 1 END DESC,created_at DESC LIMIT %s"; params.append(limit_rows)
    return fetch_all(sql,tuple(params))


def update_smart_financial_alert_status(alert_id,household_id,status):
    execute('UPDATE smart_financial_alerts SET status=%s,updated_at=NOW() WHERE id=%s AND household_id=%s',(status,alert_id,household_id))


def queue_smart_alert_emails(household_id):
    smart=get_smart_notification_settings(household_id)
    normal=list_notification_settings(household_id) or {}
    if not smart.get('email_smart_alerts') or not normal.get('email_enabled') or not normal.get('email_to'): return 0
    created=0
    for alert in list_smart_financial_alerts(household_id,'new',50):
        exists=fetch_one("SELECT id FROM email_notifications WHERE household_id=%s AND notification_type='smart_financial' AND related_alert_id=%s LIMIT 1",(household_id,alert['id']))
        if exists: continue
        body=alert['message']
        if alert.get('action_text'): body += '\n\nSugestão: '+alert['action_text']
        create_email_notification(household_id,'smart_financial',f"Family Finance — {alert['title']}",body,normal['email_to'],alert['id'])
        created+=1
    return created
