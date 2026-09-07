"""
run_routing_evals.py — routing scorecard for the Task 2 supervisor.

For each of the 6 required conversations it records which specialist the
supervisor reached (order / returns / declined) and compares against what
we expect. For the 2 ambiguous cases the "expected" is 'declined' — the
supervisor should ask for clarification rather than guess.

Usage:  python run_routing_evals.py   (same folder as supervisor.py)
"""
import supervisor as S

# (prompt, expected_route, kind)
CASES = [
    ("Where's order 1001?",              "order",    "clear-order"),
    ("What's the status of order 1003?", "order",    "clear-order"),
    ("Can I return order 1001?",         "returns",  "clear-returns"),
    ("I want a refund for order 1003",   "returns",  "clear-returns"),
    ("I have a problem with order 1002", "declined", "ambiguous"),
    ("Something's wrong with my earbuds","declined", "ambiguous"),
]


def route_of(prompt):
    """Run one message through the supervisor and report which specialist it reached."""
    S.supervisor.messages = []
    S.LAST_ROUTE["who"] = None
    _ = S.supervisor(prompt)          # sub-agents are silent; wrappers set LAST_ROUTE
    who = S.LAST_ROUTE["who"]
    return who if who else "declined"  # no specialist called => it declined/clarified


def main():
    passed = 0
    rows = []
    for prompt, expected, kind in CASES:
        actual = route_of(prompt)
        ok = (actual == expected)
        passed += ok
        rows.append((kind, expected, actual, ok, prompt))

    print("\n\n============== ROUTING SCORECARD ==============")
    print(f"{'kind':<15}{'expected':<10}{'actual':<10}{'result':<8}prompt")
    print("-" * 78)
    for kind, expected, actual, ok, prompt in rows:
        print(f"{kind:<15}{expected:<10}{actual:<10}{'PASS' if ok else 'FAIL':<8}{prompt}")
    print("-" * 78)
    print(f"{passed}/{len(CASES)} routed as expected")
    print("=" * 46)
    print("Note: ambiguous cases 'pass' when the supervisor DECLINES (asks to clarify)\n"
          "rather than guessing a specialist.")


if __name__ == "__main__":
    main()
