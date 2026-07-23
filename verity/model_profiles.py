#!/usr/bin/env python3
"""model_profiles.py — VERITY's per-model AWARENESS layer: each main LLM's unique output structure,
parsing quirks, budgets, and gotchas, so the harness handles them correctly instead of tripping on
per-model weirdness (Kimi K3's reasoning-split, Codex's payload envelope, persona-dominance, etc.).

WHY (DJ, 2026-07-23): "make VERITY aware of each LLM's unique nature and structure to account for
weird quirks like this or Kimi K3's, per model." Discovered the hard way this session:
  • Kimi K3 / GLM / DeepSeek / Opus (reasoning models) split output into a REASONING field + a CONTENT
    (answer) field — grading/reading the wrong one produced a false -40%. Read `content`, fall back to
    reasoning's tail; give ≥16k max_tokens or the answer truncates; Kimi temperature is LOCKED at 1.0.
  • Codex (OpenAI CLI) nests transcript messages in a `payload` envelope:
    {timestamp,type,payload:{role,content:[{type:"output_text",text}]}} — top-level role parsing misses it.
  • Persona dominance: a heavy identity/system prompt (e.g. ORION_CORE) can swamp PIPED analytical context —
    the model runs its persona bootstrap instead of analyzing. Use an analyst/raw system for extraction.
  • Large piped input needs a SCALED request timeout (a fixed 25s starves long-context free models).
  • Web-session models (ChatGPT/Gemini via a driven UI) run whatever model is selected in the UI; parse
    the DOM/stream, not an API field.

Use `parse_answer(model, response_json)` to get the real answer regardless of shape, and
`profile(model)` for the quirks dict (budget, temperature, notes). Pure stdlib; portable.
"""
from __future__ import annotations

# Reasoning models emit hidden reasoning separately from the final answer.
REASONING_MODELS = {
    "moonshotai/kimi-k3", "z-ai/glm-4.6", "z-ai/glm-4.5-air", "deepseek/deepseek-chat-v3.1",
    "anthropic/claude-opus-4.8", "openai/gpt-oss-120b",
}

# Per-model / per-family profiles. Match by exact slug, then by substring family, then default.
PROFILES = {
    "moonshotai/kimi-k3": {
        "family": "kimi", "reasoning": True, "min_max_tokens": 16000, "temperature": 1.0,
        "answer_field": "content", "fallback_field": "reasoning", "tok_s": 17,
        "notes": "Temp LOCKED at 1.0. #1 frontend/agentic (beats Fable-5), TRAILS on pure reasoning → "
                 "pair with the methodology + reasoning_effort=high. Slow; not for latency-critical.",
    },
    "z-ai/glm-4.6": {"family": "glm", "reasoning": True, "min_max_tokens": 16000,
                      "answer_field": "content", "fallback_field": "reasoning",
                      "notes": "Reasoning split like Kimi; GLM-family free tiers rate-limit."},
    "deepseek/deepseek-chat-v3.1": {"family": "deepseek", "reasoning": True, "min_max_tokens": 16000,
                                     "answer_field": "content", "fallback_field": "reasoning"},
    "anthropic/claude-opus-4.8": {"family": "claude", "reasoning": True, "min_max_tokens": 16000,
                                   "answer_field": "content", "fallback_field": "reasoning",
                                   "notes": "Strong baseline control; gate behind ALLOW_PAID."},
    "google/gemma-4-31b-it:free": {"family": "gemma", "reasoning": False, "min_max_tokens": 4000,
                                    "answer_field": "content", "long_context": 262000,
                                    "notes": "FREE, 262K ctx (good for large input), but rate-limits; "
                                             "scale request timeout up for big prompts."},
    "openai/gpt-5.1": {"family": "gpt", "reasoning": False, "min_max_tokens": 4000,
                        "answer_field": "content"},
    "google/gemini-2.5-pro": {"family": "gemini", "reasoning": False, "min_max_tokens": 4000,
                              "answer_field": "content"},
    # Non-API surfaces (parse differently — no message.content field):
    "codex": {"family": "codex", "transport": "rollout-jsonl",
              "envelope": "payload", "role_path": "payload.role",
              "content_path": "payload.content[].text (type=output_text)",
              "notes": "Stop-hook + transcript messages are wrapped in a `payload` envelope. Unwrap it: "
                       "the assistant turn is payload.role=='assistant', text in payload.content blocks "
                       "of type 'output_text'. Top-level role parsing MISSES it."},
    "web:chatgpt": {"family": "web", "transport": "driven-ui",
                    "notes": "Runs whatever model is selected in the ChatGPT UI; parse the DOM/stream."},
    "web:gemini": {"family": "web", "transport": "driven-ui",
                   "notes": "Runs the selected Gemini model; parse the DOM/stream."},
}
DEFAULT = {"family": "generic", "reasoning": False, "min_max_tokens": 4000, "answer_field": "content"}


def profile(model: str) -> dict:
    """Return the quirks profile for a model slug (exact → family-substring → default)."""
    if not model:
        return dict(DEFAULT)
    if model in PROFILES:
        return dict(PROFILES[model])
    if model in REASONING_MODELS or ":thinking" in model:
        return {**DEFAULT, "reasoning": True, "min_max_tokens": 16000, "fallback_field": "reasoning"}
    for slug, p in PROFILES.items():
        fam = p.get("family", "")
        if fam and fam in model:
            return dict(p)
    return dict(DEFAULT)


def request_budget(model: str) -> int:
    """max_tokens to request — reasoning models need room for BOTH hidden reasoning AND the answer."""
    return profile(model).get("min_max_tokens", 4000)


def scaled_timeout(prompt_len: int, base: int = 25, cap: int = 180) -> int:
    """A fixed request timeout starves large inputs. Scale with prompt size (bytes)."""
    for threshold, t in ((24000, 180), (12000, 120), (6000, 75), (3000, 45)):
        if prompt_len > threshold:
            return max(base, t)
    return base


def parse_answer(model: str, message: dict) -> str:
    """Extract the real ANSWER from an OpenAI-style `choices[].message` dict, honoring per-model shape.
    Reasoning models: read `content`; if empty (still thinking / truncated) fall back to the tail of
    the reasoning field. Non-reasoning: just `content`. Never returns the reasoning as the answer
    unless content is genuinely empty."""
    if not isinstance(message, dict):
        return ""
    p = profile(model)
    ans = (message.get(p.get("answer_field", "content")) or "").strip()
    if not ans and p.get("reasoning"):
        rez = (message.get("reasoning") or message.get("reasoning_content") or "")
        ans = rez[-2500:].strip()
    return ans


def codex_last_assistant(transcript_lines) -> str:
    """Extract the last assistant text from Codex rollout JSONL lines (payload envelope, output_text
    blocks). Provided here so any VERITY consumer parses Codex transcripts correctly."""
    import json
    text = ""
    for line in transcript_lines:
        try:
            ev = json.loads(line)
        except Exception:
            continue
        inner = ev.get("payload") if isinstance(ev.get("payload"), dict) else ev
        if inner.get("role") != "assistant":
            continue
        content = inner.get("content", "")
        if isinstance(content, str):
            text = content.strip() or text
        elif isinstance(content, list):
            chunks = [b.get("text", "") for b in content
                      if isinstance(b, dict) and b.get("type") in (None, "text", "output_text")]
            joined = "\n".join(c for c in chunks if c).strip()
            text = joined or text
    return text


if __name__ == "__main__":
    import json, sys
    m = sys.argv[1] if len(sys.argv) > 1 else "moonshotai/kimi-k3"
    print(json.dumps({"model": m, "profile": profile(m), "budget": request_budget(m)}, indent=2))
