#!/usr/bin/env python3
"""Ollama integration for POS Bot — handles free-text queries via phi3:mini."""

import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5:1.5b"

# System prompt that gives the LLM full context about the POS platform
SYSTEM_PROMPT = """You are NexPOS AI — POS management assistant. Be concise (<100 words). Use markdown bold and bullets.

DATA:
{data_snapshot}

Rules: Answer from data above. For actions say "use the menu buttons". Be helpful and brief."""


def build_data_snapshot(devices, merchants, transactions, alerts):
    """Build a compact data snapshot for the system prompt."""
    lines = []

    lines.append("DEVICES:")
    for did, d in devices.items():
        lines.append(f"  {did}: {d['name']} @ {d['merchant']} ({d['region']}) — {d['status']}, Battery:{d['battery']}%")

    lines.append("\nMERCHANTS:")
    for mid, m in merchants.items():
        lines.append(f"  {mid}: {m['name']} ({m['category']}, {m['region']}) — {m['devices']} devices")

    lines.append("\nTODAY'S TRANSACTIONS:")
    for region, data in transactions.items():
        lines.append(f"  {region}: {data['count']} txns, ₹{data['volume']:,} volume")

    lines.append(f"\nACTIVE ALERTS: {len(alerts)}")
    for a in alerts:
        lines.append(f"  {a['id']}: {a['type']} — {a['device']} ({a['severity']})")

    return "\n".join(lines)


def query_ollama(user_message: str, data_snapshot: str) -> str:
    """Send a query to Ollama and return the response text."""
    system = SYSTEM_PROMPT.format(data_snapshot=data_snapshot)

    payload = {
        "model": MODEL,
        "prompt": user_message,
        "system": system,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 150,
        }
    }

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "").strip()

    except urllib.error.URLError as e:
        return f"⚠️ AI service unavailable: {e.reason}"
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


def is_ollama_running() -> bool:
    """Check if Ollama is running."""
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except:
        return False
