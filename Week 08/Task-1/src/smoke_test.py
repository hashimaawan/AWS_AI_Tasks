import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")
resp = client.converse(
    modelId="anthropic.claude-3-haiku-20240307-v1:0",
    messages=[{"role": "user", "content": [{"text": "Say hello in five words."}]}],
    inferenceConfig={"maxTokens": 50, "temperature": 0},
)
print("Reply:", resp["output"]["message"]["content"][0]["text"])
print("Usage:", resp["usage"])
print("Server latency ms:", resp["metrics"]["latencyMs"])