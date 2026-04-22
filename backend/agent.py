import json
import anthropic
from backend.import_data import (
    get_all_vendors, add_vendor,
    get_all_orders, create_order, update_order_status,
    get_inventory, update_inventory,
    get_history, save_message,
)

client = anthropic.Anthropic()
MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """You are an intelligent procurement assistant for a company.
You help users manage vendors, purchase orders, and inventory.

You have access to the following tools:
- list_vendors: View all registered vendors
- add_vendor: Register a new vendor
- list_orders: View purchase orders (optionally filtered by status)
- create_order: Create a new purchase order
- update_order_status: Approve, reject, or mark orders as delivered
- check_inventory: View current inventory levels
- update_inventory: Update stock quantities

Always be concise, professional, and proactive. When inventory is low, flag it.
When asked to take an action, confirm what you did after completing it.
Format monetary values as currency (e.g., $1,234.56) and use clear tabular descriptions when listing data."""

TOOLS = [
    {
        "name": "list_vendors",
        "description": "Retrieve all registered vendors with their details and ratings.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_vendor",
        "description": "Register a new vendor in the system.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Vendor company name"},
                "category": {"type": "string", "description": "Category (e.g., Office, Electronics, Logistics)"},
                "contact_email": {"type": "string", "description": "Primary contact email"},
                "phone": {"type": "string", "description": "Contact phone number"},
            },
            "required": ["name", "category", "contact_email", "phone"],
        },
    },
    {
        "name": "list_orders",
        "description": "List purchase orders. Optionally filter by status: pending, approved, delivered, rejected.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "approved", "delivered", "rejected"],
                    "description": "Filter orders by status (optional)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "create_order",
        "description": "Create a new purchase order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "integer", "description": "ID of the vendor"},
                "item": {"type": "string", "description": "Item or product name"},
                "quantity": {"type": "integer", "description": "Quantity to order"},
                "unit_price": {"type": "number", "description": "Price per unit in USD"},
            },
            "required": ["vendor_id", "item", "quantity", "unit_price"],
        },
    },
    {
        "name": "update_order_status",
        "description": "Update the status of a purchase order (approve, reject, or mark delivered).",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer", "description": "ID of the purchase order"},
                "status": {
                    "type": "string",
                    "enum": ["approved", "rejected", "delivered"],
                    "description": "New status for the order",
                },
            },
            "required": ["order_id", "status"],
        },
    },
    {
        "name": "check_inventory",
        "description": "Check current inventory levels. Set low_stock_only=true to see only items below reorder level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "low_stock_only": {
                    "type": "boolean",
                    "description": "If true, only return items at or below reorder level",
                }
            },
            "required": [],
        },
    },
    {
        "name": "update_inventory",
        "description": "Update the quantity of an inventory item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "Exact name of the inventory item"},
                "quantity": {"type": "integer", "description": "New quantity in stock"},
            },
            "required": ["item_name", "quantity"],
        },
    },
]


def execute_tool(name: str, tool_input: dict) -> str:
    try:
        if name == "list_vendors":
            vendors = get_all_vendors()
            if not vendors:
                return "No vendors registered yet."
            return json.dumps(vendors, indent=2)

        elif name == "add_vendor":
            vendor = add_vendor(**tool_input)
            return json.dumps(vendor, indent=2)

        elif name == "list_orders":
            status = tool_input.get("status")
            orders = get_all_orders(status)
            if not orders:
                return f"No orders found{' with status: ' + status if status else ''}."
            return json.dumps(orders, indent=2)

        elif name == "create_order":
            order = create_order(**tool_input)
            return json.dumps(order, indent=2)

        elif name == "update_order_status":
            result = update_order_status(tool_input["order_id"], tool_input["status"])
            if not result:
                return f"Order #{tool_input['order_id']} not found."
            return json.dumps(result, indent=2)

        elif name == "check_inventory":
            low_stock_only = tool_input.get("low_stock_only", False)
            items = get_inventory(low_stock_only)
            if not items:
                return "No inventory items found."
            return json.dumps(items, indent=2)

        elif name == "update_inventory":
            result = update_inventory(tool_input["item_name"], tool_input["quantity"])
            if not result:
                return f"Item '{tool_input['item_name']}' not found in inventory."
            return json.dumps(result, indent=2)

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Error executing {name}: {str(e)}"


async def chat(session_id: str, user_message: str) -> str:
    # Persist user message
    save_message(session_id, "user", user_message)

    # Build message history for context
    history = get_history(session_id, limit=20)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    # Agentic loop
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Collect all content blocks for the assistant turn
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn":
            # Extract text reply
            reply = next(
                (block.text for block in response.content if block.type == "text"),
                "I've completed the requested action."
            )
            save_message(session_id, "assistant", reply)
            return reply

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason — return whatever text we have
        reply = next(
            (block.text for block in response.content if block.type == "text"),
            "An unexpected issue occurred."
        )
        save_message(session_id, "assistant", reply)
        return reply
