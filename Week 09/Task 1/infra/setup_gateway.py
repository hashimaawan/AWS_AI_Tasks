"""setup_gateway.py — expose the csbot-get-order-status Lambda as an MCP tool via an AgentCore Gateway."""
import json, os
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

REGION       = os.environ.get("AWS_REGION", "us-east-1")
LAMBDA_ARN   = os.environ["LAMBDA_ARN"]
GATEWAY_NAME = "csbot-gateway"

client = GatewayClient(region_name=REGION)

print(">> 1/3 Creating Cognito OAuth authorizer (~1 min)...")
cognito = client.create_oauth_authorizer_with_cognito(GATEWAY_NAME)

print(">> 2/3 Creating the gateway...")
gateway = client.create_mcp_gateway(
    name=GATEWAY_NAME,
    role_arn=None,                                  
    authorizer_config=cognito["authorizer_config"],
    enable_semantic_search=True,
)

print(">> 3/3 Registering the existing Lambda as an MCP tool target...")
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
    gateway=gateway,
    name="OrderTarget",
    target_type="lambda",
    target_payload={"lambdaArn": LAMBDA_ARN, "toolSchema": tool_schema},
    credentials=None,
)

def pick(obj, *keys):
    for k in keys:
        if isinstance(obj, dict) and k in obj: return obj[k]
        if hasattr(obj, k): return getattr(obj, k)
    return None

mcp_url = pick(gateway, "gatewayUrl", "mcp_url")
if not mcp_url and hasattr(gateway, "get_mcp_url"): mcp_url = gateway.get_mcp_url()

config = {
    "region": REGION,
    "gateway_id": pick(gateway, "gatewayId", "gateway_id"),
    "mcp_url": mcp_url,
    "cognito": cognito.get("client_info", cognito),
}
with open("gateway_config.json", "w") as f:
    json.dump(config, f, indent=2, default=str)

print("\n==== GATEWAY READY ====")
print(json.dumps(config, indent=2, default=str))
print("\n-- raw gateway --", gateway)
print("-- raw cognito --", json.dumps(cognito, indent=2, default=str))
