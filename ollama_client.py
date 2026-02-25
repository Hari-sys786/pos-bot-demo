#!/usr/bin/env python3
"""Ollama integration — intent classification + answer generation."""

import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5:1.5b"

# ── Intent Classifier ──

INTENT_PROMPT = """You route user messages. Reply with ONLY one word from this list:

DEVICE_LIST = view devices, check status, battery, terminals
DEVICE_ADD = add or register a new device
MERCHANT_LIST = view merchants, stores, shops  
MERCHANT_ADD = add or onboard a new merchant
REPORTS = reports, transactions, revenue, analytics, summary
MUMBAI = about mumbai specifically
DELHI = about delhi specifically
BANGALORE = about bangalore specifically
CHENNAI = about chennai specifically
ALERTS = alerts, warnings, notifications
FAQ_RESET = how to reset a device
FAQ_SETTLEMENT = about settlement
FAQ_PAPER = about paper rolls
FAQ_CONNECTIVITY = about connectivity or network
HELP = general help or troubleshooting
MENU = main menu, go back, start over
GENERAL = anything else, greetings, comparisons, analysis, chitchat

Examples:
"i want to add a device" → DEVICE_ADD
"show all merchants" → MERCHANT_LIST  
"add a new merchant" → MERCHANT_ADD
"how is mumbai doing" → MUMBAI
"any alerts?" → ALERTS
"compare two cities" → GENERAL
"hello" → GENERAL
"what is settlement process" → FAQ_SETTLEMENT

"{message}" →"""

ANSWER_PROMPT = """You are NexPOS AI — POS management assistant. Be concise (<100 words). Use markdown **bold** and bullet points.

DATA:
{data_snapshot}

Answer from the data above. Be helpful and brief."""

VALID_INTENTS = [
    "DEVICE_LIST", "DEVICE_ADD", "MERCHANT_LIST", "MERCHANT_ADD",
    "REPORTS", "MUMBAI", "DELHI", "BANGALORE", "CHENNAI",
    "ALERTS", "FAQ_RESET", "FAQ_SETTLEMENT", "FAQ_PAPER", "FAQ_CONNECTIVITY",
    "HELP", "MENU", "GENERAL"
]


def classify_intent(message: str) -> str:
    """Classify user message into an intent code."""
    payload = {
        "model": MODEL,
        "prompt": INTENT_PROMPT.format(message=message),
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 5}
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            raw = result.get("response", "").strip().upper().replace(" ", "_")
            for intent in VALID_INTENTS:
                if intent in raw:
                    return intent
            return "GENERAL"
    except Exception:
        return "GENERAL"


def generate_answer(message: str, data_snapshot: str) -> str:
    """Generate a full answer for open-ended queries."""
    payload = {
        "model": MODEL,
        "prompt": message,
        "system": ANSWER_PROMPT.format(data_snapshot=data_snapshot),
        "stream": False,
        "options": {"temperature": 0.7, "top_p": 0.9, "num_predict": 200}
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
        return f"⚠️ AI unavailable: {e.reason}"
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


def build_data_snapshot(devices, merchants, transactions, alerts):
    """Compact data snapshot for LLM context."""
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


def is_ollama_running() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except:
        return False
