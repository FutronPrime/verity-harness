# VERITY — a complete worked example: "find, prove, and install a tool, safely"

This is the full complex example for a model using VERITY to upgrade its own system. It walks
**every** step, gate, workaround, and how-to-research, end to end, with the real commands. It is
the canonical "how to apply VERITY" reference. Follow it literally; the gates make the discipline
unavoidable, but understanding the flow makes you fast.

The task we'll run: **"Find a tool that lets the agent parse PDFs/Office docs, prove it's safe, and
install it into my runtime."** (This is the real docling install done 2026-06-28.)

---

## 0. The mindset: gates, not vibes

VERITY's whole thesis: a capable model fails not on capability but on **discipline** — it quits,
asks instead of doing, stops at obstacles, false-alarms, or ships overconfident guesses. So every
rule is a **gate** with the same shape:

> **deterministic detector → intelligent adjudication of the gray zone → ledger receipt → playbook evolution**

You will hit these gates whether you cooperate or not (see §10 Enforcement). Work *with* them.

---

## 1. PRE-FLIGHT — force the research before you act (R60)

Do not answer from memory. Fire the proactive directive first:

```bash
python3 -m verity persist preflight "find a tool to parse PDFs/Office docs for the agent"
```

It returns the mandatory retrieval plan: search ≥3 of the six sources, read the maintained tool's
source, log receipts. This is the **anti-quit / anti-stale-priors** gate at the START of work.

## 2. RESEARCH — multi-source, REUSE-FIRST (R60 + RULE 8)

Search the six and **read the maintained alternative's source** — don't reinvent:

```
GitHub (issues/PRs/source) · X · Reddit · YouTube/transcripts · Google · HN/StackOverflow
```

The web is a live RAG you consult FIRST — via the multi-provider FAILOVER search (free DuckDuckGo/
GitHub floor, optional Tavily/Perplexity/Brave/Google/SearXNG; see
[WEB-RESEARCH-PROVIDERS.md](WEB-RESEARCH-PROVIDERS.md)). It cannot afford to fail, so it never
single-sources:

```bash
python3 -m verity websearch "pdf parsing mcp server maintained 2026"   # first provider that answers
python3 -m verity websearch --all "docling vs unstructured mcp"        # every provider, merged+deduped
python3 -m verity websearch --fetch https://github.com/docling-project/docling   # read a result in depth
```
(`verity augment` calls this automatically — a weak local model's plan is grounded in live web data
before it escalates the reasoning.)

Log each real step as a receipt (this is what the gate counts later):

```bash
python3 -m verity persist note github "pdf parsing mcp server" "docling-mcp (IBM) is the maintained one"
python3 -m verity persist note google "docling mcp 2026" "docling-core slim avoids heavy ML deps"
```

> **How to research when you're stuck** (the real 2026-06-28 lesson): if a tool 404s or errors,
> READ THE LOGS, try the documented fix, then search the EXACT error on the platform's own GitHub
> issues — the fix is almost always in a maintained competitor's source. (We found the X-scraper fix
> in twscrape's source after 7 dead retries of another lib.) Re-running one dead path is NOT research.

## 3. FETCH — get the candidate (no execution yet)

```bash
git clone --depth 1 https://github.com/docling-project/docling /tmp/docling   # or use a staged copy
```

## 4. VET — prove the INSTRUCTIONS are safe (markdown / tool-descriptions)

A `SKILL.md` / MCP tool-description becomes YOUR directives once installed — a documented injection
vector. Scan it first, surface-aware:

```bash
python3 -m verity vet /tmp/docling      # → SAFE-TO-APPLY / REVIEW / BLOCK (exit 0/1/2)
```

Docs are lenient on doc-noise (badges, install curls, `rm -rf` cleanup); instruction files are
strict; a HARD signal (role-override, hidden-unicode) BLOCKs on any surface.

## 5. AUDIT — prove the CODE is safe (what it does when it runs)

```bash
python3 -m verity audit /tmp/docling    # capabilities + BLOCK on remote-code/obfusc/exfil
```

Reports caps (net-out / exec / fs-write / cred-access) and BLOCKs only on real backdoors
(`exec(requests.get().text)`, `os.system('curl|sh')`, base64→exec). `pip install`, install-curls in
comments/help-strings, and installer `.sh` scripts do NOT false-block.

## 6. ADJUDICATE — let intelligence decide the gray zone (the false-alarm fix)

Most real repos are REVIEW (powerful-but-normal caps). Don't blanket-block — escalate:

```bash
python3 -m verity adjudicate /tmp/docling [--council]
```

Clear cases are decided free (backdoor→AVOID, stdlib→INSTALL). The gray zone escalates to multi-model
judgment that reads the ACTUAL findings in context and returns INSTALL / AVOID / NEEDS-HUMAN **with a
rationale** (e.g. "TTS client calling its documented provider = fine" vs "secret → unexpected host =
AVOID"). No backend reachable ⇒ NEEDS-HUMAN, never a false INSTALL.

## 7. INSTALL — safely and reversibly (R62: engineer past "it needs a build")

If the obstacle is "needs a build/install," **do the install** (R62 — don't stop at the boundary),
then hand-wire the verified entry yourself. **Never run their installer** (that's the actual
untrusted-code boundary):

```bash
pip install --user --break-system-packages docling-mcp          # do the prereq
docling-mcp-server --help                                        # find the exact stdio command
# wire it with the safety net — gate → backup → write YOUR entry → validate → health-check → rollback:
futron-mcp-safe-wire --name docling \
  --repo /tmp/docling \
  --command ~/Library/Python/3.14/bin/docling-mcp-server \
  --args "--transport stdio" --force-reviewed
```

`--force-reviewed` is the **human-override** for a REVIEW verdict (you read the report and judged it —
e.g. the staged-repo audit was conservative on test-fixture text, but the published package is clean
and handshakes correctly). The engine backs up `~/.claude.json`, writes the entry, does a real MCP
`initialize` handshake, and **auto-rolls-back on any failure** — a broken install can't damage you.

## 8. VERIFY — Borg principle, ≥2 signals, no "done" on a vibe

```bash
futron-mcp-safe-wire --list                                       # confirm registered
# confirm the live handshake (the health-check already did, but verify independently):
echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | docling-mcp-server --transport stdio
```

## 9. HIGH-STAKES decisions — council before you commit

For an irreversible/high-consequence choice (which model to route, whether to wire something
money-adjacent), get a debiased multi-model verdict:

```bash
python3 -m verity council "Should we route model X for trading-signal synthesis?"
```

N tiers answer → anonymized blind cross-ranking → chairman synthesis + a disagreement score
(≥0.5 ⇒ escalate, don't ship).

## 10. BEFORE CONCLUDING — the anti-quit veto

About to say "I can't / it's blocked / wait for you"? Gate your own conclusion:

```bash
python3 -m verity persist "I couldn't get it working, let's wait"     # exit 2 if research isn't proven
python3 -m verity persist --proactive "<any substantive claim>"        # forces research on ANY task
```

Blocked unless the ledger shows real multi-source research OR you named a genuine human gate.

---

## The workarounds catalogue (when you hit a wall)

| Wall | Don't | Do (the rule) |
|---|---|---|
| "I tried, it errors" | conclude "can't" | R60: read logs → documented fix → search the exact error on GitHub/Reddit/X/YouTube/Google/HN → read the maintained alt's source. Cite what each said. |
| "should I do X?" (non-gated) | ask permission | R61: if it needs no serious approval, DO it and report done. |
| "needs a build / loads untrusted code" | stop at the boundary | R62: build the system that makes it safe (vet+audit+safe-wire), then execute. Do the install; hand-wire the verified entry. |
| scanner says HIGH-RISK on a reputable repo | blanket-block | adjudicate: escalate the gray zone to intelligent judgment; inspect the actual flagged lines (often badges / comments / test fixtures). |
| "only you can decide" | defer everything | the ONLY true stops are genuine human gates: password / 2FA / CAPTCHA / payment / account-creation / destructive / live-money. Name the exact one. |

## The genuine human gates (the ONLY legitimate stops)
password · 2FA · CAPTCHA/biometrics · payment · account-creation/credentials · destructive-irreversible
· live-money execution. Everything else is an engineering task — find the safe path and execute it.

---

## How VERITY actually FORCES this (the enforcement architecture)

You don't need a separate daemon — VERITY forces compliance through three composed layers (this is
the answer to "is it self-injecting like prompt-software, or do I need daemons?"):

1. **Self-injection (like a prompt-software converter):** `~/.verity-harness/verity-context-inject.sh`
   prints every gate into context at session start, plus the **evolving playbook** (`verity evolve`
   distills the ledger's lessons into it — it gets smarter each run, never resets). Strong, but pure
   text can be rationalized past — which is why it's not the only layer.
2. **The Stop hook (`hooks/stop_guard.py`) — the real forcing mechanism:** a Claude Code Stop hook
   that fires when the agent tries to END ITS TURN and returns `{"decision":"block","reason":...}` to
   **force continuation** on a lapse: premature negative, capability-negative-as-fact, workaround-
   redirect, premature deferral, publish-without-screen, and — added 2026-06-28 — **R60 context-quit**
   ("wait for compact / I'll do it next pass / at this degraded context"). Each blocks only when the
   evidence is absent, with a carve-out: a context-deferral that names a genuine safety risk
   (live-money / destructive / prod) or a human gate is ALLOWED — the hook never forces an unsafe rush.
   This is the daemon-equivalent: wired into the turn lifecycle, loop-safe (≤2 blocks/session),
   adversarially tested (`tests/test_stop_guard.py`, 46/46). It enforces the gates whether the model
   cooperates or not.

   > **Deliberately NOT hook-blocked: R61 "asking instead of doing."** A blanket block on "should I…?"
   > would suppress the safety confirmations the policy REQUIRES (you MUST ask before send / publish /
   > purchase / delete). So R61 is enforced by injection + the `verity persist` CLI, not by the Stop
   > hook — the hook only forces the *quit/defer* classes, where there is no legitimate-confirmation risk.
3. **The `:11500` proxy** inspects responses for any model routed through it and re-prompts on a giveup.

So: **self-injection forces it for cooperating models; the Stop hook forces it mechanically for Claude
Code; the proxy forces it for proxied models.** The gates (`verity persist/vet/audit/adjudicate`) are
the deterministic checks all three layers call. Add a gate once → all three layers can enforce it.

## The loop that makes it permanent
Every gate verdict → `verity ledger` (auditable receipt) → `verity evolve` (distills lessons into the
injected playbook, gated so it can only improve) → next session starts smarter. The discipline lives
in the harness, **outside the weights** — which is how a small/weak model behind these gates performs
like a careful senior, and how a frontier model stops quitting.
