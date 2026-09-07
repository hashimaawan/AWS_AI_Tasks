"""
supervisor.py — Task 2: multi-agent supervisor routing (Option A: agents-as-tools).

Three agents:
  • Order sub-agent    -> ONLY get_order_status (+ FAQ knowledge base)
  • Returns sub-agent  -> ONLY get_return_policy
  • Supervisor         -> routes to the right specialist, or DECLINES when unsure.

Clean output: sub-agents run silently; you see a "routing to X" line and one final answer.
Reuses the Task 1 Gateway, Cognito, KB, and Guardrail.

Run interactively:  python supervisor.py chat
Import for eval:     import supervisor
"""
import os
import boto3
import requests
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# ---- Observability: explicit OpenTelemetry console span export ----
# Prints a trace tree (supervisor -> sub-agent -> tool, with timings) to the
# terminal, so we have an observability artifact without CloudWatch/Runtime.
import os as _os
if _os.environ.get("CSBOT_TRACE", "1") == "1":
    from opentelemetry import trace as _trace
    from opentelemetry.sdk.trace import TracerProvider as _TP
    from opentelemetry.sdk.trace.export import (
        SimpleSpanProcessor as _SSP,
        ConsoleSpanExporter as _CSE,
        
    )
    from opentelemetry.sdk.resources import Resource as _Res
    _provider = _TP(resource=_Res.create({"service.name": "csbot-supervisor"}))

    # If CSBOT_TRACE_FILE is set, write spans (one JSON per line) to that file
    # instead of flooding the console. Otherwise, print to console as before.
    _trace_file = _os.environ.get("CSBOT_TRACE_FILE")
    if _trace_file:
        _fh = open(_trace_file, "a")
        _exporter = _CSE(out=_fh)          # ConsoleSpanExporter writes formatted JSON
    else:
        _exporter = _CSE()
    _provider.add_span_processor(_SSP(_exporter))
    _trace.set_tracer_provider(_provider)
    _os.environ.setdefault("STRANDS_OTEL_ENABLE_CONSOLE_EXPORT", "true")

REGION            = os.environ.get("AWS_REGION", "us-east-1")
MCP_URL           = os.environ.get("MCP_URL", "https://csbot-gateway-qsf83slwcq.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp")
USER_POOL_ID      = os.environ.get("USER_POOL_ID", "us-east-1_zUkl0Gxco")
CLIENT_ID         = os.environ.get("CLIENT_ID", "79tdv9bb7v57tneqvrtabin34j")
COGNITO_DOMAIN    = os.environ.get("COGNITO_DOMAIN", "agentcore-d4992ab7")
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "3BVCAA2SUV")
GUARDRAIL_ID      = os.environ.get("GUARDRAIL_ID", "dx70nu28renv")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")
MODEL_ID          = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")


def get_access_token():
    cog = boto3.client("cognito-idp", region_name=REGION)
    d = cog.describe_user_pool_client(UserPoolId=USER_POOL_ID, ClientId=CLIENT_ID)["UserPoolClient"]
    scope = " ".join(d.get("AllowedOAuthScopes", []))
    print(f">> Auth: requesting token (scope: {scope or 'none'})...")
    url = f"https://{COGNITO_DOMAIN}.auth.{REGION}.amazoncognito.com/oauth2/token"
    r = requests.post(url, data={"grant_type": "client_credentials", "client_id": CLIENT_ID,
                                 "client_secret": d["ClientSecret"], "scope": scope},
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


_kb = boto3.client("bedrock-agent-runtime", region_name=REGION)


@tool
def search_faq(question: str) -> str:
    """Search the AuraBuds Pro product FAQ knowledge base (setup, battery, warranty, etc.)."""
    r = _kb.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": question},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
    )
    chunks = [x["content"]["text"] for x in r.get("retrievalResults", [])]
    return "\n\n".join(chunks) if chunks else "No matching FAQ entry was found."


model = BedrockModel(
    model_id=MODEL_ID, region_name=REGION,
    guardrail_id=GUARDRAIL_ID, guardrail_version=GUARDRAIL_VERSION,
    guardrail_trace="enabled", guardrail_redact_input=True, guardrail_redact_output=True,
)


def _find_tool(tools, needle):
    for t in tools:
        name = getattr(t, "tool_name", getattr(t, "name", ""))
        if needle in name:
            return t
    return None


_token = get_access_token()


def _transport():
    return streamablehttp_client(MCP_URL, headers={"Authorization": f"Bearer {_token}"})


mcp_client = MCPClient(_transport)
mcp_client.start()

#Tools Listing

_all_tools = mcp_client.list_tools_sync()
_order_tool   = _find_tool(_all_tools, "get_order_status")
_returns_tool = _find_tool(_all_tools, "get_return_policy")
print("Gateway tools:", [getattr(t, "tool_name", getattr(t, "name", str(t))) for t in _all_tools])

# Sub-agents run SILENTLY (callback_handler=None) so only the supervisor's final
# answer prints. Fresh context per call is enforced in the wrappers below.
order_agent = Agent(
    model=model, callback_handler=None,
    system_prompt=(
        "You are the Order specialist for AuraBuds Pro. You handle order status, shipping, "
        "delivery, and product FAQ questions. Use get_order_status for order questions "
        "(ask for the order ID if it is missing — never assume one). Use search_faq for "
        "product questions. Keep replies short and polite."
    ),
    tools=[_order_tool, search_faq],
)

returns_agent = Agent(
    model=model, callback_handler=None,
    system_prompt=(
        "You are the Returns specialist for AuraBuds Pro. You handle return eligibility and "
        "refund questions. Use get_return_policy (pass the order ID if the customer gave one; "
        "it is optional — never assume one). Keep replies short and polite."
    ),
    tools=[_returns_tool],
)


LAST_ROUTE = {"who": None}


@tool
def ask_order_agent(customer_message: str) -> str:
    """Route order status, shipping, delivery, or product-FAQ questions here.

    Args:
        customer_message: The customer's message, verbatim.
    """
    print("   \u2192 routing to ORDER agent")
    LAST_ROUTE["who"] = "order"
    order_agent.messages = []          # fresh context: no bleed between questions
    return str(order_agent(customer_message))


@tool
def ask_returns_agent(customer_message: str) -> str:
    """Route return eligibility or refund questions here.

    Args:
        customer_message: The customer's message, verbatim.
    """
    print("   \u2192 routing to RETURNS agent")
    LAST_ROUTE["who"] = "returns"
    returns_agent.messages = []        # fresh context: no bleed between questions
    return str(returns_agent(customer_message))


supervisor = Agent(
    model=model, callback_handler=None,
    system_prompt=(
        "You are a customer-support supervisor for AuraBuds Pro. Read each customer message "
        "and route it to exactly ONE specialist:\n"
        "- ask_order_agent: order status, shipping, delivery, or product/how-to questions.\n"
        "- ask_returns_agent: returns, return eligibility, or refunds.\n\n"
        "Rules:\n"
        "- Call exactly one specialist and return their answer to the customer.\n"
        "- If the message clearly fits neither, OR you cannot confidently decide which "
        "specialist it belongs to, DO NOT guess and DO NOT call a tool. Reply: 'I'm not sure "
        "whether this is an order or a returns question. Could you tell me a bit more about "
        "what you need help with?'\n"
        "- Never answer order or returns questions yourself; always route."
    ),
    tools=[ask_order_agent, ask_returns_agent],
)


def chat_loop():
    print("\nSupervisor ready. Ask an order or returns question. Type 'quit' to exit.")
    while True:
        try:
            msg = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"quit", "exit", ""}:
            break
        supervisor.messages = []       # each conversation starts clean
        LAST_ROUTE["who"] = None
        result = supervisor(msg)
        print(f"\nSupervisor: {result}\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        chat_loop()
    else:
        print("\nSupervisor ready. Run 'python supervisor.py chat' to talk to it, "
              "or 'python run_routing_evals.py' for the routing eval.")
