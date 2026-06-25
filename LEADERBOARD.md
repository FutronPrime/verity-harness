# VERITY harness-lift leaderboard — verity_compare (edge/fun/real_world, 2026-06-25)

Naive vs 2-pass harness on the SAME model. Two-axis: lift AND token cost. Run on YOUR model: `python3 verity_compare.py --model <id>`.

| model | naive | harness | lift | token× | p |
|---|---|---|---|---|---|
| mistralai/mistral-small-24b-instruct-2501 | 75% | 90% | +14.8pp | 2.91× | 0.1573 |
| qwen/qwen-2.5-coder-32b-instruct | 67% | 77% | +10.2pp | 3.63× | 0.1573 |
| google/gemma-2-27b-it | 74% | 75% | +0.8pp | 2.51× | 0.7055 |

Floor: ~32B+ (`verity doctor`). Below floor the harness catches errors but can't fix them.
