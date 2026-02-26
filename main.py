"""
POS AI Bot — Demo Gateway (FastAPI + WebSocket)
- LLM-powered intent detection (Ollama qwen2.5:1.5b)
- Single-card forms for actions that need user input
- JWT + RBAC
"""
import json
import time
import jwt
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from llm_engine import process_message
from tools import get_tools_for_role
from dummy_data import api_add_device, api_disable_device, api_create_merchant

JWT_SECRET = "demo-secret-key-pos-2026"
JWT_ALGORITHM = "HS256"

DEMO_USERS = {
    "viewer_demo": {"user_id": "U001", "role": "viewer", "tenant_id": "tenant-001", "name": "Priya Patel"},
    "manager_demo": {"user_id": "U002", "role": "manager", "tenant_id": "tenant-001", "name": "Rahul Sharma"},
    "admin_demo": {"user_id": "U003", "role": "admin", "tenant_id": "tenant-001", "name": "Amit Kumar"},
    "super_admin_demo": {"user_id": "U004", "role": "super_admin", "tenant_id": "tenant-001", "name": "System Admin"},
}

app = FastAPI(title="POS AI Bot Demo", version="1.0.0")

# ── Form definitions for write-actions ────────────────────────────────────────
FORMS = {
    "add_device": {
        "title": "📱 Add New Device",
        "fields": [
            {"name": "device_id", "label": "Device ID", "type": "text", "placeholder": "POS-1234", "required": True},
            {"name": "merchant_id", "label": "Merchant", "type": "select", "options": [
                {"value": "MER-0098", "label": "MER-0098 — Cafe Blue"},
                {"value": "MER-0112", "label": "MER-0112 — Green Mart"},
                {"value": "MER-0205", "label": "MER-0205 — Spice House"},
                {"value": "MER-0301", "label": "MER-0301 — BookNook"},
                {"value": "MER-0455", "label": "MER-0455 — FreshBites"},
            ]},
            {"name": "region", "label": "Region", "type": "select", "options": [
                {"value": "MUM", "label": "Mumbai (MUM)"},
                {"value": "DEL", "label": "Delhi (DEL)"},
                {"value": "BLR", "label": "Bangalore (BLR)"},
                {"value": "HYD", "label": "Hyderabad (HYD)"},
            ]},
        ],
        "submit_label": "Register Device",
        "execute": lambda d: api_add_device(d["device_id"], d["merchant_id"], d["region"]),
    },
    "disable_device": {
        "title": "🚫 Disable Device",
        "fields": [
            {"name": "device_id", "label": "Device ID", "type": "text", "placeholder": "POS-3301", "required": True},
            {"name": "reason", "label": "Reason", "type": "select", "options": [
                {"value": "Hardware malfunction", "label": "Hardware malfunction"},
                {"value": "Lost/Stolen", "label": "Lost / Stolen"},
                {"value": "Merchant request", "label": "Merchant request"},
                {"value": "Scheduled maintenance", "label": "Scheduled maintenance"},
            ]},
        ],
        "submit_label": "Disable Device",
        "execute": lambda d: api_disable_device(d["device_id"], d["reason"]),
    },
    "create_merchant": {
        "title": "🏪 Onboard New Merchant",
        "fields": [
            {"name": "name", "label": "Merchant Name", "type": "text", "placeholder": "e.g. Spice Garden", "required": True},
            {"name": "merchant_id", "label": "Merchant ID", "type": "text", "placeholder": "MER-0500", "required": True},
            {"name": "category", "label": "Category", "type": "select", "options": [
                {"value": "restaurant", "label": "🍽 Restaurant"},
                {"value": "retail", "label": "🛒 Retail"},
                {"value": "food_court", "label": "🍕 Food Court"},
                {"value": "pharmacy", "label": "💊 Pharmacy"},
                {"value": "grocery", "label": "🥬 Grocery"},
            ]},
            {"name": "region", "label": "Region", "type": "select", "options": [
                {"value": "MUM", "label": "Mumbai (MUM)"},
                {"value": "DEL", "label": "Delhi (DEL)"},
                {"value": "BLR", "label": "Bangalore (BLR)"},
                {"value": "HYD", "label": "Hyderabad (HYD)"},
            ]},
            {"name": "address", "label": "Address", "type": "text", "placeholder": "Full address", "required": True},
            {"name": "contact", "label": "Contact", "type": "text", "placeholder": "+91-9876543210", "required": True},
        ],
        "submit_label": "Create Merchant",
        "execute": lambda d: api_create_merchant(d["name"], d["merchant_id"], d["category"], d["region"], d["address"], d["contact"]),
    },
}

FORM_TRIGGERS = {"add_device", "disable_device", "create_merchant"}


def create_token(username: str) -> str:
    user = DEMO_USERS.get(username)
    if not user: return None
    payload = {**user, "username": username,
               "exp": datetime.utcnow() + timedelta(hours=24),
               "iat": datetime.utcnow()}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def validate_token(token: str) -> dict:
    try: return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError: return {"error": "Token expired"}
    except jwt.InvalidTokenError: return {"error": "Invalid token"}


@app.get("/api/auth/login")
async def login(username: str):
    if username not in DEMO_USERS:
        return JSONResponse({"error": "Unknown user."}, status_code=400)
    return {"token": create_token(username), "user": DEMO_USERS[username]}

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/tools")
async def list_tools(role: str = "viewer"):
    tools = get_tools_for_role(role)
    return {"role": role, "tool_count": len(tools), "tools": tools}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            token = data.get("token", "")
            user = validate_token(token)
            if "error" in user:
                await websocket.send_json({"type": "error", "code": 401, "message": f"Auth failed: {user['error']}"})
                continue

            role = user.get("role", "viewer")

            # ── Form submission ──
            if data.get("type") == "form_submit":
                form_name = data.get("form_name", "")
                form_data = data.get("form_data", {})
                form_def = FORMS.get(form_name)

                await websocket.send_json({"type": "typing", "status": True})
                start = time.time()

                if not form_def:
                    await websocket.send_json({"type": "message", "role": "assistant",
                        "content": "⚠️ Unknown form.", "buttons": [], "metadata": {
                            "tool_used": None, "tool_args": None, "rbac_blocked": False,
                            "confidence": "low", "latency_ms": 0, "model": "system", "user_role": role}})
                    await websocket.send_json({"type": "typing", "status": False})
                    continue

                try:
                    result = form_def["execute"](form_data)
                    latency = round((time.time() - start) * 1000)
                    if isinstance(result, dict) and "error" in result:
                        content = f"❌ {result['error']}"
                    else:
                        content = f"✅ {result.get('message', 'Operation completed successfully.')}"
                except Exception as e:
                    content = f"⚠️ Error: {str(e)}"
                    latency = round((time.time() - start) * 1000)

                await websocket.send_json({"type": "message", "role": "assistant",
                    "content": content, "buttons": [], "metadata": {
                        "tool_used": form_name, "tool_args": form_data, "rbac_blocked": False,
                        "confidence": "high", "latency_ms": latency, "model": "form-action", "user_role": role}})
                await websocket.send_json({"type": "typing", "status": False})
                continue

            # ── Normal chat message ──
            user_msg = data.get("message", "").strip()
            if not user_msg: continue

            await websocket.send_json({"type": "typing", "status": True})
            start = time.time()

            result = process_message(user_msg, role)
            tool_name = result.get("tool_used")
            latency = round((time.time() - start) * 1000)

            # If tool triggers a form → send form card instead of executing
            if tool_name in FORM_TRIGGERS and not result.get("rbac_blocked"):
                form_def = FORMS[tool_name]
                await websocket.send_json({
                    "type": "form",
                    "form_name": tool_name,
                    "title": form_def["title"],
                    "fields": form_def["fields"],
                    "submit_label": form_def["submit_label"],
                    "metadata": {"latency_ms": latency, "model": "qwen2.5:1.5b (Ollama)", "user_role": role}
                })
                await websocket.send_json({"type": "typing", "status": False})
                continue

            # Regular response
            await websocket.send_json({
                "type": "message", "role": "assistant",
                "content": result["response"], "buttons": [],
                "metadata": {
                    "tool_used": result["tool_used"], "tool_args": result["tool_args"],
                    "rbac_blocked": result["rbac_blocked"], "confidence": result["confidence"],
                    "latency_ms": latency, "model": "qwen2.5:1.5b (Ollama)", "user_role": role}
            })
            await websocket.send_json({"type": "typing", "status": False})

    except WebSocketDisconnect: pass
    except Exception as e:
        try: await websocket.send_json({"type": "error", "message": str(e)})
        except: pass


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open("static/index.html", "r") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500, log_level="info")
