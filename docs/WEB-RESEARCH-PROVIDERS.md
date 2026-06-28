# Web-research providers — turning the whole web into a live RAG the model consults first

The R60 "go research the six sources" gate is only real if the model can actually search — and a
single provider WILL fail (downtime, rate-limit, API change). So `verity/websearch.py` is
**multi-provider with failover**: it tries providers in priority order and returns the first that
answers, degrading all the way to a free, no-key floor. **It cannot afford to fail, so it doesn't
depend on any one source.** (Meta-lesson, applied to itself: never single-source anything load-bearing.)

```bash
verity websearch "best agentic web search api 2026"     # first provider that answers
verity websearch --all "agentic RAG patterns"           # query every available provider, merge+dedupe
verity websearch --fetch https://site.com/page          # scrape ANY page → readable text
# used automatically by `verity augment` to ground plans in live data before reasoning.
```

## Providers (priority order; the free ones need NO key)

| Provider | Env var(s) | Notes |
|---|---|---|
| **Tavily** | `TAVILY_API_KEY` | LLM-native search/RAG — [tavily.com](https://www.tavily.com/) |
| **Perplexity** | `PERPLEXITY_API_KEY` | answer + citations — [agent API](https://www.perplexity.ai/gen/api-platform/agent-api) |
| **Brave Search** | `BRAVE_API_KEY` | independent index |
| **Google CSE** | `GOOGLE_CSE_KEY` + `GOOGLE_CSE_CX` | [custom-search](https://developers.google.com/custom-search/v1/overview) · `customsearch.googleapis.com/customsearch/v1` |
| **Perplexity (free)** | — | **no key, no account** — anonymous via OSS `helallao/perplexity-ai`: `pip install git+https://github.com/helallao/perplexity-ai` (NOT PyPI `perplexityai`, which is the keyed SDK). Perplexity-grade answers free. |
| **SearXNG** | `SEARX_URL` *or none* | **free, no key** — auto-tries a rotating list of PUBLIC instances if `SEARX_URL` unset; aggregates Google/Bing/etc. (public instances often disable JSON → falls through gracefully.) |
| **DuckDuckGo** | — | **free, no key** — the always-available floor (verified live: returns real results) |
| **GitHub** | — | free repo/code search; auto-added for repo/library/sdk queries |

Set any subset; the layer auto-detects and routes best→free. With zero keys it still works (DDG + GitHub).

## To add a provider
Write a `_name(query, n) -> [{title,url,snippet,source}]` (raise on no-key/error) and add it to
`PROVIDERS` in `verity/websearch.py`. One function, and the failover chain picks it up.

## Curated resource set (the research that built this — saved per R60/RULE 8)

**Search APIs / agentic search services**
- Tavily — https://www.tavily.com/  · Perplexity Agent API — https://www.perplexity.ai/gen/api-platform/agent-api
- Google Custom Search — https://developers.google.com/custom-search/v1/overview · endpoint `https://customsearch.googleapis.com/customsearch/v1`
- Progress agentic-RAG generative search — https://www.progress.com/agentic-rag/use-cases/generative-search
- LangChain search integrations — https://docs.langchain.com/oss/python/integrations/providers/overview

**Agentic web-search frameworks / browser-search (OSS)**
- antematter/agentic-websearch — https://github.com/antematter/agentic-websearch
- bahathabet/agentic-search — https://github.com/bahathabet/agentic-search
- GitHub gh-aw web-search reference — https://github.github.com/gh-aw/reference/web-search/
- Johell1NS/browser-search — https://github.com/Johell1NS/browser-search
- feder-cr/invisible_playwright — https://github.com/feder-cr/invisible_playwright
- arman-bd/chromiumfish — https://github.com/arman-bd/chromiumfish
- 1broseidon/ketch — https://github.com/1broseidon/ketch · ketch SKILL — https://github.com/gandazgul/runwield/blob/main/src/skills/ketch/SKILL.md
- SafeRL-Lab/agentic-web — https://github.com/SafeRL-Lab/agentic-web
- coleam00 crawl4AI-agent-v2 — https://github.com/coleam00/ottomator-agents/tree/main/crawl4AI-agent-v2

**Curated lists / patterns**
- nibzard awesome-agentic-patterns (web-search loop) — https://github.com/nibzard/awesome-agentic-patterns/blob/main/patterns/ai-web-search-agent-loop.md
- steel-dev/awesome-web-agents — https://github.com/steel-dev/awesome-web-agents
- r/LLMDevs awesome web agents — https://www.reddit.com/r/LLMDevs/comments/1j7z6u6/
- AIxorDie/ai-decoded — https://github.com/AIxorDie/ai-decoded

**Computer-use / browser agents (for JS-heavy & auth-walled pages — Tier above plain HTTP)**
- Microsoft OmniParser v2 — https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/
- THUDM/WebRL — https://github.com/THUDM/WebRL · Simular — https://www.simular.ai/

**Grounding / hallucination reduction**
- Connecting an LLM to the internet — https://medium.com/@matthieumordrel/the-various-ways-to-connect-an-llm-to-the-internet-6438d92faed9
- Grounding LLMs with fresh web data — https://towardsdatascience.com/grounding-llms-with-fresh-web-data-to-reduce-hallucinations/
- r/LocalLLaMA best free deep-research — https://www.reddit.com/r/LocalLLaMA/comments/1mfpnxi/
- Reddit threads: r/AI_Agents best search tool — https://www.reddit.com/r/AI_Agents/comments/1pf9avo/ · r/LangChain internet search — https://www.reddit.com/r/LangChain/comments/1mwkgfc/ · r/hermesagent browser-search — https://www.reddit.com/r/hermesagent/comments/1ucly0g/

## Mined upgrades (researched the provided resources — RULE 8, applied not just saved)

Researched the resource set and ported the highest-leverage techniques:

- **Iterative deepening loop** (from nibzard/awesome-agentic-patterns · ai-web-search-agent-loop):
  `deep_research(query, ask=, rounds=)` — search → the reasoner names the biggest remaining GAP →
  refine the query → search again → stop on "DONE" or rounds. Makes research THOROUGH, not single-shot.
  `verity websearch --deep "<q>"`.
- **Six-source scoping** (R60 made literal): `six_source(query)` / `verity websearch --six` runs an
  explicit `site:`-scoped search per canonical source (github/reddit/youtube/stackoverflow/HN + web),
  so "research the six sources" isn't one open-web query — each source is hit and labeled.

### Backlog (mined, attributed, not yet built)
- **Readability extraction + CSS-select** (from 1broseidon/ketch): replace `fetch()`'s crude tag-strip
  with main-content (readability-style) extraction + a `--select <css>` for targeted scrape. Better
  "read the page" quality.
- **Parallel multi-angle workers** (agentic-search-loop Stage 3): spawn searches for different
  angles/domains simultaneously and aggregate (today `--all` is multi-provider, not multi-angle).
- **Browser tier for JS-heavy/auth-walled** (OmniParser v2 / ketch / futron-claw): a `_browser(url)`
  escalation when `fetch()` returns thin/blocked content — render via Playwright/CUA. (See FUTRON
  memory subsystem-verity-websearch-rag TODO.)
- **Search-decision classifier** (Stage 1): skip search when internal knowledge suffices (cost control).

## Next: deeper tiers (slots already in place)
- **NotebookLM / free Gemini-grounded research** as a high-reasoning provider behind `as_context()`.
- **Browser/CUA tier** (Playwright/OmniParser/ketch) for JS-heavy or auth-walled pages `fetch()` can't read — `verity websearch --fetch` handles static HTML today; the browser tier is the escalation for the rest.
