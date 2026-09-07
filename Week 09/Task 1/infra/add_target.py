"""Register the Lambda as an MCP target on the EXISTING gateway."""
import json, os
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

REGION     = "us-east-1"
GATEWAY_ID = "csbot-gateway-qsf83slwcq"
LAMBDA_ARN = os.environ["LAMBDA_ARN"]

client = GatewayClient(region_name=REGION)

tool_schema = {"inlinePayload": [{
    "name": "get_order_status",
    "description": "Retrieves the status, carrier, estimated delivery date, and items for a customer's order given the order ID.",
    "inputSchema": {
        "type": "object",
        "properties": {"order_id": {"type": "string", "description": "The customer's numeric order ID, e.g. 1001."}},
        "required": ["order_id"],
    },
}]}

target = client.create_mcp_gateway_target(
    gateway={"gatewayId": GATEWAY_ID},
    name="OrderTarget",
    target_type="lambda",
    target_payload={"lambdaArn": LAMBDA_ARN, "toolSchema": tool_schema},
    credentials=None,
)
print("✅ Target created:")
print(json.dumps(target, indent=2, default=str))
