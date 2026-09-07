"""Register the returns Lambda as a 2nd MCP target on the existing gateway."""
import json
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

REGION     = "us-east-1"
GATEWAY_ID = "csbot-gateway-qsf83slwcq"
LAMBDA_ARN = "arn:aws:lambda:us-east-1:481719141347:function:csbot-get-return-policy"

client = GatewayClient(region_name=REGION)

tool_schema = {"inlinePayload": [{
    "name": "get_return_policy",
    "description": "Returns the return eligibility and refund policy for a customer's order. If no order ID is given, returns the general return policy.",
    "inputSchema": {
        "type": "object",
        "properties": {"order_id": {"type": "string", "description": "The customer's order ID, e.g. 1001. Optional."}},
        "required": [],
    },
}]}

target = client.create_mcp_gateway_target(
    gateway={"gatewayId": GATEWAY_ID},
    name="ReturnsTarget",
    target_type="lambda",
    target_payload={"lambdaArn": LAMBDA_ARN, "toolSchema": tool_schema},
    credentials=None,
)
print("✅ Returns target created:")
print(json.dumps(target, indent=2, default=str))
