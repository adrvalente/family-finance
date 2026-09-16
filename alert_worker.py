#!/usr/bin/env python3
from db import (
    fetch_all,
    list_notification_settings,
    queue_household_alert_emails,
    refresh_contract_alerts,
    refresh_market_alerts,
    refresh_price_increase_alerts,
    refresh_smart_financial_alerts,
    queue_smart_alert_emails,
)

def main():
    households = fetch_all("""
        SELECT id
        FROM households
        ORDER BY id
    """)

    total_market = 0
    total_contract = 0
    total_price = 0
    total_emails = 0
    total_smart = 0
    total_smart_emails = 0

    for row in households:
        household_id = row["id"]
        settings = list_notification_settings(household_id) or {}

        market_min = float(
            settings.get("minimum_market_annual_saving") or 60
        )

        total_market += refresh_market_alerts(
            household_id,
            minimum_annual_saving=market_min
        )
        total_contract += refresh_contract_alerts(household_id)
        total_price += refresh_price_increase_alerts(household_id)
        total_smart += refresh_smart_financial_alerts(household_id)
        total_emails += queue_household_alert_emails(household_id)
        total_smart_emails += queue_smart_alert_emails(household_id)

    print(
        f"market={total_market} "
        f"contract={total_contract} "
        f"price={total_price} "
        f"smart={total_smart} "
        f"emails={total_emails} "
        f"smart_emails={total_smart_emails}"
    )

if __name__ == "__main__":
    main()
