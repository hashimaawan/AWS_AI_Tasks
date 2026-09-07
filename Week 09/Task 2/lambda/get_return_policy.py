"""
get_return_policy.py — Task 2 returns/refund Lambda (csbot-get-return-policy).

Deployed in AWS Lambda (Python 3.12), exposed as a SECOND MCP tool (ReturnsTarget)
on the same AgentCore Gateway. Tags: owner=hashim, environment=sandbox-ha.

Note: order_id is OPTIONAL here (unlike the order tool) — "what's your return policy?"
is a valid question with no order.
"""
import json

# Mock return/refund data, keyed by order ID — hardcoded for the demo.
MOCK_RETURNS = {
    "1001": ("Order 1001 is eligible for return. It was delivered 2 days ago — within the "
             "30-day window — and is unopened. You'll receive a full refund to your original "
             "payment method once we receive it."),
    "1002": ("Order 1002 is still processing and hasn't shipped yet, so there's nothing to "
             "return. If you'd like to cancel before it ships, we can do that for a full refund."),
    "1003": ("Order 1003 is not eligible for return. It was delivered 40 days ago, which is "
             "past our 30-day return window."),
}

GENERAL_POLICY = ("Return policy: items can be returned within 30 days of delivery if unopened "
                  "and in original condition. Refunds go to the original payment method within "
                  "5-7 business days of us receiving the item. Final-sale items and opened earbuds "
                  "(for hygiene reasons) are not returnable.")


def _get_return_policy(order_id):
    order_id = str(order_id).strip()
    if not order_id:
        return GENERAL_POLICY
    return MOCK_RETURNS.get(
        order_id,
        f"I couldn't find an order with ID '{order_id}'. Here's our general policy: {GENERAL_POLICY}",
    )


def lambda_handler(event, context):
    tool_name = ""
    cc = getattr(context, "client_context", None)
    if cc and getattr(cc, "custom", None):
        tool_name = cc.custom.get("bedrockAgentCoreToolName", "")

    if "get_return_policy" in tool_name or not tool_name:
        message = _get_return_policy(event.get("order_id", ""))
        return {"statusCode": 200, "body": json.dumps({"result": message})}

    return {"statusCode": 200, "body": json.dumps({"error": f"Unknown tool: {tool_name or 'none'}"})}
