#!/usr/bin/env python3
"""VERITY stop-guard — a MECHANICAL forcing function against LLM overconfidence.

The injected gate text is advisory: the model can rationalize past it (and did — 2026-06-15, a
QA backend was called a "global outage" without reading one log line). This hook fires on a CODE
condition instead: when an agent tries to END ITS TURN on a premature negative, it BLOCKS the stop
and sends the agent back to investigate. No opt-out, no goodwill required — the VERITY thesis applied
to the model's own reasoning.

Wired as a Claude Code `Stop` / `SubagentStop` hook. Input: hook JSON on stdin
(transcript_path, stop_hook_active). Output: exit 0 to allow, or {"decision":"block","reason":...}
to force continuation. Loop-safe (honors stop_hook_active + a per-session block cap).

Catches TWO failure modes, only when the evidence trail is missing:
  1) UNVERIFIED INFRA/FEASIBILITY NEGATIVE — "it's down / broken / can't be fixed / impossible /
     global outage / environmental" with NO sign of: reading logs, attempting repair/restart, or
     searching the error. → forces logs → repair → search.
  2) PREMATURE DEFERRAL — "only you can / you'll have to / requires manual" with NO sign of an
     automation attempt (CUA / browser-act / computer-use / openclick / playwright). → forces a
     real automation attempt before handing the task back to the human (R55: automate-before-defer).
"""
import json
import os
import re
import sys

MAX_BLOCKS = 2  # per session — never trap the agent in an infinite loop

NEG = re.compile(r"""(?ix)
    \b(it'?s\s+(down|broken|unavailable)|can'?t\s+be\s+(fixed|done)|cannot\s+be\s+(fixed|done)
    | not\s+(possible|fixable|feasible) | unfixable | impossible | no\s+way\s+to
    | global\s+outage | environmental\s+(outage|issue|problem) | nothing\s+(i|we)\s+can\s+do
    | out\s+of\s+(my|our)\s+control | (model|backend|service|api)\s+is\s+(down|unavailable)
    | (isn'?t|aren'?t|not|never|no\s+longer)\s+(currently\s+)?(authenticated|configured|set\s*up|installed|wired|reachable|available)
    | no\s+(api\s+)?(tokens?|creds?|credentials?|auth\b) | doesn'?t\s+exist
    | (credentials?|creds?|tokens?|account)\s+(are|is)?\s*missing | missing\s+(credentials?|creds?|tokens?))
""")
# A "the tool isn't ready, so I'll just work around it" REDIRECT — my most common quiet lapse: reaching
# for a fallback (browser, manual, a different tool) instead of querying the tool's own status first.
WORKAROUND = re.compile(r"""(?ix)
    (the\s+(clean|only|right|best|simplest)\s+(path|way|option)\s+is
    | so\s+(the\s+clean\s+|i'?ll\s+|we'?ll\s+|i\s+have\s+to\s+|we\s+have\s+to\s+).{0,24}(use|post\s+through|go\s+through|via\s+the\s+browser|do\s+it\s+manually)
    | instead\s+(i'?ll|we'?ll|use|let'?s) | fall\s*back\s+to | work\s*around
    | (use|do|go|post|try|switch)\b[^.]{0,40}\binstead\b)
""")
# A confident CAPABILITY/POSSIBILITY negative asserted as fact — "only weights can do this",
# "structurally won't", "not reachable without training", "no prompt can". DISTINCT from the infra NEG:
# this is about what's POSSIBLE. The exact sin the harness's author committed 2026-06-22 ("discover =
# weights only") — a Rule-6 search debunked it (ADAS/FunSearch/AlphaEvolve discover with a FROZEN model).
# Earned ONLY when the trail shows a search (INVESTIGATED) for how it's actually done without the constraint.
CAPABILITY = re.compile(r"""(?ix)
    \b(only\s+(weights?|training|fine[\s-]?tuning|gradients?|rl|retraining|a\s+trained\s+model)\s+(can|could|will|do(es)?)
    | structurally\s+(impossible|can'?t|cannot|won'?t|unable|hard\b)
    | (not|never|isn'?t|won'?t\s+be)\s+(reachable|achievable|possible|feasible|replicable|doable)\s+without
    | can'?t\s+be\s+(done|achieved|solved|discovered|reached|replicated)\s+without\s+(weight|training|fine|gradient|rl)
    | (weights?|gradient|training)[\s-]only
    | no\s+(prompt|amount\s+of\s+prompting|prompt\s+software)\s+(can|could|will)
    | impossible\s+without\s+(training|weights|fine[\s-]?tuning))
""")
DEFER = re.compile(r"""(?ix)
    \b(only\s+you\s+can | you'?ll\s+have\s+to | you\s+(will\s+)?(need|have)\s+to\s+(do|run|manually)
    | requires?\s+(you|your|manual|human|a\s+human) | needs?\s+(you|your\s+input)
    | i\s+can'?t\s+(do|run|access)\s+(this|that|it)\s+(myself|for\s+you) | hand(ing)?\s+(this|it)\s+(back|off)\s+to\s+you
    # ── lazy hand-off of an AUTOMATABLE task (install/download/setup punted to the user) ──
    | your\s+(move|turn|\d+[\s-]*min)
    | you\s+(can|should|just|could|go\s+ahead\s+and|gotta|might\s+want\s+to)?\s*(install|download|drag|launch|set\s*up|grab|run\s+the|clone)\b
    | once\s+you'?(ve|re)?\s+(install|download|set\s*up|launch|got|grabbed|cloned)
    | drag\s+.{0,30}\s+to\s+(applications|the\s+dock)
    | tell\s+me\s+(once|when)\s+(it'?s|you'?ve|you\s+have)
    | (install|download|grab|clone|set\s*up)\s+.{0,30}\byourself\b
    # SUPPORT-DEFLECT — the softer giveup low-B models favor (multi-model test: qwen2.5:3b deflected
    # to "seek assistance from our support team" where a frontier model said "can't be done").
    | (recommend|suggest|advise|best\s+to|you\s+(should|could|might|may))\s+(seek(ing)?|contact(ing)?|reach(ing)?\s+out\s+to|ask(ing)?)\s+[^.]{0,24}(support|help\s+(team|desk)|assistance|customer\s+service|the\s+(team|vendor|provider))
    | (contact|email|call)\s+[^.]{0,15}support | seek(ing)?\s+(assistance|help)\s+(from|with) | for\s+further\s+(guidance|assistance|help|support))
""")
# evidence the negative was earned — logs/repair/search OR DISCOVERY (querying the tool's own status,
# health, accounts, help, the system directory, or creds — the check that satisfies a "not ready" claim).
INVESTIGATED = re.compile(r"""(?ix)
    (\btail\b|\bcat\b|\bgrep\b|\bless\b|\.log\b|read.{0,12}log|logs?\b
    | restart|kickstart|reboot|refresh|reinstall|launchctl|systemctl|--force|repair|bounce
    | websearch|web_search|search_|curl\s+http|https?://|github|reddit|stackoverflow|google|youtube|brave|ddgs
    | futron-scrape|x-read|fetch_tweet|agent-reach
    | \baccounts\b|\bhealth\b|\bstatus\b|--list|--query|--help|print-disabled|defaults\s+read
    | futron-system-directory|command\s+-v|which\s+\w|grep[^\n]{0,40}(cred|token|account|auth))
""")
# evidence an automation attempt was made before deferring — incl. real INSTALL/SETUP actions
# (mounting a DMG, copying an app, npm/pip/brew/git, dequarantine, launching) so a hand-off is only
# allowed AFTER the agent actually tried to do it itself.
AUTOMATION = re.compile(r"""(?ix)
    (cua|browser-act|browser_act|computer-use|computer_use|openclick|playwright|claude-in-chrome
    | futron-claw|axiom|osascript|cdp|oauth-cdp|applescript|--browser-login|automate
    | hdiutil|xattr|\bcp\s+-[rR]|/Applications|open\s+-a|\bopen\s+["'~/]|installer\b|brew\s+install
    | npm\s+(install|i)\b|pip3?\s+install|pipx\s+install|git\s+clone|defaults\s+write|launchctl\s+(load|bootstrap)
    | agent-desktop|chmod\s+\+x|curl\s+-[a-zA-Z]*o|wget)
""")
# OUTWARD PUBLISH (post to public) — and the SCREENING that must precede it (brand/persona gate).
PUBLISH = re.compile(r"""(?ix)
    (social-publish\s+post                    # the actual post subcommand (NOT 'accounts'/'health' discovery)
    | \bpost(ing|ed)?\s+(to|the|all|it|this)\b | \btweet(ing|ed)?\b | publish(ing|ed)\s+(to|the|this|it)
    | compose.{0,20}(tweet|post) | x\.com.{0,30}post | (reddit|instagram|facebook|linkedin)\s+post)
""")
SCREENED = re.compile(r"""(?ix)
    (sets-review|test-screening|soul-personality-audit|persona[\s_-]*(screen|audit|panel)|s\.e\.t\.s|screening)
""")
# R60 CONTEXT-QUIT — deferring the CURRENT task to "a fresh pass / after compact / next session"
# or because "context is low/degraded". These are the exact quit-phrasings the other classes miss
# (the author used them repeatedly 2026-06-28). "Low/stale context" is NOT a boundary — it's where
# you push through. Earned ONLY by investigation OR a named genuine-safety reason (see SAFETY_REASON).
CONTEXT_QUIT = re.compile(r"""(?ix)
    ( wait\s+for\s+(the\s+)?(/?compact|a\s+fresh|fresh\s+context|the\s+next\s+(pass|session))
    | (do|finish|complete|wire|tackle|handle|run)\s+(it|this|that|the\s+rest|them)\s+(in\s+a\s+|on\s+a\s+|with\s+a\s+)?(fresh|next|later|follow[\s-]?up|new|clean)\s*(pass|session|context)
    | next\s+(bounded\s+)?(pass|action|session)\b | in\s+a\s+(fresh|clean|follow[\s-]?up)\s+(pass|session|context)
    | (at|in|given|on)\s+(this|the)\s+(degraded|low|tail|stale|poor)\s+(context|fill|budget)
    | (degraded|low|stale|poor)\s+context\b | tail\s+of\s+(a\s+|this\s+)?long\s+context
    | i'?ll\s+(do|finish|complete|get\s+to|tackle|wire)\s+(it|this|that|them)\s+(next|later)
    | let'?s\s+wait\b | come\s+back\s+to\s+(it|this)\s+(next|later|in\s+a) )
""")
# ── FOUND-AND-DEFERRED (added 2026-07-25 at DJ's direction) ───────────────────────────
# The evasion the other classes all miss: the agent FINDS a specific, fixable problem, states
# it clearly, and then hands it back instead of fixing it. It reads as diligence — a crisp
# diagnosis plus a ready-made one-liner — which is exactly why it slips past. DJ, verbatim:
#   "any issues and obstacles or suggestions you find FIX THEM don't just note or suggest it
#    should be done! how do i force you to actually be proactive... instead of just telling me
#    or asking me when you know i'm going to say do it"
# Real instances from this session: "I did NOT fix it… the fix is one line, for you to run",
# "Say the word and I'll apply it", and "those are pre-existing, not regressions" (used to
# excuse 8 flagged tools). Each was a fix the agent could have shipped in the same turn.
# EARNED ONLY by naming a genuine boundary (SAFETY_REASON) — e.g. it needs a password, it
# modifies a safety gate, it moves money. "It's out of scope" and "it pre-dates me" are not
# boundaries; they are choices to leave the work undone.
FOUND_DEFER = re.compile(r"""(?ix)
    ( (say|just\s+say)\s+the\s+word
    | want\s+me\s+to\s+(fix|apply|do|patch|handle|build|wire|run|change|update)
    | (shall|should)\s+i\s+(fix|apply|patch|go\s+ahead)
    | for\s+you\s+to\s+(run|apply|do|decide)\b
    | i'?m\s+not\s+(going\s+to\s+|gonna\s+)?(patch|fix|change|touch|modify)(ing)?\s+(it|this|that)\b
    | i\s+(did\s+)?not\s+fix\b | i\s+didn'?t\s+fix\b | left\s+(it\s+)?(as[\s-]is|alone|unfixed)
    | (that|this|these|those|it)\s+(is|are|'?s|'?re)\s+pre[\s-]?existing
    | not\s+(a\s+)?regressions?\b
    | (worth|would\s+be\s+worth)\s+(doing|fixing|auditing|adding|building|checking)\b
    | (someone|somebody|you)\s+should\s+(fix|do|run|apply|handle)
    | (recommend|suggest)\s+(fixing|doing|running|applying|adding)
    | (leaving|leave)\s+(that|it|those|them)\s+(to\s+you|for\s+you|as[\s-]is|alone)
    | (out\s+of|beyond)\s+scope\s+(for|of)\s+(this|now)
    | (your|the\s+user'?s)\s+call\b
    | i'?ll\s+leave\s+(that|it|this)\s+(to|with)\s+you )
""")

# ── R12 FALSE ALL-CLEAR (added 2026-07-26) ────────────────────────────────────────────
# The inverse of every class above. Those catch acts of COMMISSION — a claim the agent had
# not earned. This catches the OMISSION that ends a turn looking perfect: "no issues found",
# "all clear", "everything looks good". It is the single most common way a Missed-Needed
# leaves no trace, because a clean report and a blind report are textually identical.
#
# The honest form states the LIMIT of what was checked: "these checks found nothing THEY CAN
# SEE", "X was not verified", "that domain is UNMONITORED". So the gate is EARNED by any
# scope qualifier — a real all-clear on a genuinely-checked surface passes untouched. What
# it blocks is the unqualified one, which claims coverage nobody established.
#
# Evidence for the class, measured 2026-07-26: a brand-screening gate had been failing OPEN
# for an unknown period, printing confident scores it never computed. Nothing reported it,
# because a gate that is quietly wrong emits exactly what a working gate emits.
FALSE_ALL_CLEAR = re.compile(r"""(?ix)
    ( no\s+(issues?|problems?|errors?|failures?|concerns?)\s+(were\s+)?(found|detected|present)
    | (found|detected)\s+no\s+(issues?|problems?|errors?|failures?)
    | \ball\s+clear\b | \ball\s+good\b | \bnothing\s+to\s+report\b
    | everything\s+(looks|is|seems|checks\s+out)\s*(good|fine|healthy|ok|okay|correct)?\b
    | clean\s+bill\s+of\s+health
    | (system|everything|it|things)\s+(is|are|looks?)\s+healthy\b
    | no\s+(other\s+)?(remaining\s+)?(issues?|problems?)\b )
""")
# Naming the LIMIT of the check earns the all-clear — this is the honest phrasing.
# A "publish" whose only target is an ARTIFACT is not outward-facing: artifacts are private
# by default and mint a link only the owner can open. Demanding a brand screen for one is
# friction with no safety value — and a gate that cries wolf on a safe action is exactly how
# a REAL publish warning gets skimmed past. Any genuine outward target overrides this.
ARTIFACT_ONLY = re.compile(r"""(?ix)
    \bartifacts?\b
""")
OUTWARD_TARGET = re.compile(r"""(?ix)
    ( \b(to|on)\s+(x|twitter|reddit|instagram|facebook|linkedin|threads|bluesky|mastodon)\b
    | social-publish\s+post | \btweet | \bpublic(ly)?\b | \bsubreddit\b | \bfollowers\b )
""")
SCOPE_QUALIFIED = re.compile(r"""(?ix)
    ( they\s+can\s+see | \bUNMONITORED\b | (was|were|could)\s+not\s+(be\s+)?(check|verif|test|scan)
    | (did|do)\s+not\s+(check|verify|cover|test|scan) | not\s+(checked|verified|covered|tested|scanned)
    | within\s+(the\s+)?scope | these\s+(checks?|detectors?|tests?) | limits?\s+of\s+(this|the)
    | \bMN[\s-]?risk\b | held\s+below | \bunverified\b | i\s+could\s+not\s+(check|confirm|verify)
    | (blind|unmeasured)\b | no\s+verdict
    # meta/quoting: talking ABOUT the phrase is not claiming it. A gate that fires on its
    # own documentation makes the rule unwritable — caught by the adversarial suite, 2026-07-26.
    | ["\u2018\u2019\u201c\u201d'].{0,40}(no\s+issues|all\s+clear|nothing\s+to\s+report)
    | \b(R12|rule|guard|gate|protocol|says|instead\s+of|never\s+say|don'?t\s+say)\b )
""")

# A genuine reason that DOES justify deferring/stopping (money/destructive/prod/human gate) — naming
# one earns the stop, so the context-quit block is suppressed.
SAFETY_REASON = re.compile(r"""(?ix)
    \b(password|2fa|two[\s-]?factor|mfa|otp|captcha|biometric|face\s?id|touch\s?id
    | payment|credit\s?card|\bbank\b|wire\s+transfer|live[\s-]?trad|real\s+money|move\s+money|funds?\b
    | destructive|irreversible|delete\s+prod|drop\s+(the\s+)?(database|table)|production\s+config
    | tcc|privacy\s+prompt|account[\s-]creation)
""")


def _tail(path, n=240):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.readlines()[-n:]
    except Exception:
        return []


def _parse(lines):
    """Return (last_assistant_text, recent_actions_blob)."""
    last_text, actions = "", []
    for ln in lines:
        try:
            o = json.loads(ln)
        except Exception:
            continue
        msg = o.get("message") or o
        role = o.get("type") or msg.get("role")
        content = msg.get("content")
        if isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and role in ("assistant", None):
                    last_text = b.get("text", "") or last_text
                if b.get("type") == "tool_use":
                    actions.append((b.get("name", "") or "") + " " +
                                   json.dumps(b.get("input", {}))[:600])
                if b.get("type") == "tool_result":
                    actions.append(json.dumps(b.get("content", ""))[:300])
        elif isinstance(content, str) and role == "assistant":
            last_text = content or last_text
    return last_text, "\n".join(actions[-30:])


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed input → never block
    if data.get("stop_hook_active"):
        sys.exit(0)  # we already nudged once this stop-cycle — don't loop
    tpath = data.get("transcript_path", "")
    sid = data.get("session_id", "x")
    if not tpath or not os.path.exists(tpath):
        sys.exit(0)

    text, actions = _parse(_tail(tpath))
    if not text:
        sys.exit(0)
    tail_text = text[-1600:]  # the conclusion the agent is stopping on

    neg = bool(NEG.search(tail_text)) or bool(WORKAROUND.search(tail_text))
    capability = bool(CAPABILITY.search(tail_text))
    defer = bool(DEFER.search(tail_text))
    publish = bool(PUBLISH.search(tail_text)) or bool(PUBLISH.search(actions))
    # private artifact, no outward target named -> not an outward publish
    if publish and ARTIFACT_ONLY.search(tail_text) and not OUTWARD_TARGET.search(
            tail_text + ' ' + actions):
        publish = False
    # R60 context-quit: deferring the task to a fresh pass / low context — but NOT if a genuine
    # safety reason (money/destructive/human gate) is named (that earns the stop).
    quit_ctx = bool(CONTEXT_QUIT.search(tail_text)) and not bool(SAFETY_REASON.search(tail_text))
    found_defer = bool(FOUND_DEFER.search(tail_text)) and not bool(SAFETY_REASON.search(tail_text))
    # R12: an unqualified all-clear. Earned by naming what was NOT checked.
    false_clear = bool(FALSE_ALL_CLEAR.search(tail_text)) and not bool(SCOPE_QUALIFIED.search(tail_text))
    if not (neg or capability or defer or publish or quit_ctx or found_defer or false_clear):
        sys.exit(0)

    investigated = bool(INVESTIGATED.search(actions))
    automated = bool(AUTOMATION.search(actions))
    screened = bool(SCREENED.search(actions)) or bool(SCREENED.search(text))

    reason = None
    if capability and not investigated:
        reason = ("VERITY stop-guard: you asserted a CAPABILITY NEGATIVE as fact — 'only weights/training "
                  "can do this', 'structurally impossible', 'not reachable without X', 'no prompt can' — "
                  "but the transcript shows NO search for how it's actually achieved without that "
                  "constraint. This is the costliest class of assumption and is almost always wrong "
                  "un-searched. SEARCH first (GitHub / arXiv / Google for the named technique), THEN "
                  "conclude. Precedent: 'agentic discovery needs weight training' was debunked in three "
                  "citations — ADAS, FunSearch, AlphaEvolve all discover with a FROZEN model via an outer "
                  "search loop. If you HAVE searched and the impossibility is truly earned, cite the "
                  "specific evidence and stop. Do not let an un-searched 'only X can' stand.")
    elif neg and not investigated:
        reason = ("VERITY stop-guard: you're concluding something is DOWN / BROKEN / IMPOSSIBLE / NOT "
                  "AUTHENTICATED / NOT CONFIGURED — or reaching for a WORKAROUND — but the transcript "
                  "shows no investigation. Before that stands you MUST, in order: for infra → (1) READ "
                  "logs, (2) ATTEMPT repair/restart/refresh, (3) SEARCH the exact error. For 'the tool "
                  "isn't ready / I'll just use X instead' → QUERY THE TOOL'S OWN STATUS FIRST (its "
                  "`accounts`/`health`/`status`/`--list`, and `futron-system-directory --query`) — the "
                  "system very likely already has the solution. 'Errored/empty/not-configured' is a "
                  "symptom, not a diagnosis. Investigate, then continue. (If you HAVE already checked and "
                  "the negative is truly earned, state the specific evidence and stop.)")
    elif publish and not screened:
        reason = ("VERITY stop-guard: you're about to PUBLISH / POST outward-facing content without "
                  "running the required BRAND PERSONA SCREENING. Per protocol, run "
                  "`futron-sets-review --panel marketing --text \"<copy>\"` FIRST and confirm it passes, "
                  "and confirm you're posting to the CORRECT account(s) (query `futron-social-publish "
                  "accounts`). Public posts are irreversible — screen, route, then post.")
    elif defer and not automated:
        reason = ("VERITY stop-guard: you're HANDING AN AUTOMATABLE TASK BACK TO THE USER ('your move / "
                  "you install / drag it to Applications / tell me once it's running') without doing it "
                  "yourself first. You almost certainly CAN do it autonomously — DO IT: install an app "
                  "(curl/`hdiutil attach` the dmg → `cp -R *.app /Applications` → `xattr -dr "
                  "com.apple.quarantine` → `open -a`), `npm/pip/brew install`, `git clone`, edit a config, "
                  "or drive the GUI via CUA (futron-claw / computer-use / Claude-in-Chrome / Playwright / "
                  "osascript). Defer ONLY at a GENUINE human boundary — password entry, 2FA, CAPTCHA, "
                  "biometrics, payment, or a macOS TCC privacy prompt (mic/camera/screen/accessibility "
                  "grant) — and name the exact one you hit. 'It needs setup' is not a boundary; it's a task.")
    elif quit_ctx and not investigated:
        reason = ("VERITY stop-guard (R60): you're DEFERRING the current task to 'a fresh pass / after "
                  "compact / next session' or because 'context is low/degraded/the tail of a long "
                  "context'. That is NOT a boundary — it's exactly where you push through. Complete it "
                  "NOW. The ONLY things that justify stopping are a genuine human gate (password/2FA/"
                  "CAPTCHA/payment/account-creation) or genuinely-unsafe-to-rush work (live-money/"
                  "destructive/prod config) — and if it's the latter you must NAME the specific risk, "
                  "not cite 'low context'. If you've actually done the work, state the result and stop.")
    if not reason and found_defer:
        reason = ("VERITY stop-guard: you FOUND a concrete, fixable issue and are HANDING IT BACK "
                  "instead of fixing it ('want me to…', 'say the word', 'the fix is one line for you "
                  "to run', 'worth doing', 'pre-existing / not a regression', 'your call'). DJ has "
                  "standing instruction: FIX what you find, in the same turn — do not report it and "
                  "wait for a yes he has already given. Go do it now, then verify it. Deferring is "
                  "earned ONLY by naming a genuine boundary: a password/2FA/CAPTCHA/biometric gate, "
                  "payment or live money, account creation, or a change to a safety gate that needs "
                  "his itemized approval. 'Out of scope', 'pre-existing', and 'someone should' are "
                  "NOT boundaries — they are decisions to leave the work undone. If you genuinely "
                  "already fixed it, say what you changed and how you verified it.")
    if not reason and false_clear:
        reason = ("VERITY stop-guard (R12): you are ending on an UNQUALIFIED ALL-CLEAR — "
                  "'no issues found' / 'all clear' / 'everything looks good'. A clean report and "
                  "a BLIND report are textually identical, which is why this is the single most "
                  "common way a Missed-Needed leaves no trace. State the LIMIT instead: which "
                  "checks actually ran, what they CANNOT see, and which domains are UNMONITORED "
                  "because a check could not run. Say 'these checks found nothing they can see', "
                  "not 'no issues found'. Also surface anything you noticed and did NOT act on. "
                  "If you genuinely verified a bounded surface, name that surface and the "
                  "all-clear stands.")
    if not reason:
        sys.exit(0)

    # per-session block cap → never trap the agent
    cnt_dir = os.path.expanduser("~/.verity-harness/guard")
    os.makedirs(cnt_dir, exist_ok=True)
    cnt_file = os.path.join(cnt_dir, f"{re.sub(r'[^A-Za-z0-9]', '_', sid)}.cnt")
    n = 0
    try:
        n = int(open(cnt_file).read().strip() or "0")
    except Exception:
        pass
    if n >= MAX_BLOCKS:
        sys.exit(0)  # honored it enough times this session; let the human decide
    open(cnt_file, "w").write(str(n + 1))

    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


if __name__ == "__main__":
    main()
