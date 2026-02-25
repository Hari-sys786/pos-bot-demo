#!/usr/bin/env python3
"""POS Management Chatbot Demo — IRCTC-style guided bot with dummy data."""

import json
import re
import threading

from ollama_client import classify_intent, generate_answer, build_data_snapshot, is_ollama_running

# ─── Dummy Data ───────────────────────────────────────────────────────────────

DEVICES = {
    "POS-1001": {"name": "Counter A", "merchant": "Cafe Blue", "merchant_id": "MER-001", "region": "Mumbai", "status": "Online", "battery": 87, "last_txn": "2026-02-24 15:32", "model": "Verifone V240m", "fw": "v3.2.1"},
    "POS-1002": {"name": "Counter B", "merchant": "Cafe Blue", "merchant_id": "MER-001", "region": "Mumbai", "status": "Online", "battery": 45, "last_txn": "2026-02-24 15:28", "model": "Verifone V240m", "fw": "v3.2.1"},
    "POS-2001": {"name": "Billing 1", "merchant": "FreshMart", "merchant_id": "MER-002", "region": "Delhi", "status": "Offline", "battery": 12, "last_txn": "2026-02-23 22:10", "model": "PAX A920", "fw": "v5.1.0"},
    "POS-2002": {"name": "Billing 2", "merchant": "FreshMart", "merchant_id": "MER-002", "region": "Delhi", "status": "Online", "battery": 93, "last_txn": "2026-02-24 14:55", "model": "PAX A920", "fw": "v5.1.0"},
    "POS-3001": {"name": "Main POS", "merchant": "BookNook", "merchant_id": "MER-003", "region": "Bangalore", "status": "Online", "battery": 72, "last_txn": "2026-02-24 16:01", "model": "Ingenico Move5000", "fw": "v2.8.4"},
    "POS-3002": {"name": "Express", "merchant": "BookNook", "merchant_id": "MER-003", "region": "Bangalore", "status": "Maintenance", "battery": 0, "last_txn": "2026-02-22 09:30", "model": "Ingenico Move5000", "fw": "v2.8.4"},
    "POS-4001": {"name": "Register 1", "merchant": "SpiceJunction", "merchant_id": "MER-004", "region": "Chennai", "status": "Online", "battery": 66, "last_txn": "2026-02-24 15:50", "model": "Sunmi P2", "fw": "v1.4.2"},
    "POS-4002": {"name": "Register 2", "merchant": "SpiceJunction", "merchant_id": "MER-004", "region": "Chennai", "status": "Online", "battery": 54, "last_txn": "2026-02-24 15:47", "model": "Sunmi P2", "fw": "v1.4.2"},
}

MERCHANTS = {
    "MER-001": {"name": "Cafe Blue", "category": "Restaurant", "region": "Mumbai", "contact": "Rahul Sharma", "phone": "+91-98765-43210", "devices": 2, "status": "Active", "onboarded": "2025-08-15"},
    "MER-002": {"name": "FreshMart", "category": "Grocery", "region": "Delhi", "contact": "Priya Verma", "phone": "+91-98765-43211", "devices": 2, "status": "Active", "onboarded": "2025-09-01"},
    "MER-003": {"name": "BookNook", "category": "Retail", "region": "Bangalore", "contact": "Amit Patel", "phone": "+91-98765-43212", "devices": 2, "status": "Active", "onboarded": "2025-10-20"},
    "MER-004": {"name": "SpiceJunction", "category": "Restaurant", "region": "Chennai", "contact": "Deepa Rajan", "phone": "+91-98765-43213", "devices": 2, "status": "Active", "onboarded": "2026-01-05"},
}

TRANSACTIONS_DAILY = {
    "Mumbai": {"count": 342, "volume": 485000, "avg": 1418},
    "Delhi": {"count": 289, "volume": 372000, "avg": 1287},
    "Bangalore": {"count": 198, "volume": 267000, "avg": 1348},
    "Chennai": {"count": 256, "volume": 334000, "avg": 1305},
}

ALERTS = [
    {"id": "ALT-001", "type": "Low Battery", "device": "POS-2001", "merchant": "FreshMart", "time": "14:30", "severity": "warning"},
    {"id": "ALT-002", "type": "Device Offline", "device": "POS-2001", "merchant": "FreshMart", "time": "22:15", "severity": "critical"},
    {"id": "ALT-003", "type": "Maintenance Due", "device": "POS-3002", "merchant": "BookNook", "time": "09:00", "severity": "info"},
    {"id": "ALT-004", "type": "High Txn Volume", "device": "POS-1001", "merchant": "Cafe Blue", "time": "13:00", "severity": "info"},
]

FAQ = {
    "reset device": "To reset a POS device:\n1. Hold Power + Volume Down for 10s\n2. Select 'Factory Reset' from recovery menu\n3. Device will reboot and re-register automatically\n\n⚠️ This erases all local data. Pending transactions are synced first.",
    "settlement": "Settlement runs automatically at 11:00 PM daily. Manual settlement: Device Menu → Settings → Force Settlement. Funds reflect in T+1 business days.",
    "paper roll": "Compatible paper rolls: 57mm × 40mm thermal. Order from Supplies Portal or contact support@posplatform.com. Average roll lasts ~200 transactions.",
    "connectivity": "POS devices support WiFi, 4G SIM, and Bluetooth tethering. Priority: WiFi > 4G > BT. Check signal: Menu → Network → Diagnostics.",
}

# ─── Bot Engine ───────────────────────────────────────────────────────────────

class BotEngine:
    def __init__(self):
        self.sessions = {}

    def get_session(self, sid):
        if sid not in self.sessions:
            self.sessions[sid] = {"state": "main_menu"}
        return self.sessions[sid]

    def process(self, sid, text, button_data=None):
        session = self.get_session(sid)
        action = button_data or text.strip().lower()

        # Handle form submissions
        if action.startswith("form_submit_"):
            form_type = action.replace("form_submit_", "")
            try:
                form_data = json.loads(text) if text.startswith("{") else {}
            except:
                form_data = {}
            return self._handle_form_submit(form_type, form_data)

        # Search state
        if session["state"] == "search_device":
            session["state"] = "main_menu"
            did = text.strip().upper()
            if did in DEVICES:
                return self._device_detail(did)
            return [{"type": "text", "content": f"❌ Device **{did}** not found.", "buttons": [{"text": "🔍 Try Again", "data": "search_device"}, {"text": "📋 All Devices", "data": "view_all_devices"}, {"text": "🏠 Menu", "data": "menu"}]}]

        if action in ("start", "menu", "hi", "hello", "hey", "/start", "home"):
            return self._main_menu()
        if action == "device_status": return self._device_menu()
        if action == "view_all_devices": return self._all_devices()
        if action.startswith("device_detail_"): return self._device_detail(action[14:])
        if action == "search_device":
            session["state"] = "search_device"
            return [{"type": "text", "content": "🔍 Enter the Device ID (e.g. POS-1001):"}]
        if action == "merchants": return self._merchant_menu()
        if action == "view_all_merchants": return self._all_merchants()
        if action.startswith("merchant_detail_"): return self._merchant_detail(action[16:])
        if action == "add_merchant": return self._show_merchant_form()
        if action == "add_device": return self._show_device_form()
        if action.startswith("confirm_deactivate_"): return self._deactivate_confirm(action[19:])
        if action.startswith("do_deactivate_"): return self._do_deactivate(action[14:])
        if action == "reports": return self._reports_menu()
        if action == "daily_summary": return self._daily_summary()
        if action.startswith("region_report_"): return self._region_report(action[14:])
        if action == "alerts": return self._show_alerts()
        if action.startswith("alert_ack_"): return self._ack_alert(action[10:])
        if action == "help": return self._help_menu()
        if action.startswith("faq_"): return self._show_faq(action[4:])

        return self._nl_fallback(text)

    # ── Menus ──

    def _main_menu(self):
        return [{"type": "text", "content": "👋 **Welcome to POS Management Bot!**\n\nI can help you manage devices, merchants, view reports and more. What would you like to do?",
                 "buttons": [
                     {"text": "📱 Devices", "data": "device_status"},
                     {"text": "🏪 Merchants", "data": "merchants"},
                     {"text": "📊 Reports", "data": "reports"},
                     {"text": "🔔 Alerts", "data": "alerts"},
                     {"text": "❓ Help & FAQ", "data": "help"},
                 ]}]

    # ── Devices ──

    def _device_menu(self):
        online = sum(1 for d in DEVICES.values() if d["status"] == "Online")
        offline = sum(1 for d in DEVICES.values() if d["status"] == "Offline")
        maint = sum(1 for d in DEVICES.values() if d["status"] == "Maintenance")
        return [{"type": "text", "content": f"📱 **Device Dashboard**\n\n🟢 Online: **{online}**  •  🔴 Offline: **{offline}**  •  🟡 Maintenance: **{maint}**\nTotal: **{len(DEVICES)}** devices",
             "buttons": [
                 {"text": "📋 All Devices", "data": "view_all_devices"},
                 {"text": "🔍 Search by ID", "data": "search_device"},
                 {"text": "➕ Add Device", "data": "add_device"},
                 {"text": "🏠 Menu", "data": "menu"},
             ]}]

    def _all_devices(self):
        cards = []
        for did, d in DEVICES.items():
            icon = {"Online": "🟢", "Offline": "🔴", "Maintenance": "🟡"}.get(d["status"], "⚪")
            bat = "🪫" if d["battery"] < 20 else "🔋"
            cards.append({
                "title": f"{icon} {did} — {d['name']}",
                "subtitle": f"{d['merchant']} • {d['region']}",
                "fields": [f"Status: **{d['status']}**", f"{bat} Battery: **{d['battery']}%**", f"Last Txn: {d['last_txn']}"],
                "buttons": [{"text": "View Details", "data": f"device_detail_{did}"}]
            })
        return [{"type": "cards", "content": "📱 **All Devices**", "cards": cards,
                 "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]

    def _device_detail(self, did):
        d = DEVICES.get(did)
        if not d: return [{"type": "text", "content": f"❌ Device {did} not found.", "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]
        icon = {"Online": "🟢", "Offline": "🔴", "Maintenance": "🟡"}.get(d["status"], "⚪")
        content = f"📱 **{did} — {d['name']}** {icon}\n\n| | |\n|---|---|\n| Merchant | {d['merchant']} |\n| Region | {d['region']} |\n| Model | {d['model']} |\n| Firmware | {d['fw']} |\n| Battery | {d['battery']}% |\n| Last Txn | {d['last_txn']} |\n| Status | {d['status']} |"
        btns = [{"text": "📋 All Devices", "data": "view_all_devices"}, {"text": "🏠 Menu", "data": "menu"}]
        if d["status"] == "Online":
            btns.insert(0, {"text": "🔴 Deactivate", "data": f"confirm_deactivate_{did}"})
        return [{"type": "text", "content": content, "buttons": btns}]

    def _deactivate_confirm(self, did):
        d = DEVICES.get(did)
        if not d: return [{"type": "text", "content": "❌ Device not found.", "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]
        return [{"type": "text", "content": f"⚠️ **Confirm Deactivation**\n\nDevice: **{did}** ({d['name']})\nMerchant: {d['merchant']}\n\nThis will take the device offline.",
                 "buttons": [{"text": "✅ Yes, Deactivate", "data": f"do_deactivate_{did}"}, {"text": "❌ Cancel", "data": f"device_detail_{did}"}]}]

    def _do_deactivate(self, did):
        if did in DEVICES:
            DEVICES[did]["status"] = "Offline"
            DEVICES[did]["battery"] = 0
        return [{"type": "text", "content": f"✅ Device **{did}** deactivated.",
                 "buttons": [{"text": "📋 All Devices", "data": "view_all_devices"}, {"text": "🏠 Menu", "data": "menu"}]}]

    # ── Forms (inline card forms) ──

    def _show_device_form(self):
        merchant_options = [{"value": mid, "label": m["name"]} for mid, m in MERCHANTS.items()]
        return [{"type": "form", "title": "➕ Add New Device", "form_id": "device", "fields": [
            {"name": "device_id", "label": "Device ID", "type": "text", "placeholder": "POS-5001", "required": True},
            {"name": "name", "label": "Device Name", "type": "text", "placeholder": "Counter A", "required": True},
            {"name": "merchant", "label": "Merchant", "type": "select", "options": merchant_options, "required": True},
            {"name": "region", "label": "Region", "type": "select", "options": [
                {"value": "Mumbai", "label": "Mumbai"}, {"value": "Delhi", "label": "Delhi"},
                {"value": "Bangalore", "label": "Bangalore"}, {"value": "Chennai", "label": "Chennai"},
                {"value": "Hyderabad", "label": "Hyderabad"}
            ], "required": True},
            {"name": "model", "label": "Device Model", "type": "select", "options": [
                {"value": "Verifone V240m", "label": "Verifone V240m"}, {"value": "PAX A920", "label": "PAX A920"},
                {"value": "Ingenico Move5000", "label": "Ingenico Move5000"}, {"value": "Sunmi P2", "label": "Sunmi P2"},
            ], "required": True},
        ]}]

    def _show_merchant_form(self):
        return [{"type": "form", "title": "➕ Add New Merchant", "form_id": "merchant", "fields": [
            {"name": "name", "label": "Merchant Name", "type": "text", "placeholder": "Cafe Blue", "required": True},
            {"name": "category", "label": "Category", "type": "select", "options": [
                {"value": "Restaurant", "label": "🍽️ Restaurant"}, {"value": "Grocery", "label": "🛒 Grocery"},
                {"value": "Retail", "label": "🛍️ Retail"}, {"value": "Pharmacy", "label": "💊 Pharmacy"},
                {"value": "Fuel Station", "label": "⛽ Fuel Station"},
            ], "required": True},
            {"name": "region", "label": "Region", "type": "select", "options": [
                {"value": "Mumbai", "label": "Mumbai"}, {"value": "Delhi", "label": "Delhi"},
                {"value": "Bangalore", "label": "Bangalore"}, {"value": "Chennai", "label": "Chennai"},
                {"value": "Hyderabad", "label": "Hyderabad"},
            ], "required": True},
            {"name": "contact", "label": "Contact Person", "type": "text", "placeholder": "Rahul Sharma", "required": True},
            {"name": "phone", "label": "Phone Number", "type": "text", "placeholder": "+91-98765-43210", "required": True},
        ]}]

    def _handle_form_submit(self, form_type, data):
        if form_type == "device":
            did = data.get("device_id", "").upper()
            if not did or not data.get("name") or not data.get("merchant"):
                return [{"type": "text", "content": "❌ Please fill all required fields.", "buttons": [{"text": "➕ Try Again", "data": "add_device"}, {"text": "🏠 Menu", "data": "menu"}]}]
            if did in DEVICES:
                return [{"type": "text", "content": f"❌ Device **{did}** already exists.", "buttons": [{"text": "➕ Try Again", "data": "add_device"}, {"text": "🏠 Menu", "data": "menu"}]}]
            mer_name = MERCHANTS.get(data["merchant"], {}).get("name", data["merchant"])
            DEVICES[did] = {
                "name": data["name"], "merchant": mer_name, "merchant_id": data.get("merchant", ""),
                "region": data.get("region", ""), "status": "Online", "battery": 100,
                "last_txn": "—", "model": data.get("model", ""), "fw": "v1.0.0"
            }
            if data.get("merchant") in MERCHANTS:
                MERCHANTS[data["merchant"]]["devices"] += 1
            return [{"type": "text", "content": f"✅ **Device Registered!**\n\n🆔 **{did}**\n📱 {data['name']}\n🏪 {mer_name} • 📍 {data.get('region','')}\n📟 {data.get('model','')}",
                     "buttons": [{"text": "📋 View Devices", "data": "view_all_devices"}, {"text": "🏠 Menu", "data": "menu"}]}]

        elif form_type == "merchant":
            if not data.get("name") or not data.get("category"):
                return [{"type": "text", "content": "❌ Please fill all required fields.", "buttons": [{"text": "➕ Try Again", "data": "add_merchant"}, {"text": "🏠 Menu", "data": "menu"}]}]
            new_id = f"MER-{len(MERCHANTS)+1:03d}"
            MERCHANTS[new_id] = {
                "name": data["name"], "category": data["category"], "region": data.get("region", ""),
                "contact": data.get("contact", ""), "phone": data.get("phone", ""),
                "devices": 0, "status": "Active", "onboarded": "2026-02-24"
            }
            return [{"type": "text", "content": f"✅ **Merchant Created!**\n\n🆔 **{new_id}**\n🏪 {data['name']}\n📂 {data['category']} • 📍 {data.get('region','')}\n👤 {data.get('contact','')}",
                     "buttons": [{"text": "📋 View Merchants", "data": "view_all_merchants"}, {"text": "🏠 Menu", "data": "menu"}]}]

        return [{"type": "text", "content": "❌ Unknown form.", "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]

    # ── Merchants ──

    def _merchant_menu(self):
        active = sum(1 for m in MERCHANTS.values() if m["status"] == "Active")
        return [{"type": "text", "content": f"🏪 **Merchant Management**\n\n✅ Active: **{active}** merchants\n📱 Total devices: **{sum(m['devices'] for m in MERCHANTS.values())}**",
             "buttons": [
                 {"text": "📋 All Merchants", "data": "view_all_merchants"},
                 {"text": "➕ Add Merchant", "data": "add_merchant"},
                 {"text": "🏠 Menu", "data": "menu"},
             ]}]

    def _all_merchants(self):
        cards = []
        for mid, m in MERCHANTS.items():
            cards.append({
                "title": f"🏪 {m['name']} ({mid})",
                "subtitle": f"{m['category']} • {m['region']}",
                "fields": [f"Contact: **{m['contact']}**", f"Devices: **{m['devices']}**", f"Since: {m['onboarded']}"],
                "buttons": [{"text": "View Details", "data": f"merchant_detail_{mid}"}]
            })
        return [{"type": "cards", "content": "🏪 **All Merchants**", "cards": cards,
                 "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]

    def _merchant_detail(self, mid):
        m = MERCHANTS.get(mid)
        if not m: return [{"type": "text", "content": f"❌ Merchant {mid} not found.", "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]
        content = f"🏪 **{m['name']}** ({mid})\n\n| | |\n|---|---|\n| Category | {m['category']} |\n| Region | {m['region']} |\n| Contact | {m['contact']} |\n| Phone | {m['phone']} |\n| Devices | {m['devices']} |\n| Status | {m['status']} |\n| Onboarded | {m['onboarded']} |"
        return [{"type": "text", "content": content, "buttons": [{"text": "📋 All Merchants", "data": "view_all_merchants"}, {"text": "🏠 Menu", "data": "menu"}]}]

    # ── Reports ──

    def _reports_menu(self):
        total_txn = sum(r["count"] for r in TRANSACTIONS_DAILY.values())
        total_vol = sum(r["volume"] for r in TRANSACTIONS_DAILY.values())
        return [{"type": "text", "content": f"📊 **Reports**\n\n📅 Today:\n💳 **{total_txn:,}** transactions\n💰 **₹{total_vol:,.0f}** volume\n📈 **₹{total_vol//total_txn:,}** avg ticket",
             "buttons": [
                 {"text": "📈 Full Summary", "data": "daily_summary"},
                 *[{"text": f"📍 {r}", "data": f"region_report_{r}"} for r in TRANSACTIONS_DAILY],
                 {"text": "🏠 Menu", "data": "menu"},
             ]}]

    def _daily_summary(self):
        rows = ""
        for region, data in TRANSACTIONS_DAILY.items():
            rows += f"| {region} | {data['count']:,} | ₹{data['volume']:,.0f} | ₹{data['avg']:,} |\n"
        return [{"type": "text", "content": f"📈 **Daily Summary**\n\n| Region | Txns | Volume | Avg |\n|---|---|---|---|\n{rows}",
                 "buttons": [{"text": "📊 Reports", "data": "reports"}, {"text": "🏠 Menu", "data": "menu"}]}]

    def _region_report(self, region):
        data = TRANSACTIONS_DAILY.get(region)
        if not data: return [{"type": "text", "content": f"❌ No data for {region}.", "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]
        devices = [f"• {did}: {d['name']} ({d['status']})" for did, d in DEVICES.items() if d["region"] == region]
        return [{"type": "text", "content": f"📍 **{region}**\n\n💳 Txns: **{data['count']:,}**\n💰 Volume: **₹{data['volume']:,.0f}**\n📈 Avg: **₹{data['avg']:,}**\n\n📱 Devices:\n" + "\n".join(devices),
                 "buttons": [{"text": "📊 Reports", "data": "reports"}, {"text": "🏠 Menu", "data": "menu"}]}]

    # ── Alerts ──

    def _show_alerts(self):
        if not ALERTS:
            return [{"type": "text", "content": "✅ No active alerts!", "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]
        cards = []
        for a in ALERTS:
            icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(a["severity"], "⚪")
            cards.append({
                "title": f"{icon} {a['type']}", "subtitle": f"{a['device']} • {a['merchant']}",
                "fields": [f"Time: {a['time']}", f"Severity: **{a['severity'].upper()}**"],
                "buttons": [{"text": "✅ Acknowledge", "data": f"alert_ack_{a['id']}"}]
            })
        return [{"type": "cards", "content": f"🔔 **Alerts** ({len(ALERTS)})", "cards": cards,
                 "buttons": [{"text": "🏠 Menu", "data": "menu"}]}]

    def _ack_alert(self, aid):
        global ALERTS
        ALERTS = [a for a in ALERTS if a["id"] != aid]
        return [{"type": "text", "content": f"✅ Alert **{aid}** cleared.\n🔔 Remaining: **{len(ALERTS)}**",
                 "buttons": [{"text": "🔔 Alerts", "data": "alerts"}, {"text": "🏠 Menu", "data": "menu"}]}]

    # ── Help ──

    def _help_menu(self):
        return [{"type": "text", "content": "❓ **Help & FAQ**\n\nSelect a topic or type your question:",
                 "buttons": [
                     {"text": "🔄 Reset Device", "data": "faq_reset device"},
                     {"text": "💰 Settlement", "data": "faq_settlement"},
                     {"text": "🧻 Paper Roll", "data": "faq_paper roll"},
                     {"text": "📶 Connectivity", "data": "faq_connectivity"},
                     {"text": "🏠 Menu", "data": "menu"},
                 ]}]

    def _show_faq(self, key):
        answer = FAQ.get(key, "No FAQ entry found.")
        return [{"type": "text", "content": f"📖 **FAQ**\n\n{answer}", "buttons": [{"text": "❓ More FAQ", "data": "help"}, {"text": "🏠 Menu", "data": "menu"}]}]

    # ── NL Fallback (LLM Intent Classification → Route to Handler) ──

    def _nl_fallback(self, text):
        t = text.lower()

        # Quick regex — device ID mentioned directly
        match = re.search(r'pos-\d{4}', t, re.I)
        if match: return self._device_detail(match.group().upper())

        # LLM Intent Classification — ALL free text goes through this
        if is_ollama_running():
            intent = classify_intent(text)

            # Route to existing handlers based on classified intent
            INTENT_ROUTES = {
                "DEVICE":       self._device_menu,
                "ADD_DEVICE":   self._show_device_form,
                "MERCHANT":     self._merchant_menu,
                "ADD_MERCHANT": self._show_merchant_form,
                "REPORT":       self._reports_menu,
                "ALERT":        self._show_alerts,
                "HELP":         self._help_menu,
            }

            # If intent has a specific qualifier (city, ID, name, etc.), send to LLM for smart answer
            # Only use handler for generic/short queries like "reports", "devices", "alerts"
            words = text.strip().split()
            is_specific = len(words) >= 3  # "reports for delhi", "show me mumbai devices", etc.

            if intent in INTENT_ROUTES and not is_specific:
                return INTENT_ROUTES[intent]()

            # GENERAL intent — full LLM answer
            snapshot = build_data_snapshot(DEVICES, MERCHANTS, TRANSACTIONS_DAILY, ALERTS)
            ai_response = generate_answer(text, snapshot)

            if ai_response and not ai_response.startswith("⚠️"):
                return [{"type": "text", "content": f"🤖 **NexPOS AI**\n\n{ai_response}",
                         "buttons": [
                             {"text": "📱 Devices", "data": "device_status"},
                             {"text": "🏪 Merchants", "data": "merchants"},
                             {"text": "📊 Reports", "data": "reports"},
                             {"text": "🏠 Menu", "data": "menu"},
                         ]}]

        # Final fallback — Ollama not running
        return [{"type": "text", "content": "🤔 I'm not sure what you need. Pick an option:",
                 "buttons": [{"text": "📱 Devices", "data": "device_status"}, {"text": "🏪 Merchants", "data": "merchants"}, {"text": "📊 Reports", "data": "reports"}, {"text": "🔔 Alerts", "data": "alerts"}, {"text": "❓ Help", "data": "help"}]}]
