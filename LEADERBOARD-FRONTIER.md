# VERITY harness lift — FRONTIER models (verity_compare, edge/fun/real_world --fast, 2026-06-27)

Naive vs 2-pass harness on the SAME frontier model. NOTE: gpt-5.5-codex unavailable on OpenRouter → used gpt-5.3-codex (latest codex). Expect SMALL lift — frontier models already score high (ceiling), the harness's value is largest on weaker models.

| model | naive | harness | lift | token× | p |
|---|---|---|---|---|---|
| anthropic/claude-opus-4.8 | 83% | 100% | +16.7pp | 2.91× | 0.3173 |
| google/gemini-3.1-pro-preview | 100% | 100% | +0.0pp | 2.99× | 1.0 |
| openai/gpt-5.3-codex | 83% | 83% | +0.0pp | 9.3× | 1.0 |
| openai/gpt-5.5 | 100% | 100% | +0.0pp | 24.24× | 1.0 |
