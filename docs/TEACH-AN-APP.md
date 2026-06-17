# Teach VERITY a new app, site, or command

VERITY's agents have **"hands"** — they can observe and act on any surface, then verify. You don't write
brittle per-app integrations; you point the right hands at the target. (Generalizes voice-os's
[ADD-AN-APP](https://github.com/per-simmons/voice-os/blob/master/ADD-AN-APP.md) pattern beyond the desktop.)

## The hands, by surface
| Surface | Hands | How it sees / acts |
|---|---|---|
| **Desktop app** | `agent-desktop` (+ `osascript`) | Reads the macOS **accessibility tree** as JSON (`verity desktop snapshot`), then `click`/`type`/`select`/`toggle` by `@ref`. Works on almost any app — no pixels. |
| **Website / web app** | **Playwright** (or browser-act / Claude-in-Chrome) | Navigate, read the DOM, `click`/`fill`/`extract`/`screenshot`, headless or headed. |
| **CLI / system** | the **shell** (`ShellExecutor`) | Run any command; read stdout/exit code as the result. |

The harness surfaces all three in reuse-first (`verity resources "<goal>"`), so an agent reaches for the
right hands instead of giving up or asking you to do it by hand.

## The recipe (same shape on every surface)
1. **OBSERVE** — look at the target through its hands:
   `verity desktop snapshot --app "Music"` · Playwright `page.accessibility/snapshot` · `--help` for a CLI.
2. **FIND** the element/endpoint/flag you need (an `@ref`, a selector, a subcommand).
3. **ACT** — `click`/`type`/`select` · `fill`/`navigate` · run the command.
4. **VERIFY** (Borg) — confirm it actually did the thing (read back state / a passing check). No "done" on a vibe.
5. **REGISTER** — if it's reusable, let **`verity synthesize`** build it into a small tool and record it
   (`verity synth-list`), so next time the capability already exists.

## Don't hand it back
If a task needs an app/site/command driven, **drive it** with the hands above — defer to the user only at a
genuine human boundary (password, 2FA, CAPTCHA, payment, or a macOS TCC privacy grant). "It needs setup" is
a task, not a boundary (the stop-guard enforces this).

Related: `verity desktop` (the desktop hands) · `verity synthesize` (build a missing capability) ·
[`examples/voice-clone-workflow.md`](../examples/voice-clone-workflow.md) (a full agentic workflow example).
