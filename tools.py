"""
Tool definitions following the proposal's OpenAI Function Calling Schema.
Each tool maps to one REST endpoint. min_role controls RBAC.
"""

TOOL_DEFINITIONS = [
    {
        "name": "get_device_status",
        "description": "Returns current status, battery, last transaction time for a POS device.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Device ID like POS-4421"},
                "region": {"type": "string", "enum": ["MUM", "DEL", "BLR", "HYD"], "description": "Optional region filter"}
            },
            "required": ["device_id"]
        },
        "min_role": "viewer"
    },
    {
        "name": "list_devices",
        "description": "List all POS devices, optionally filtered by region or status.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "enum": ["MUM", "DEL", "BLR", "HYD"]},
                "status": {"type": "string", "enum": ["online", "offline", "maintenance", "disabled"]}
            }
        },
        "min_role": "viewer"
    },
    {
        "name": "get_report",
        "description": "Get settlement report for a date and/or region.",
        "parameters": {
            "type": "object",
            "properties": {
                "report_type": {"type": "string", "enum": ["settlement"], "default": "settlement"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "region": {"type": "string", "enum": ["MUM", "DEL", "BLR", "HYD"]}
            }
        },
        "min_role": "viewer"
    },
    {
        "name": "get_transactions",
        "description": "Get recent transactions, optionally for a specific device.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Filter by device ID"},
                "days": {"type": "integer", "default": 7, "description": "Look back N days"},
                "limit": {"type": "integer", "default": 10, "description": "Max results"}
            }
        },
        "min_role": "viewer"
    },
    {
        "name": "search_faq",
        "description": "Search the knowledge base / FAQ for POS-related questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        },
        "min_role": "viewer"
    },
    {
        "name": "get_user_activity",
        "description": "Get user activity logs (logins, actions) for today.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD"}
            }
        },
        "min_role": "manager"
    },
    {
        "name": "add_device",
        "description": "Register a new POS device to a merchant and region.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "New device ID (POS-XXXX format)"},
                "merchant_id": {"type": "string", "description": "Merchant ID (MER-XXXX)"},
                "region": {"type": "string", "enum": ["MUM", "DEL", "BLR", "HYD"]}
            },
            "required": ["device_id", "merchant_id", "region"]
        },
        "min_role": "admin"
    },
    {
        "name": "disable_device",
        "description": "Disable/deactivate a POS device.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "reason": {"type": "string", "description": "Reason for disabling"}
            },
            "required": ["device_id"]
        },
        "min_role": "admin"
    },
    {
        "name": "create_merchant",
        "description": "Onboard a new merchant. Requires: name, merchant_id, category, region, address, contact.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "merchant_id": {"type": "string"},
                "category": {"type": "string", "enum": ["restaurant", "retail", "food_court", "pharmacy", "grocery"]},
                "region": {"type": "string", "enum": ["MUM", "DEL", "BLR", "HYD"]},
                "address": {"type": "string"},
                "contact": {"type": "string"}
            },
            "required": ["name", "merchant_id", "category", "region", "address", "contact"]
        },
        "min_role": "admin"
    },
    {
        "name": "list_tenants",
        "description": "List all tenants in the platform (super admin only).",
        "parameters": {"type": "object", "properties": {}},
        "min_role": "super_admin"
    },
    {
        "name": "update_tenant",
        "description": "Update tenant configuration (super admin only).",
        "parameters": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "region": {"type": "string"},
                "status": {"type": "string", "enum": ["active", "suspended"]}
            },
            "required": ["tenant_id"]
        },
        "min_role": "super_admin"
    }
]

# Role hierarchy for RBAC
ROLE_HIERARCHY = {
    "viewer": 0,
    "manager": 1,
    "admin": 2,
    "super_admin": 3
}

def get_tools_for_role(role: str) -> list:
    """Filter tool definitions by user's role — prompt-level RBAC (Layer 1)."""
    role_level = ROLE_HIERARCHY.get(role, 0)
    return [t for t in TOOL_DEFINITIONS if ROLE_HIERARCHY.get(t["min_role"], 0) <= role_level]

def validate_tool_call(tool_name: str, role: str) -> bool:
    """Gateway-level RBAC (Layer 2) — verify tool call is permitted for role."""
    for t in TOOL_DEFINITIONS:
        if t["name"] == tool_name:
            return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(t["min_role"], 0)
    return False
