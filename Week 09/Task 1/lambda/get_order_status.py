"""
get_order_status.py — Task 1 order-lookup Lambda (csbot-get-order-status).

Deployed in AWS Lambda (Python 3.12), exposed as an MCP tool via the AgentCore Gateway.
Tags on the function: owner=hashim, environment=sandbox-ha (required by the org SCP).
"""
import json

# Mock order data — hardcoded for the demo, no DynamoDB needed.
MOCK_ORDERS = {
    "1001": {"status": "Shipped",    "carrier": "FedEx", "eta": "2026-09-05",             "items": "Wireless Headphones x1"},
    "1002": {"status": "Processing", "carrier": None,    "eta": "2026-09-09",             "items": "Mechanical Keyboard x1"},
    "1003": {"status": "Delivered",  "carrier": "UPS",   "eta": "2026-08-28 (delivered)", "items": "USB-C Cable x2"},
}


def _get_order_status(order_id):
    order = MOCK_ORDERS.get(str(order_id).strip())
    if not order:
        return (f"I couldn't find an order with ID '{order_id}'. "
                f"Please double-check the order number.")
    carrier = f" via {order['carrier']}" if order["carrier"] else ""
    return (f"Order {order_id}: {order['items']}. "
            f"Status: {order['status']}{carrier}. "
            f"Estimated delivery: {order['eta']}.")


def lambda_handler(event, context):
    # AgentCore Gateway passes the tool name (prefixed with the target name) via the
    # client context. It's empty in a plain console test, hence the fallback.
    tool_name = ""
    cc = getattr(context, "client_context", None)
    if cc and getattr(cc, "custom", None):
        tool_name = cc.custom.get("bedrockAgentCoreToolName", "")

    # Gateway delivers the tool's input-schema properties directly on the event.
    if "get_order_status" in tool_name or (not tool_name and "order_id" in event):
        message = _get_order_status(event.get("order_id", ""))
        return {"statusCode": 200, "body": json.dumps({"result": message})}

    return {"statusCode": 200, "body": json.dumps({"error": f"Unknown tool: {tool_name or 'none'}"})}
