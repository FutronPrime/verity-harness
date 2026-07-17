# Source parity and resilient YouTube access

## R64: source parity

For substantive external research, troubleshooting, tool selection, and
architecture claims, VERITY requires receipts from all six canonical lanes:

1. GitHub source, issues, or pull requests
2. X
3. Reddit
4. YouTube or a transcript
5. Google, official documentation, or the open web
6. Hacker News or Stack Overflow

This is stricter than R60's original quit-prevention threshold. R60 asks
whether an agent earned the right to give up. R64 asks whether an agent did a
complete current-source sweep before calling an approach "best", "missing",
or "impossible". User-provided links satisfy Rule 8 intake, but do not replace
independent discovery.

Use the proactive gate at the start and before the conclusion:

```bash
python3 -m verity persist preflight "research goal"
python3 -m verity persist note github "query" "finding"
python3 -m verity persist note x "query" "finding"
python3 -m verity persist note reddit "query" "finding"
python3 -m verity persist note youtube "query" "finding"
python3 -m verity persist note google "query" "finding"
python3 -m verity persist note hn "query" "finding"
python3 -m verity persist --proactive "proposed conclusion"
```

Trivial and wholly local deterministic tasks are exempt.

## YouTube resolver policy

`verity.youtube` is the shared access layer for transcript, visual-analysis,
and playback callers. Its route order is least-privilege first:

1. current `yt-dlp`, anonymously;
2. optional Chrome browser cookies with the `web_safari` player client;
3. optional Safari browser cookies with the same client.

Browser-cookie routes are enabled explicitly by the caller or with:

```bash
export VERITY_YOUTUBE_COOKIE_BROWSERS=chrome,safari
```

Cookie values never appear in results or error evidence. GUI projects such as
YoutubeDownloader, Arroxy, and Youwee are useful operator surfaces and
independent references, but the automation core stays on current `yt-dlp` so
extractor fixes arrive without waiting for a wrapper release. Legacy
`youtube-dl` is retained only as a compatibility reference, not the primary.

## Regression proof

`tests/test_youtube.py` verifies route order, an automatic 403 fallback, and
cookie-value redaction. `tests/test_persist.py` verifies that proactive
research conclusions require all six source receipts.
