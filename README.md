
- **Parse** — Raw `.txt` scripts become structured `Episode`, `Scene`, `Beat` objects with second-level timestamps.
- **Chunk** — Each scene is pre-cut into candidate 20–60s windows anchored on dialogue beats. The LLM never invents timestamps — it only picks and scores pre-computed ones.
- **Score** — Each candidate gets three independent 0–10 scores (hook, cliffhanger, standalone clarity) with rationale, returned as structured JSON.
- **Filter / Dedupe / Diversify** — Quality floor of 6.5, 60% overlap dedup, max 2 picks per episode.
- **Rank** — A growth-marketer prompt orders the shortlist into a release schedule.
- **Montages** — A second pass finds thematic patterns across episodes and stitches 8–15s segments into supercuts.
- **Evaluate** — Timestamp validity + score distribution + coverage + LLM-as-judge spot check.

## Design decisions

- **LLM isolated behind one interface.** `scripts/llm_client.py` is the only file that imports the SDK. Swapping providers is a 3-line change.
- **All LLM calls cached by content hash.** Re-running the full pipeline is free and reproducible after the first run.
- **Structured outputs end to end.** Pydantic schemas on every LLM call — no free-text parsing.
- **Pre-computed candidate windows.** Eliminates the single biggest reliability risk (timestamp hallucination).
- **Transient errors retried.** 429/5xx responses get exponential backoff automatically.
- **Nothing about the data is hardcoded.** The show name, episode count, and folder path are discovered at runtime.

## Run it

Needs Python 3.10+ and a Google AI Studio API key.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "GEMINI_API_KEY=your_key_here" > .env

# Unzip the episode pack into data/
# (Expects data/<Show Name>/episode-*.txt)

python run_pipeline.py        # ~15 min first run, instant after (cache)
streamlit run app.py
```

Pipeline outputs land in `outputs/`:
- `raw_candidates.json` — every scored candidate
- `shortlist.json` — top picks after filter/dedup/diversify
- `ranked_promos.json` — final release schedule with strategy
- `montages.json` — cross-episode thematic supercuts
- `evaluation.json` — quality report
- `manifest.json` — run summary

## Swap in a new show

Drop the folder of scripts into `data/` (replacing or alongside the existing one) and re-run. The parser, scorer, ranker, and UI all discover the show name and episode count from the folder. No code edits needed.

## Swap the model

Change `_MODEL` in `scripts/llm_client.py`. If using a different provider (OpenAI, Anthropic, etc.), the `call_structured` and `call_text` functions in that file are the only things to rewrite. Everything downstream uses them unchanged.

## Known limitations

- Hook/cliffhanger judgment depends on how well a text-only model imagines visual impact. Strong on dialogue-driven beats, weaker on purely visual ones.
- Montages draw from the top shortlist, so a theme spanning weaker episodes may not surface.
- Scores are comparable within a run, not across model versions.

## Stack

Python 3.12 · google-genai (Gemini 3.5 Flash) · Pydantic · Streamlit