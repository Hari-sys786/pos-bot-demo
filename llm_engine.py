"""
LLM Engine — Ollama-powered intent detection + data-aware response generation.
Architecture:
  1. LLM classifies message → READ_QUERY | WRITE_ACTION | CHAT
  2. READ_QUERY → gather all relevant data → feed to LLM → it answers ANY question
  3. WRITE_ACTION → return action type (server shows form)
  4. CHAT → LLM responds conversationally
"""
import json
import re
import urllib.request
from tools import get_tools_for_role, validate_tool_call
from dummy_data import (
    api_get_device_status, api_list_devices, api_get_report,
    api_get_transactions, api_search_faq, api_add_device,
    api_disable_device, api_create_merchant, api_get_user_activity,
    api_list_tenants, api_update_tenant, api_get_transaction_summary,
    DEVICES, MERCHANTS, FAQ
)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b"


def call_ollama(prompt: str, max_tokens: int = 300) -> str | None:
    try:
        payload = json.dumps({
            "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.1, "num_predict": max_tokens}
        }).encode()
        req = urllib.request.Request(OLLAMA_URL, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read()).get("response", "").strip()
    except Exception:
        return None


# ── Step 1: Classify intent ──────────────────────────────────────────────────

CLASSIFY_PROMPT = """Classify this POS management chatbot message. Reply ONLY with JSON.

CATEGORIES:
- READ: Any question about data (devices, transactions, reports, merchants, users, FAQ, comparisons, analytics, counts, status)
- WRITE: User wants to ADD, CREATE, DISABLE, DELETE, UPDATE, REGISTER, or ONBOARD something
- CHAT: Greetings, small talk, unclear messages

WRITE ACTIONS: add_device, disable_device, create_merchant

Examples:
"Is POS-4421 online?" → {"category":"READ"}
"List all devices" → {"category":"READ"}
"Which device has most transactions?" → {"category":"READ"}
"Show me reports for Delhi" → {"category":"READ"}
"How do I reset a device?" → {"category":"READ"}
"Compare transaction volumes" → {"category":"READ"}
"What's the busiest region?" → {"category":"READ"}
"Add a device" → {"category":"WRITE","action":"add_device"}
"Register new device" → {"category":"WRITE","action":"add_device"}
"I want to add a device" → {"category":"WRITE","action":"add_device"}
"Disable POS-3301" → {"category":"WRITE","action":"disable_device"}
"Deactivate a device" → {"category":"WRITE","action":"disable_device"}
"Add merchant" → {"category":"WRITE","action":"create_merchant"}
"Create a new merchant" → {"category":"WRITE","action":"create_merchant"}
"Onboard a merchant" → {"category":"WRITE","action":"create_merchant"}
"Hi" → {"category":"CHAT"}
"Hello" → {"category":"CHAT"}
"Thanks" → {"category":"CHAT"}

Message: "{message}"
JSON:"""


def classify_intent(message: str) -> dict:
    """Classify message into READ/WRITE/CHAT using LLM. Fallback: regex."""
    prompt = CLASSIFY_PROMPT.replace("{message}", message.replace('"', '\\"'))
    raw = call_ollama(prompt, max_tokens=60)

    if raw:
        try:
            match = re.search(r'\{[^{}]+\}', raw)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

    # Regex fallback
    return classify_fallback(message)


def classify_fallback(message: str) -> dict:
    msg = message.lower().strip()

    # Write actions
    if ("add" in msg or "register" in msg or "new" in msg) and ("device" in msg or "pos" in msg) and "merchant" not in msg:
        return {"category": "WRITE", "action": "add_device"}
    if ("add" in msg or "create" in msg or "onboard" in msg or "new" in msg) and "merchant" in msg:
        return {"category": "WRITE", "action": "create_merchant"}
    if any(w in msg for w in ["disable", "deactivate", "turn off", "block"]) and ("device" in msg or "pos" in msg or re.search(r'pos-\d+', msg)):
        return {"category": "WRITE", "action": "disable_device"}

    # Chat
    if msg in ("hi", "hello", "hey", "thanks", "thank you", "ok", "bye", "good morning", "good evening"):
        return {"category": "CHAT"}

    # Everything else is a read query
    return {"category": "READ"}


# ── Step 2: Gather ALL relevant data for read queries ────────────────────────

def gather_data() -> str:
    """Collect all system data into a context string for the LLM."""
    devices = api_list_devices()
    transactions = api_get_transactions(limit=15)
    report = api_get_report()
    txn_summary = api_get_transaction_summary()
    activity = api_get_user_activity()
    faq = FAQ

    ctx = "=== POS DEVICES ===\n"
    for d in devices:
        ctx += f"{d['device_id']}: merchant={d['merchant']}, region={d['region']}, status={d['status']}, battery={d['battery']}%, last_txn={d['last_txn']}, model={d['model']}\n"

    ctx += "\n=== MERCHANTS ===\n"
    for mid, m in MERCHANTS.items():
        ctx += f"{mid}: name={m['name']}, category={m['category']}, region={m['region']}, devices={m['devices']}\n"

    ctx += "\n=== TRANSACTION SUMMARY (by device, sorted by count desc) ===\n"
    for t in txn_summary:
        ctx += f"{t['device_id']} ({t['merchant']}, {t['region']}): {t['txn_count']} transactions, total=₹{t['total_volume']:,.2f}, avg=₹{t['avg_txn']:,.2f}\n"

    ctx += "\n=== RECENT TRANSACTIONS (last 15) ===\n"
    for t in transactions[:15]:
        ctx += f"{t['txn_id']}: device={t['device_id']}, type={t['type']}, amount=₹{t['amount']:,.2f}, status={t['status']}, time={t['timestamp']}\n"

    ctx += f"\n=== SETTLEMENT REPORT ({report['date']}) ===\n"
    for region, data in report["regions"].items():
        ctx += f"{region}: total=₹{data['total_amount']:,.2f}, txns={data['total_txns']}, success={data['successful_txns']}, failed={data['failed_txns']}, refunds=₹{data['refunds']:,.2f}, net=₹{data['net_settlement']:,.2f}\n"

    ctx += "\n=== USER ACTIVITY ===\n"
    for a in activity:
        ctx += f"{a['user']}: {a['action']} at {a['timestamp']} from {a['ip']}\n"

    ctx += "\n=== FAQ ===\n"
    for f in faq:
        ctx += f"Q: {f['q']}\nA: {f['a']}\n\n"

    return ctx


# ── Step 3: LLM answers ANY question using the data ─────────────────────────

ANSWER_PROMPT = """You are NexPOS AI, a POS management assistant. Answer the user's question using ONLY the data below.

{data}

RULES:
- Be concise (3-10 lines max)
- Use bullet points for lists
- Use emojis sparingly: 📱💳📊✅❌🟢🔴🥇🥈🥉
- Format currency as ₹ with commas
- Use **bold** for emphasis
- If data doesn't contain the answer, say so honestly
- Answer the EXACT question asked, don't dump everything

User question: "{question}"
Answer:"""


def answer_read_query(message: str) -> str:
    """Feed all data to LLM and let it answer any question."""
    data = gather_data()
    prompt = ANSWER_PROMPT.replace("{data}", data).replace("{question}", message.replace('"', '\\"'))
    response = call_ollama(prompt, max_tokens=500)

    if response and len(response) > 15:
        return response

    # Fallback: basic keyword matching for common queries
    return answer_fallback(message)


def answer_fallback(message: str) -> str:
    """Simple fallback when Ollama is down."""
    msg = message.lower()

    if re.search(r'pos-\d+', msg):
        did = re.search(r'POS-\d+', message, re.IGNORECASE).group().upper()
        result = api_get_device_status(did)
        if "error" in result:
            return f"❌ {result['error']}"
        s = '🟢' if result['status']=='online' else '🔴' if result['status']=='offline' else '🟡'
        return f"📱 **{result['device_id']}** ({result['model']})\n• Merchant: {result['merchant']}\n• Region: {result['region']}\n• Status: {s} {result['status'].upper()}\n• Battery: {result['battery']}%\n• Last Txn: {result['last_txn']}"

    if any(w in msg for w in ["device", "list", "all pos"]):
        devices = api_list_devices()
        lines = ["📋 **POS Devices:**\n"]
        for d in devices:
            icon = '🟢' if d['status']=='online' else '🔴' if d['status']=='offline' else '🟡'
            lines.append(f"• {d['device_id']} — {d['merchant']} ({d['region']}) {icon} | 🔋{d['battery']}%")
        return "\n".join(lines)

    if any(w in msg for w in ["transaction", "txn"]):
        txns = api_get_transactions(limit=10)
        lines = ["💳 **Recent Transactions:**\n"]
        for t in txns[:5]:
            icon = "✅" if t["status"]=="success" else "❌" if t["status"]=="failed" else "⏳"
            lines.append(f"• {t['txn_id']} | {t['device_id']} | ₹{t['amount']:,.2f} | {icon}")
        return "\n".join(lines)

    if any(w in msg for w in ["report", "settlement"]):
        r = api_get_report()
        lines = [f"📊 **Settlement Report — {r['date']}**\n"]
        for region, data in r["regions"].items():
            lines.append(f"**{region}:** ₹{data['total_amount']:,.2f} ({data['total_txns']} txns) | Net: ₹{data['net_settlement']:,.2f}")
        return "\n".join(lines)

    if any(w in msg for w in ["faq", "how to", "how do", "reset", "refund"]):
        results = api_search_faq(message)
        lines = ["📚 **Knowledge Base:**\n"]
        for f in results:
            lines.append(f"**Q:** {f['q']}\n**A:** {f['a']}\n")
        return "\n".join(lines)

    if any(w in msg for w in ["activity", "logged", "audit"]):
        acts = api_get_user_activity()
        lines = ["👥 **User Activity:**\n"]
        for a in acts:
            lines.append(f"• {a['user']} — {a['action']} at {a['timestamp']}")
        return "\n".join(lines)

    return "I couldn't process that. Try asking about devices, transactions, reports, or FAQ."


# ── Main entry point ─────────────────────────────────────────────────────────

def process_message(message: str, role: str, conversation_history: list = None) -> dict:
    """
    1. Classify → READ / WRITE / CHAT
    2. READ → gather data → LLM answers
    3. WRITE → return action (server shows form)
    4. CHAT → LLM responds
    """
    classification = classify_intent(message)
    category = classification.get("category", "CHAT")

    # ── WRITE: trigger form ──
    if category == "WRITE":
        action = classification.get("action", "")
        # RBAC check
        tool_min_roles = {"add_device": "admin", "disable_device": "admin", "create_merchant": "admin"}
        if not validate_tool_call(action, role) if action in tool_min_roles else False:
            return {
                "response": f"🚫 **Access Denied.** `{action}` requires admin role. Your role: **{role}**.",
                "tool_used": action, "tool_args": None, "rbac_blocked": True, "confidence": "high"
            }
        return {
            "response": None,
            "tool_used": action, "tool_args": None, "rbac_blocked": False, "confidence": "high"
        }

    # ── READ: gather data + LLM answers ──
    if category == "READ":
        response = answer_read_query(message)
        return {
            "response": response,
            "tool_used": "data_query", "tool_args": None,
            "rbac_blocked": False, "confidence": "high"
        }

    # ── CHAT: conversational ──
    chat_prompt = f"""You are NexPOS AI, a helpful POS management assistant.
The user said: "{message}"
You can help with: device status, transactions, reports, FAQ, add/disable devices, merchant management.
Keep response to 2-4 lines. Be friendly and professional.
Response:"""

    llm_resp = call_ollama(chat_prompt, max_tokens=200)
    if llm_resp and len(llm_resp) > 10:
        response = llm_resp
    else:
        response = "👋 Hi! I'm NexPOS AI. I can help with device status, transactions, reports, FAQ, and more. What would you like to know?"

    return {
        "response": response,
        "tool_used": None, "tool_args": None, "rbac_blocked": False, "confidence": "high"
    }
