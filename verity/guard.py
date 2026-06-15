"""Overconfidence detector — the shared patterns behind VERITY's two enforcement points:

  • the PROXY (server.py): inspects every model RESPONSE server-side and re-prompts once when it
    smells a premature giveup. Universal — fires for ANY OpenAI-format model routed through :11500,
    with no opt-out (the daemon enforces it, not the model's goodwill).
  • the Claude Code STOP HOOK (hooks/stop_guard.py): blocks ending a turn on the same patterns.
    (That file keeps its own inline copy because it's deployed standalone, outside the package.)

The failure these target: an LLM concluding "it's down / impossible / I can't / only you can" WITHOUT
investigating — the single most expensive, most common LLM error. Caught on a code condition.
"""
import re

# A negative VERDICT about feasibility/infra ("it can't be done / it's broken / it's an outage").
NEGATIVE = re.compile(r"""(?ix)
    \b(it'?s\s+(down|broken|unavailable|impossible)
    | can'?t\s+be\s+(fixed|done|completed) | cannot\s+be\s+(fixed|done|completed)
    | not\s+(possible|fixable|feasible|doable) | unfixable | impossible | no\s+way\s+to
    | global\s+outage | environmental\s+(outage|issue|problem) | nothing\s+(i|we)\s+can\s+do
    | out\s+of\s+(my|our)\s+control | (model|backend|service|api|shim)\s+is\s+(down|unavailable)
    | there'?s\s+no\s+(way|option|api|tool) | doesn'?t\s+exist | gave?\s+up)
""")

# A premature DEFERRAL to the human ("only you can…") — the automate-before-defer failure.
DEFER = re.compile(r"""(?ix)
    \b(only\s+you\s+can | you'?ll\s+have\s+to | you\s+(will\s+)?(need|have)\s+to\s+(do|run|manually)
    | requires?\s+(you|your|manual|human|a\s+human) | needs?\s+(you|your\s+input)
    | i\s+can'?t\s+(do|run|access)\s+(this|that|it)\s+(myself|for\s+you)
    | hand(ing)?\s+(this|it)\s+(back|off)\s+to\s+you | you'?ll\s+need\s+to\s+(sign|log)\s+in)
""")

CORRECTIVE = (
    "[VERITY GUARD] Your previous answer concluded a NEGATIVE ('it's down / impossible / can't / "
    "only you can') — the single most expensive assumption an agent makes. Before that conclusion "
    "is allowed to stand you MUST show you investigated. For a broken tool/service, IN ORDER: "
    "(1) READ its logs, (2) ATTEMPT its repair/restart/refresh, (3) SEARCH the exact error "
    "(GitHub/Reddit/X/YouTube/Google/StackOverflow). For an 'only you can' deferral, first ATTEMPT "
    "the automation stack (browser/CDP/CUA/computer-use) and defer ONLY at a genuine human boundary "
    "(password, 2FA, CAPTCHA, payment). 'Errored / empty / timed-out' is a SYMPTOM, not a diagnosis. "
    "Now either (a) give the concrete next investigative step + take it, or (b) if you HAVE already "
    "investigated, state the specific evidence that makes the negative truly earned. Do not repeat "
    "the bare giveup.")


def flag(text: str) -> str | None:
    """Return 'negative' / 'defer' if the text reads as a premature giveup, else None."""
    if not text:
        return None
    # only look at the conclusion-ish tail; avoids matching a quoted/hypothetical mid-answer mention
    tail = text[-1800:]
    if NEGATIVE.search(tail):
        return "negative"
    if DEFER.search(tail):
        return "defer"
    return None
