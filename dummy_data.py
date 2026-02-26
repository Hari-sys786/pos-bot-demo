"""
Dummy POS Management Data — simulates the Java/Spring Boot REST API layer.
All data is in-memory. This replaces the real API calls described in the proposal.
"""
import random
from datetime import datetime, timedelta

# ── Devices ──────────────────────────────────────────────────────────────────
DEVICES = {
    "POS-4421": {"merchant": "Cafe Blue", "region": "MUM", "status": "online", "battery": 78, "last_txn": "2026-02-24T15:42:00", "model": "Verifone V240m"},
    "POS-3301": {"merchant": "Green Mart", "region": "DEL", "status": "offline", "battery": 12, "last_txn": "2026-02-23T09:15:00", "model": "PAX A920"},
    "POS-5510": {"merchant": "Spice House", "region": "BLR", "status": "online", "battery": 95, "last_txn": "2026-02-24T16:01:00", "model": "Ingenico Move5000"},
    "POS-6622": {"merchant": "BookNook", "region": "HYD", "status": "maintenance", "battery": 45, "last_txn": "2026-02-22T11:30:00", "model": "Verifone V240m"},
    "POS-7788": {"merchant": "FreshBites", "region": "MUM", "status": "online", "battery": 62, "last_txn": "2026-02-24T14:55:00", "model": "PAX A920"},
    "POS-9999": {"merchant": "QuickStop", "region": "DEL", "status": "online", "battery": 88, "last_txn": "2026-02-24T16:10:00", "model": "Ingenico Move5000"},
}

# ── Merchants ────────────────────────────────────────────────────────────────
MERCHANTS = {
    "MER-0098": {"name": "Cafe Blue", "category": "restaurant", "region": "MUM", "address": "MG Road, Mumbai", "contact": "+91-9876543210", "status": "active", "devices": ["POS-4421"]},
    "MER-0112": {"name": "Green Mart", "category": "retail", "region": "DEL", "address": "Connaught Place, Delhi", "contact": "+91-9876543211", "status": "active", "devices": ["POS-3301"]},
    "MER-0205": {"name": "Spice House", "category": "restaurant", "region": "BLR", "address": "Church Street, Bangalore", "contact": "+91-9876543212", "status": "active", "devices": ["POS-5510"]},
    "MER-0301": {"name": "BookNook", "category": "retail", "region": "HYD", "address": "Banjara Hills, Hyderabad", "contact": "+91-9876543213", "status": "active", "devices": ["POS-6622"]},
    "MER-0455": {"name": "FreshBites", "category": "food_court", "region": "MUM", "address": "Andheri West, Mumbai", "contact": "+91-9876543214", "status": "active", "devices": ["POS-7788"]},
}

# ── Transactions (dummy recent) ─────────────────────────────────────────────
def generate_transactions(device_id=None, days=7, limit=20):
    txn_types = ["sale", "refund", "void"]
    statuses = ["success", "failed", "pending"]
    results = []
    now = datetime.now()
    devices = [device_id] if device_id else list(DEVICES.keys())
    for _ in range(limit):
        d = random.choice(devices)
        results.append({
            "txn_id": f"TXN-{random.randint(100000, 999999)}",
            "device_id": d,
            "merchant": DEVICES[d]["merchant"],
            "type": random.choice(txn_types),
            "amount": round(random.uniform(50, 15000), 2),
            "currency": "INR",
            "status": random.choices(statuses, weights=[85, 10, 5])[0],
            "timestamp": (now - timedelta(hours=random.randint(0, days * 24))).isoformat()[:19],
        })
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results

# ── Settlement Reports ───────────────────────────────────────────────────────
def generate_settlement_report(date_str=None, region=None):
    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    regions = [region] if region else ["MUM", "DEL", "BLR", "HYD"]
    report = {"date": date_str, "regions": {}}
    for r in regions:
        total = round(random.uniform(50000, 500000), 2)
        report["regions"][r] = {
            "total_amount": total,
            "total_txns": random.randint(100, 2000),
            "successful_txns": random.randint(80, 1800),
            "failed_txns": random.randint(5, 50),
            "refunds": round(random.uniform(1000, 20000), 2),
            "net_settlement": round(total * 0.97, 2),
        }
    return report

# ── User Activity Logs ───────────────────────────────────────────────────────
USER_ACTIVITY = [
    {"user": "rahul.sharma", "action": "login", "timestamp": "2026-02-24T09:00:00", "ip": "192.168.1.45"},
    {"user": "priya.patel", "action": "login", "timestamp": "2026-02-24T09:15:00", "ip": "192.168.1.78"},
    {"user": "amit.kumar", "action": "export_report", "timestamp": "2026-02-24T10:30:00", "ip": "192.168.1.92"},
    {"user": "rahul.sharma", "action": "add_device", "timestamp": "2026-02-24T11:00:00", "ip": "192.168.1.45"},
    {"user": "priya.patel", "action": "view_dashboard", "timestamp": "2026-02-24T12:00:00", "ip": "192.168.1.78"},
    {"user": "admin", "action": "create_merchant", "timestamp": "2026-02-24T14:00:00", "ip": "10.0.0.1"},
]

# ── FAQ / Knowledge Base ─────────────────────────────────────────────────────
FAQ = [
    {"q": "How do I reset a POS device?", "a": "Press and hold the power button for 10 seconds. If issue persists, contact support with the device ID."},
    {"q": "What does 'maintenance' status mean?", "a": "The device is undergoing scheduled maintenance or firmware update. It will be back online within 2-4 hours."},
    {"q": "How to process a refund?", "a": "Go to Transactions > Find the original sale > Click Refund. Refunds are processed within 24 hours."},
    {"q": "What regions are supported?", "a": "Currently: Mumbai (MUM), Delhi (DEL), Bangalore (BLR), and Hyderabad (HYD)."},
    {"q": "How to add a new merchant?", "a": "Admin role required. Go to Merchants > Add New. Fill in: name, merchant ID, category, address, region, contact, and tax ID."},
    {"q": "What is the settlement cycle?", "a": "Settlements are processed daily at T+1. Reports are available by 8 AM the next business day."},
    {"q": "POS device battery draining fast", "a": "Check: 1) Background apps running, 2) Screen brightness, 3) WiFi vs cellular mode. If battery < 20% and dropping fast, schedule a device swap."},
]

# ── Tenants (for super admin) ────────────────────────────────────────────────
TENANTS = {
    "tenant-001": {"name": "PayQuick India", "region": "IN", "active_merchants": 156, "active_devices": 312, "status": "active"},
    "tenant-002": {"name": "SwiftPay EU", "region": "EU", "active_merchants": 89, "active_devices": 178, "status": "active"},
    "tenant-003": {"name": "PayFast SEA", "region": "SEA", "active_merchants": 45, "active_devices": 90, "status": "suspended"},
}


# ── API Simulation Functions ─────────────────────────────────────────────────
def api_get_device_status(device_id, region=None):
    dev = DEVICES.get(device_id)
    if not dev:
        return {"error": f"Device {device_id} not found", "status_code": 404}
    if region and dev["region"] != region:
        return {"error": f"Device {device_id} not in region {region}", "status_code": 404}
    return {"device_id": device_id, **dev}

def api_list_devices(region=None, status=None):
    results = []
    for did, dev in DEVICES.items():
        if region and dev["region"] != region:
            continue
        if status and dev["status"] != status:
            continue
        results.append({"device_id": did, **dev})
    return results

def api_get_report(report_type="settlement", date=None, region=None):
    return generate_settlement_report(date, region)

def api_get_transactions(device_id=None, days=7, limit=10):
    return generate_transactions(device_id, days, limit)

def api_search_faq(query):
    query_lower = query.lower()
    matches = []
    for faq in FAQ:
        if any(word in faq["q"].lower() or word in faq["a"].lower() for word in query_lower.split()):
            matches.append(faq)
    return matches[:3] if matches else [{"q": "No results", "a": "Try rephrasing your question or contact support."}]

def api_add_device(device_id, merchant_id, region):
    if device_id in DEVICES:
        return {"error": f"Device {device_id} already exists", "status_code": 409}
    DEVICES[device_id] = {"merchant": MERCHANTS.get(merchant_id, {}).get("name", "Unknown"), "region": region, "status": "online", "battery": 100, "last_txn": "N/A", "model": "PAX A920"}
    return {"success": True, "message": f"Device {device_id} added to {region}"}

def api_disable_device(device_id, reason="Admin request"):
    if device_id not in DEVICES:
        return {"error": f"Device {device_id} not found", "status_code": 404}
    DEVICES[device_id]["status"] = "disabled"
    return {"success": True, "message": f"Device {device_id} disabled. Reason: {reason}"}

def api_create_merchant(name, merchant_id, category, region, address, contact):
    if merchant_id in MERCHANTS:
        return {"error": f"Merchant {merchant_id} already exists", "status_code": 409}
    MERCHANTS[merchant_id] = {"name": name, "category": category, "region": region, "address": address, "contact": contact, "status": "active", "devices": []}
    return {"success": True, "message": f"Merchant '{name}' ({merchant_id}) created in {region}"}

def api_get_user_activity(date=None):
    return USER_ACTIVITY

def api_get_transaction_summary():
    """Per-device transaction counts and volumes."""
    summary = {}
    for did, dev in DEVICES.items():
        count = random.randint(20, 500)
        volume = round(random.uniform(10000, 200000), 2)
        summary[did] = {
            "device_id": did,
            "merchant": dev["merchant"],
            "region": dev["region"],
            "txn_count": count,
            "total_volume": volume,
            "avg_txn": round(volume / count, 2),
        }
    # Sort by txn_count desc
    return sorted(summary.values(), key=lambda x: x["txn_count"], reverse=True)


def api_list_tenants():
    return [{"tenant_id": tid, **t} for tid, t in TENANTS.items()]

def api_update_tenant(tenant_id, **kwargs):
    if tenant_id not in TENANTS:
        return {"error": f"Tenant {tenant_id} not found", "status_code": 404}
    TENANTS[tenant_id].update(kwargs)
    return {"success": True, "message": f"Tenant {tenant_id} updated"}
