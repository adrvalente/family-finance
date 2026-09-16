#!/usr/bin/env python3
import json
import sys
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from db import (
    add_market_offer_history,
    expire_old_market_offers,
    find_or_create_market_provider,
    list_market_sources,
    update_market_source_run,
    upsert_market_offer_from_source,
)

TIMEOUT = 20


def get_path(obj, path, default=None):
    if not path:
        return default

    cur = obj
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def as_float(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("€", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def collect_json(source, config):
    response = requests.get(source["endpoint_url"], timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    items_path = config.get("items_path")
    items = get_path(data, items_path, data)

    if isinstance(items, dict):
        items = [items]

    if not isinstance(items, list):
        raise ValueError("A fonte JSON não devolveu uma lista de ofertas.")

    mapping = config.get("mapping", {})
    result = []

    for item in items:
        result.append({
            "provider": get_path(item, mapping.get("provider")),
            "plan": get_path(item, mapping.get("plan")),
            "monthly_price": as_float(get_path(item, mapping.get("monthly_price"))),
            "unit_price": as_float(get_path(item, mapping.get("unit_price"))),
            "daily_price": as_float(get_path(item, mapping.get("daily_price"))),
            "contract_months": get_path(item, mapping.get("contract_months")),
            "conditions": get_path(item, mapping.get("conditions")),
            "source_url": get_path(item, mapping.get("source_url")) or source["endpoint_url"],
        })

    return result


def text_from_selector(soup, selector):
    if not selector:
        return None
    node = soup.select_one(selector)
    return node.get_text(" ", strip=True) if node else None


def collect_html(source, config):
    response = requests.get(
        source["endpoint_url"],
        timeout=TIMEOUT,
        headers={"User-Agent": "FamilyFinance/2.4"}
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    offer_selector = config.get("offer_selector")
    if not offer_selector:
        raise ValueError("Falta offer_selector na configuração HTML.")

    mapping = config.get("mapping", {})
    result = []

    for node in soup.select(offer_selector):
        def node_text(selector):
            if not selector:
                return None
            found = node.select_one(selector)
            return found.get_text(" ", strip=True) if found else None

        result.append({
            "provider": node_text(mapping.get("provider")),
            "plan": node_text(mapping.get("plan")),
            "monthly_price": as_float(node_text(mapping.get("monthly_price"))),
            "unit_price": as_float(node_text(mapping.get("unit_price"))),
            "daily_price": as_float(node_text(mapping.get("daily_price"))),
            "contract_months": node_text(mapping.get("contract_months")),
            "conditions": node_text(mapping.get("conditions")),
            "source_url": source["endpoint_url"],
        })

    return result


def process_source(source):
    try:
        config = json.loads(source["config_json"] or "{}")
        source_type = source["source_type"]

        if source_type == "json":
            offers = collect_json(source, config)
        elif source_type == "html":
            offers = collect_html(source, config)
        else:
            raise ValueError(f"source_type não suportado: {source_type}")

        validity_days = int(source["default_validity_days"] or 7)
        checked = date.today()
        valid_until = checked + timedelta(days=validity_days)

        inserted = 0

        for offer in offers:
            provider_name = (offer.get("provider") or "").strip()
            plan_name = (offer.get("plan") or "").strip()

            if not provider_name or not plan_name:
                continue

            provider_id = find_or_create_market_provider(
                provider_name,
                source["service_type"],
                offer.get("source_url")
            )

            offer_id = upsert_market_offer_from_source(
                source_id=source["id"],
                provider_id=provider_id,
                plan_name=plan_name,
                monthly_price=offer.get("monthly_price"),
                unit_price=offer.get("unit_price"),
                daily_price=offer.get("daily_price"),
                contract_months=offer.get("contract_months"),
                conditions=offer.get("conditions"),
                source=source["name"],
                source_url=offer.get("source_url"),
                date_checked=checked,
                valid_until=valid_until,
            )

            add_market_offer_history(
                offer_id=offer_id,
                monthly_price=offer.get("monthly_price"),
                unit_price=offer.get("unit_price"),
                daily_price=offer.get("daily_price"),
                date_checked=checked,
                source_id=source["id"],
            )

            inserted += 1

        update_market_source_run(
            source["id"],
            "ok",
            None
        )

        return {
            "source": source["name"],
            "status": "ok",
            "offers": inserted
        }

    except Exception as exc:
        update_market_source_run(
            source["id"],
            "error",
            str(exc)[:2000]
        )
        return {
            "source": source["name"],
            "status": "error",
            "error": str(exc)
        }


def main():
    expire_old_market_offers()
    sources = list_market_sources(active_only=True)

    results = [process_source(s) for s in sources]

    print(json.dumps(
        {
            "sources": len(sources),
            "results": results
        },
        ensure_ascii=False,
        default=str
    ))


if __name__ == "__main__":
    main()
