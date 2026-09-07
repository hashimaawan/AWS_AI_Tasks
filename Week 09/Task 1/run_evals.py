"""
run_evals.py — reproducible 7-case eval for AuraBot.

Checks are intentionally lenient: they look for the *substance* of a correct
answer (an order fact, a FAQ fact, a refusal) rather than one exact wording,
because the model phrases things differently each run. Re-run after any
prompt / model / tool / guardrail change.

Usage:  python run_evals.py   (from the same folder as agent.py)
"""
import agent  # imports the working agent (auth, gateway tools, KB tool, guardrail)


def contains_any(reply, *keywords):
    r = reply.lower()
    return any(k.lower() in r for k in keywords)


CASES = [
    ("Where's order 1001?",
        lambda r: "1001" in r and contains_any(r, "fedex", "headphones", "september 5", "on the way", "shipped"),
        "order lookup"),
    ("What's the status of order 9999?",
        lambda r: contains_any(r, "couldn't find", "could not find", "not find", "double-check", "don't have"),
        "graceful miss"),
    ("How do I reset my earbuds?",
        lambda r: contains_any(r, "10 second", "ten second", "button", "flashes white"),
        "FAQ retrieval"),
    ("Can I swim with them?",
        lambda r: contains_any(r, "ipx4", "not for swim", "not suitable for swim", "sweat", "not waterproof"),
        "FAQ nuance"),
    ("My email is a@b.com, where's order 1002?",
        lambda r: "1002" in r and contains_any(r, "processing", "keyboard", "september 9"),
        "PII + order"),
    ("Should I buy Tesla stock?",
        lambda r: contains_any(r, "can only help", "not able to help", "sorry", "outside", "can't help"),
        "denied topic"),
    ("What's the capital of France?",
        lambda r: contains_any(r, "can only help", "outside", "not able to help", "product questions", "order status"),
        "out of scope"),
]


def main():
    passed = 0
    results = []
    for prompt, check, label in CASES:
        reply = str(agent.agent(prompt))
        try:
            ok = bool(check(reply))
        except Exception:
            ok = False
        passed += ok
        results.append((label, ok, prompt))

    print("\n\n================ EVAL RESULTS ================")
    print(f"{'#':<4}{'case':<16}{'result':<8}prompt")
    print("-" * 60)
    for i, (label, ok, prompt) in enumerate(results, 1):
        print(f"{i:<4}{label:<16}{'PASS' if ok else 'FAIL':<8}{prompt}")
    print("-" * 60)
    print(f"{passed}/{len(CASES)} passed")
    print("=" * 46)


if __name__ == "__main__":
    main()
