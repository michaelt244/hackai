import asyncio
import json
import os

import httpx

BUTTERBASE_URL = os.environ.get("BUTTERBASE_URL", "")
BUTTERBASE_KEY = os.environ.get("BUTTERBASE_ANON_KEY", "")

INDIVIDUAL_BASELINE_COST = 0.5  # cents — baseline if everyone used a premium model

_headers = {
    "apikey": BUTTERBASE_KEY,
    "Authorization": f"Bearer {BUTTERBASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


async def record_cost(channel_id: str, cost_cents: float):
    if not BUTTERBASE_URL:
        return
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{BUTTERBASE_URL}/channel_usage",
            headers=_headers,
            json={"channel_id": channel_id, "cost_cents": cost_cents},
        )


async def save_contact(channel_id: str, contact_data: dict):
    if not BUTTERBASE_URL:
        return
    contact = contact_data.get("contact", {})
    payload = {"channel_id": channel_id}
    for col, val in {
        "name": contact.get("name"),
        "company": contact.get("company"),
        "role": contact.get("role"),
        "context": contact.get("context"),
        "action_items": json.dumps(contact_data.get("actionItems", [])),
        "sentiment": contact_data.get("sentiment"),
        "follow_up_date": contact_data.get("followUpDate"),
    }.items():
        if val is not None:
            payload[col] = val
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(f"{BUTTERBASE_URL}/contacts", headers=_headers, json=payload)


async def get_stats(channel_id: str) -> dict:
    if not BUTTERBASE_URL:
        return {"total_cost_cents": 0, "saved_cents": 0, "message_count": 0}
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{BUTTERBASE_URL}/channel_usage",
            headers={**_headers, "Accept": "application/json"},
            params={"channel_id": f"eq.{channel_id}", "select": "cost_cents"},
        )
    rows = resp.json()
    total = sum(r["cost_cents"] for r in rows)
    count = len(rows)
    saved = max(0, (count * INDIVIDUAL_BASELINE_COST) - total)
    return {
        "total_cost_cents": round(total, 2),
        "saved_cents": round(saved, 2),
        "message_count": count,
    }
