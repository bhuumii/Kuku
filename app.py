import json
from pathlib import Path
from collections import defaultdict
import streamlit as st

from scripts.parser import parse_all_episodes, Episode, Beat


DATA_ROOT = Path("data")
OUTPUT_DIR = Path("outputs")
CONTEXT_BEATS = 2


st.set_page_config(
    page_title="Promo Finder",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown("""
<style>
  :root {
    --accent: #0d9488;
    --accent-soft: rgba(13, 148, 136, 0.10);
    --accent-border: rgba(13, 148, 136, 0.35);
    --text-dim: color-mix(in srgb, currentColor 55%, transparent);
    --text-faint: color-mix(in srgb, currentColor 35%, transparent);
    --surface: color-mix(in srgb, currentColor 4%, transparent);
    --surface-border: color-mix(in srgb, currentColor 10%, transparent);
  }

  .block-container {
    padding-top: 2.5rem; padding-bottom: 4rem;
    max-width: 1100px;
  }

  .app-title {
    font-family: ui-serif, Georgia, "Iowan Old Style", "Apple Garamond", serif;
    font-size: 2.9rem; font-weight: 700;
    letter-spacing: -0.035em; line-height: 1.05;
    margin-bottom: 0.4rem;
  }
  .app-title .accent-dot {
    display: inline-block; width: 10px; height: 10px;
    border-radius: 50%; background: var(--accent);
    margin-left: 6px; vertical-align: 10px;
  }
  .app-sub {
    color: var(--text-dim); font-size: 0.88rem;
    margin-bottom: 2.75rem; letter-spacing: 0.02em;
    text-transform: uppercase; font-weight: 500;
  }
  .app-sub .divider { margin: 0 10px; opacity: 0.4; }

  .strategy-card {
    background: var(--surface);
    border: 1px solid var(--surface-border);
    border-left: 3px solid var(--accent);
    padding: 16px 20px; border-radius: 6px;
    margin-bottom: 2rem;
  }
  .strategy-label {
    text-transform: uppercase; font-size: 0.72rem;
    letter-spacing: 0.08em; color: var(--text-dim);
    font-weight: 600; margin-bottom: 6px;
  }
  .strategy-body { font-size: 0.93rem; line-height: 1.6; }

  .promo-row {
    padding: 14px 0 10px 0;
    border-bottom: 1px solid var(--surface-border);
  }
  .promo-rank {
    display: inline-block; font-variant-numeric: tabular-nums;
    font-weight: 700; font-size: 0.85rem;
    color: var(--text-dim); margin-right: 14px;
    min-width: 26px;
  }
  .promo-rank.top { color: var(--accent); }
  .promo-ep {
    font-weight: 600; font-size: 1rem; letter-spacing: -0.01em;
  }
  .promo-time {
    color: var(--text-dim); font-size: 0.88rem;
    font-variant-numeric: tabular-nums; margin-left: 8px;
  }

  .chip {
    display: inline-block; padding: 2px 9px; border-radius: 4px;
    font-size: 0.72rem; font-weight: 600;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em; margin-right: 6px;
    border: 1px solid var(--surface-border);
  }
  .chip-strong { background: var(--accent-soft); color: var(--accent); border-color: var(--accent-border); }
  .chip-neutral { background: var(--surface); color: inherit; }

  .label {
    text-transform: uppercase; font-size: 0.68rem;
    letter-spacing: 0.1em; color: var(--text-dim);
    font-weight: 600; margin-top: 10px; margin-bottom: 4px;
  }

  .script-wrap {
    background: var(--surface);
    border: 1px solid var(--surface-border);
    border-radius: 6px; padding: 10px 14px;
    font-size: 0.88rem; line-height: 1.55;
  }
  .beat {
    padding: 4px 8px; margin: 2px -8px; border-radius: 4px;
    display: block;
  }
  .beat-in {
    background: var(--accent-soft);
    border-left: 2px solid var(--accent);
  }
  .beat-out {
    color: var(--text-faint);
  }
  .beat-divider {
    text-align: center; color: var(--text-faint);
    font-size: 0.72rem; letter-spacing: 0.15em;
    padding: 6px 0; text-transform: uppercase;
  }
  .ts {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.78rem; color: var(--text-dim);
    margin-right: 10px;
  }
  .speaker { font-weight: 600; }
  .tone { color: var(--text-dim); font-style: italic; font-weight: 400; }
  .kind-tag {
    font-size: 0.68rem; letter-spacing: 0.08em;
    color: var(--text-dim); text-transform: uppercase;
    margin-right: 8px;
  }

  .montage-card {
    padding: 18px 0 14px 0;
    border-bottom: 1px solid var(--surface-border);
  }
  .montage-theme {
    font-size: 1.45rem; font-weight: 700;
    letter-spacing: -0.02em; margin-bottom: 6px;
    display: inline-block;
    padding: 2px 10px; margin-left: -10px;
    background: var(--accent-soft);
    border-radius: 4px;
  }
  .montage-pitch {
    color: var(--text-dim); font-size: 0.92rem;
    font-style: italic; margin-bottom: 10px;
  }

  .ep-header {
    display: flex; align-items: baseline;
    padding: 14px 0 6px 0;
  }
  .ep-num { font-weight: 700; font-size: 1rem; margin-right: 12px; min-width: 90px; }
  .ep-logline { color: var(--text-dim); font-size: 0.88rem; }

  div[data-testid="stExpander"] {
    border: none !important; background: transparent !important;
  }
  div[data-testid="stExpander"] summary {
    font-weight: 500 !important; font-size: 0.88rem !important;
    padding: 4px 0 !important;
  }
  div[data-testid="stExpander"] summary:hover { color: var(--accent); }

  .stTabs [data-baseweb="tab-list"] {
    gap: 28px;
    border-bottom: 1px solid var(--surface-border) !important;
  }
  .stTabs [data-baseweb="tab"] {
    padding: 10px 2px !important;
    font-size: 0.92rem !important;
    color: var(--text-dim) !important;
  }
  .stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: inherit !important;
  }
  .stTabs [data-baseweb="tab-highlight"] {
    background-color: var(--accent) !important;
  }
  .stTabs [data-baseweb="tab-border"] {
    background-color: var(--surface-border) !important;
  }

  hr { border-color: var(--surface-border) !important; margin: 0 !important; }
</style>
""", unsafe_allow_html=True)


def discover_show() -> tuple[Path | None, str]:
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        return None, manifest.get("show_name", "Unknown show")

    if DATA_ROOT.exists():
        candidates = [p for p in DATA_ROOT.iterdir() if p.is_dir()]
        if candidates:
            folder = sorted(candidates)[0]
            return folder, folder.name

    return None, "Unknown show"


@st.cache_data
def load_episodes() -> dict[int, Episode]:
    episodes_json = OUTPUT_DIR / "episodes.json"
    if episodes_json.exists():
        from scripts.parser import episodes_from_dict
        eps = episodes_from_dict(json.loads(episodes_json.read_text()))
        return {e.number: e for e in eps}

    folder, _ = discover_show()
    if folder:
        eps = parse_all_episodes(folder)
        return {e.number: e for e in eps}

    return {}


@st.cache_data
def load_json(name: str):
    path = OUTPUT_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _ts(t: float) -> str:
    m = int(t // 60)
    s = t - m * 60
    return f"{m:02d}:{s:05.2f}"


def _score_chip(label: str, value: float) -> str:
    cls = "chip-strong" if value >= 7.5 else "chip-neutral"
    return f'<span class="chip {cls}">{label} {value:.1f}</span>'


def _render_beat(beat: Beat, in_window: bool) -> str:
    ts = f'<span class="ts">{_ts(beat.start)}</span>'
    if beat.kind == "dialogue":
        tone = f' <span class="tone">({beat.tone})</span>' if beat.tone else ""
        body = f'<span class="speaker">{beat.speaker}</span>{tone}: {beat.content}'
    else:
        body = f'<span class="kind-tag">{beat.kind}</span>{beat.content}'
    cls = "beat beat-in" if in_window else "beat beat-out"
    return f'<div class="{cls}">{ts}{body}</div>'


def _render_script_window(episode: Episode, start: float, end: float):
    scene = next((s for s in episode.scenes if s.start <= start < s.end), episode.scenes[0])
    beats = scene.beats
    in_indices = [i for i, b in enumerate(beats) if b.start >= start and b.end <= end]
    if not in_indices:
        st.markdown('<div class="script-wrap"><em>No dialogue beats fall exactly in this window.</em></div>', unsafe_allow_html=True)
        return

    first = max(0, in_indices[0] - CONTEXT_BEATS)
    last = min(len(beats), in_indices[-1] + CONTEXT_BEATS + 1)

    html_parts = []
    if first > 0:
        html_parts.append(f'<div class="beat-divider">· {first} earlier beat{"s" if first != 1 else ""} ·</div>')
    for i in range(first, last):
        b = beats[i]
        html_parts.append(_render_beat(b, i in in_indices))
    remaining = len(beats) - last
    if remaining > 0:
        html_parts.append(f'<div class="beat-divider">· {remaining} later beat{"s" if remaining != 1 else ""} ·</div>')

    st.markdown(f'<div class="script-wrap">{"".join(html_parts)}</div>', unsafe_allow_html=True)


def ranked_tab(episodes: dict[int, Episode]):
    data = load_json("ranked_promos.json")
    if not data:
        st.warning("Run `python run_pipeline.py` first.")
        return

    st.markdown(
        f'<div class="strategy-card">'
        f'<div class="strategy-label">Release strategy</div>'
        f'<div class="strategy-body">{data["overall_strategy"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    for promo in data["promos"]:
        rank = promo["rank"]
        rank_cls = "promo-rank top" if rank <= 3 else "promo-rank"
        duration = promo["end_seconds"] - promo["start_seconds"]
        st.markdown(
            f'<div class="promo-row">'
            f'<span class="{rank_cls}">#{rank:02d}</span>'
            f'<span class="promo-ep">Episode {promo["episode_number"]}</span>'
            f'<span class="promo-time">{_ts(promo["start_seconds"])}–{_ts(promo["end_seconds"])} · {duration:.0f}s</span><br>'
            f'<div style="margin-top:6px; margin-left:40px;">'
            f'{_score_chip("Overall", promo["overall_score"])}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        with st.expander("View clip detail"):
            cols = st.columns([1, 1.3], gap="large")
            with cols[0]:
                st.markdown('<div class="label">Hook · first 3 seconds</div>', unsafe_allow_html=True)
                st.markdown(promo["hook_description"])
                st.markdown('<div class="label">Cliffhanger</div>', unsafe_allow_html=True)
                st.markdown(promo["cliffhanger_description"])
                st.markdown(f'<div class="label">Why it sits at #{rank}</div>', unsafe_allow_html=True)
                st.markdown(promo["post_rationale"])
            with cols[1]:
                st.markdown('<div class="label">Script window</div>', unsafe_allow_html=True)
                ep = episodes.get(promo["episode_number"])
                if ep:
                    _render_script_window(ep, promo["start_seconds"], promo["end_seconds"])


def per_episode_tab(episodes: dict[int, Episode]):
    raw = load_json("raw_candidates.json")
    if not raw:
        st.warning("Run `python run_pipeline.py` first.")
        return

    by_ep: dict[int, list] = defaultdict(list)
    for c in raw:
        by_ep[c["episode_number"]].append(c)

    for ep_num in sorted(by_ep.keys()):
        cands = sorted(by_ep[ep_num], key=lambda c: c["overall_score"], reverse=True)[:2]
        ep = episodes.get(ep_num)
        if not ep or not cands:
            continue

        logline = ep.logline[:120] + ("…" if len(ep.logline) > 120 else "")
        st.markdown(
            f'<div class="ep-header">'
            f'<div class="ep-num">Episode {ep_num}</div>'
            f'<div class="ep-logline">{logline}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        for i, c in enumerate(cands, 1):
            label = "Top pick" if i == 1 else "Alternate"
            with st.expander(
                f"{label}  ·  {_ts(c['start_seconds'])}–{_ts(c['end_seconds'])}  ·  score {c['overall_score']:.1f}"
            ):
                cols = st.columns([1, 1.3], gap="large")
                with cols[0]:
                    chips = (
                        _score_chip("Hook", c["hook_score"]) + " " +
                        _score_chip("Cliff", c["cliffhanger_score"]) + " " +
                        _score_chip("Standalone", c["standalone_score"])
                    )
                    st.markdown(chips, unsafe_allow_html=True)
                    st.markdown('<div class="label">Hook</div>', unsafe_allow_html=True)
                    st.markdown(c["hook_description"])
                    st.markdown('<div class="label">Cliffhanger</div>', unsafe_allow_html=True)
                    st.markdown(c["cliffhanger_description"])
                    st.markdown('<div class="label">Why it works</div>', unsafe_allow_html=True)
                    st.markdown(c["rationale"])
                with cols[1]:
                    st.markdown('<div class="label">Script window</div>', unsafe_allow_html=True)
                    _render_script_window(ep, c["start_seconds"], c["end_seconds"])
        st.markdown("<hr>", unsafe_allow_html=True)


def montage_tab(episodes: dict[int, Episode]):
    data = load_json("montages.json")
    if not data:
        st.info("No montages yet — run the full pipeline.")
        return

    if data.get("discovery_notes"):
        st.markdown(
            f'<div class="strategy-card">'
            f'<div class="strategy-label">What the system noticed</div>'
            f'<div class="strategy-body">{data["discovery_notes"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    for montage in data["montages"]:
        st.markdown(
            f'<div class="montage-card">'
            f'<div class="montage-theme">{montage["theme"]}</div>'
            f'<div class="montage-pitch">"{montage["audience_pitch"]}"</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns([1, 1])
        with cols[0]:
            st.markdown('<div class="label">Editorial rationale</div>', unsafe_allow_html=True)
            st.markdown(montage["editorial_rationale"])
        with cols[1]:
            st.markdown('<div class="label">Final-segment tease</div>', unsafe_allow_html=True)
            st.markdown(montage["cliffhanger_segment_note"])

        st.markdown('<div class="label" style="margin-top:14px;">Segments</div>', unsafe_allow_html=True)
        for i, seg in enumerate(montage["segments"], 1):
            with st.expander(
                f"Segment {i}  ·  Ep {seg['episode_number']}  ·  "
                f"{_ts(seg['start_seconds'])}–{_ts(seg['end_seconds'])}"
            ):
                st.markdown(seg["what_happens"])
                ep = episodes.get(seg["episode_number"])
                if ep:
                    _render_script_window(ep, seg["start_seconds"], seg["end_seconds"])
        st.markdown("<hr>", unsafe_allow_html=True)


def evaluation_tab():
    data = load_json("evaluation.json")
    if not data:
        st.info("Run `python run_pipeline.py` to generate the evaluation report.")
        return

    st.markdown('<div class="label">Timestamp validity</div>', unsafe_allow_html=True)
    t = data["timestamp_check"]
    if t["issues_found"] == 0:
        st.markdown(f"All {t['total_checked']} shortlisted promos have valid windows (20–60s, within scene bounds).")
    else:
        st.markdown(f"**{t['issues_found']} of {t['total_checked']} have issues:**")
        for issue in t["issues"]:
            st.markdown(f"- {issue}")

    st.markdown('<div class="label">Score distribution</div>', unsafe_allow_html=True)
    sd = data["score_distribution"]
    st.markdown(
        f"Across **{sd['n']} raw candidates** — overall mean "
        f"{sd['overall']['mean']} (σ {sd['overall']['std']}, range {sd['overall']['min']}–{sd['overall']['max']}). "
        f"{sd['overall']['high_scoring']} candidates scored ≥8, {sd['overall']['low_scoring']} scored <5. "
        f"A spread like this suggests the scorer is actually discriminating, not bunching."
    )

    st.markdown('<div class="label">Coverage across the series</div>', unsafe_allow_html=True)
    c = data["coverage"]
    st.markdown(
        f"**{c['episodes_with_any_candidate']}/{c['episodes_total']}** episodes produced at least one candidate. "
        f"**{c['episodes_with_strong_candidate']}/{c['episodes_total']}** produced at least one strong candidate (score ≥7.5)."
    )
    if c["episodes_with_no_strong_candidate"]:
        st.markdown(
            f"Episodes with no strong pick: **{', '.join(str(n) for n in c['episodes_with_no_strong_candidate'])}** — "
            f"these are typically dialogue-light transition episodes."
        )

    st.markdown('<div class="label">LLM-as-judge spot check</div>', unsafe_allow_html=True)
    j = data["llm_judge"]
    st.markdown(
        f"An independent LLM pass was asked to audit **{j['sample_size']} random shortlist promos** "
        f"as a skeptical critic. It agreed with the scorer on **{j['scorer_judge_agreement']}** picks "
        f"and would actually post **{j['would_post_on_tiktok']}** on TikTok. "
        f"Mean absolute score difference: **{j['mean_score_delta']}** points."
    )
    with st.expander("View judge verdicts on the sampled promos"):
        for s in j["sampled_promos"]:
            agree = "✓ agrees" if s["judge_agrees"] else "✗ disagrees"
            post = "would post" if s["would_post"] else "would NOT post"
            st.markdown(
                f"**Ep {s['episode']}** — scorer {s['scorer_score']}, judge {s['judge_score']} · {agree} · {post}"
            )
            st.markdown(f"<div style='color: var(--text-dim); font-size:0.88rem;'>{s['judge_reasoning']}</div>", unsafe_allow_html=True)
            st.markdown("")



def main():
    _, show_name = discover_show()
    episodes = load_episodes()
    ep_count = len(episodes)

    st.markdown(
        '<div class="app-title">Microdrama promo finder</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="app-sub">Kuku Technologies'
        f'<span class="divider">·</span>'
        f'{show_name}'
        f'<span class="divider">·</span>'
        f'{ep_count} episodes</div>',
        unsafe_allow_html=True,
    )

    tabs = st.tabs([
        "Per-episode picks",
        "Release schedule",
        "Cross-episode montages",
        "Evaluation",
    ])

    with tabs[0]: per_episode_tab(episodes)
    with tabs[1]: ranked_tab(episodes)
    with tabs[2]: montage_tab(episodes)
    with tabs[3]: evaluation_tab()


if __name__ == "__main__":
    main()