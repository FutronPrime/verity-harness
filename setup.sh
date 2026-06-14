#!/usr/bin/env bash
# VERITY — one-command setup. Makes the harness run 100% standalone.
#
# The harness itself has ZERO pip dependencies (pure Python stdlib). The only
# real runtime need is a model to talk to. This script sets up BOTH paths:
#   • Tier 0 (sovereign): installs Ollama + pulls a local open model you OWN.
#   • Tier 1 (cloud, optional): detects an API key if you have one.
#
# Usage:  bash setup.sh
set -euo pipefail

MODEL="${LLM_TIER0_MODEL:-llama3.2}"
say() { printf "\033[1;36m[setup]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[setup]\033[0m %s\n" "$*"; }

# ── 1. Python (the only language requirement — stdlib only, no pip) ──
if ! command -v python3 >/dev/null 2>&1; then
  warn "Python 3 not found. Install Python 3.9+ from https://python.org and re-run."
  exit 1
fi
say "Python 3 found: $(python3 --version)"
say "No pip install needed — the harness is pure stdlib. ✅"

# ── 2. Tier 0 (sovereign floor): Ollama + a local model you own ──
if ! command -v ollama >/dev/null 2>&1; then
  say "Ollama not found — installing (the un-revocable local tier)…"
  case "$(uname -s)" in
    Darwin|Linux) curl -fsSL https://ollama.com/install.sh | sh ;;
    *) warn "Auto-install only supports macOS/Linux. Get Ollama: https://ollama.com/download" ;;
  esac
fi
if command -v ollama >/dev/null 2>&1; then
  say "Ollama found: $(ollama --version 2>/dev/null | head -1)"
  if ! ollama list 2>/dev/null | grep -q "${MODEL%%:*}"; then
    say "Pulling local model '$MODEL' (this is your sovereign floor — nobody can revoke it)…"
    ollama pull "$MODEL" || warn "Pull failed — run 'ollama pull $MODEL' manually later."
  else
    say "Local model '$MODEL' already present. ✅"
  fi
else
  warn "Ollama unavailable — Tier 0 (sovereign floor) will be offline until installed."
fi

# ── 3. Tier 1 (cloud, optional): detect an API key ──
if [ -n "${LLM_TIER1_API_KEY:-}${OPENROUTER_API_KEY:-}${OPENAI_API_KEY:-}" ]; then
  say "Cloud API key detected — Tier 1 ready. ✅"
else
  warn "No cloud API key set. The harness still runs fully on Tier 0 (local)."
  warn "For frontier-class cloud routing, set one:  export LLM_TIER1_API_KEY=<key>"
  warn "(OpenRouter gives one key → hundreds of models: https://openrouter.ai)"
fi

# ── 4. Done ──
say "Setup complete. Verify the tiers:"
echo "    python3 -m verity tiers"
say "Prove vendor-suspension survival (cloud down → local floor answers):"
echo "    python3 -m verity failover-test"
say "Run the always-on invisible proxy (point any OpenAI client at it):"
echo "    python3 -m verity.server   # → http://127.0.0.1:11500/v1"
