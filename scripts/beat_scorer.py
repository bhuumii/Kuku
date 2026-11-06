import time
from typing import Optional
from pydantic import BaseModel, Field
from tqdm import tqdm

from scripts.parser import Episode, Scene, Beat
from scripts.llm_client import call_structured


class PromoCandidate(BaseModel):
    episode_number: int
    scene_number: int
    start_seconds: float
    end_seconds: float
    hook_score: float = Field(ge=0, le=10)
    cliffhanger_score: float = Field(ge=0, le=10)
    standalone_score: float = Field(ge=0, le=10)
    overall_score: float = Field(ge=0, le=10)
    hook_description: str
    cliffhanger_description: str
    rationale: str

    @property
    def duration(self) -> float:
        return self.end_seconds - self.start_seconds


class ScoredWindows(BaseModel):
    candidates: list[PromoCandidate]


MIN_PROMO = 20.0
MAX_PROMO = 60.0
TARGET_PROMO = 35.0


def _beats_in_window(scene: Scene, start: float, end: float) -> list[Beat]:
    return [b for b in scene.beats if b.start >= start and b.end <= end]


def _format_beats_for_prompt(beats: list[Beat]) -> str:
    lines = []
    for b in beats:
        ts = f"[{b.start:6.2f}-{b.end:6.2f}]"
        if b.kind == "dialogue":
            tone = f" ({b.tone})" if b.tone else ""
            lines.append(f'{ts} {b.speaker}{tone}: "{b.content}"')
        else:
            lines.append(f"{ts} [{b.kind.upper()}] {b.content}")
    return "\n".join(lines)


def _build_candidate_windows(scene: Scene) -> list[tuple[float, float]]:
    windows: list[tuple[float, float]] = []
    if scene.duration < MIN_PROMO:
        return windows

    if scene.duration <= MAX_PROMO:
        windows.append((scene.start, scene.end))

    dialogue_anchors = [b.start for b in scene.beats if b.kind == "dialogue"]
    if not dialogue_anchors:
        return windows

    key_anchors = [
        scene.start,
        dialogue_anchors[0],
        scene.start + scene.duration * 0.25,
        scene.start + scene.duration * 0.5,
        scene.end - TARGET_PROMO,
        scene.end - MAX_PROMO,
    ]
    key_anchors = sorted(set(round(max(scene.start, a), 1) for a in key_anchors if a >= scene.start))

    seen: set[tuple[float, float]] = set()
    for a in key_anchors:
        for length in (TARGET_PROMO, MAX_PROMO):
            start = a
            end = min(scene.end, start + length)
            if end - start < MIN_PROMO:
                continue
            key = (round(start, 1), round(end, 1))
            if key in seen:
                continue
            seen.add(key)
            windows.append((start, end))

    return windows


_SCENE_PROMPT = """You are a social media editor for a short-form drama platform. Your job is to evaluate candidate video clips (20-60 seconds) cut from a microdrama episode. For each candidate window, judge whether it would work as a scroll-stopping promo on TikTok, Instagram Reels, or YouTube Shorts.

Score each candidate on three dimensions, 0 to 10:

- hook_score: how strong is the FIRST 3 SECONDS? A great hook is a slap, a reveal, a shocking line, visible conflict, or a provocative image. Dialogue setup, slow establishing shots, or quiet moments score low.
- cliffhanger_score: does the clip END on an unresolved moment that forces the viewer to want the next episode? An interrupted confrontation, a reveal, a threat, a silence after a bomb drops — score high. A clean resolution — score low.
- standalone_score: can a stranger who has never seen the show understand what's happening in this clip? If it requires prior context to make sense — score low.

overall_score = your editorial judgment, weighted roughly: 40% hook, 35% cliffhanger, 25% standalone.

Be strict. Most candidates will score 3-6. Only genuinely exceptional clips deserve 8+.

Episode context (do not quote in your output):
Episode {episode_number} logline: {logline}

SCENE {scene_number} — {heading} (runs {scene_start:.1f}s to {scene_end:.1f}s in the episode)

Full scene for context:
{full_scene}

Candidate windows to evaluate:
{candidates_block}

For every candidate, return:
- episode_number: {episode_number}
- scene_number: {scene_number}
- start_seconds, end_seconds: as given
- scores and one-sentence rationale
- hook_description: what the viewer sees in the first 3 seconds
- cliffhanger_description: the exact unresolved moment at the end

Return every candidate given, in the same order."""


def _candidates_block(windows: list[tuple[float, float]], scene: Scene) -> str:
    blocks = []
    for i, (s, e) in enumerate(windows, 1):
        beats = _beats_in_window(scene, s, e)
        if not beats:
            continue
        blocks.append(
            f"--- CANDIDATE {i} (start={s:.2f}s, end={e:.2f}s, duration={e-s:.1f}s) ---\n"
            f"{_format_beats_for_prompt(beats)}"
        )
    return "\n\n".join(blocks)


def score_scene(episode: Episode, scene: Scene) -> list[PromoCandidate]:
    windows = _build_candidate_windows(scene)
    if not windows:
        return []

    prompt = _SCENE_PROMPT.format(
        episode_number=episode.number,
        logline=episode.logline,
        scene_number=scene.number,
        heading=scene.heading,
        scene_start=scene.start,
        scene_end=scene.end,
        full_scene=_format_beats_for_prompt(scene.beats),
        candidates_block=_candidates_block(windows, scene),
    )

    result = call_structured(prompt, ScoredWindows)
    valid = [
        c for c in result.candidates
        if MIN_PROMO <= c.duration <= MAX_PROMO
        and c.start_seconds >= scene.start - 0.5
        and c.end_seconds <= scene.end + 0.5
    ]
    return valid


def score_all_episodes(episodes: list[Episode], pause_seconds: float = 1.5) -> list[PromoCandidate]:
    all_candidates: list[PromoCandidate] = []
    scenes_to_score = [(e, s) for e in episodes for s in e.scenes if s.duration >= MIN_PROMO]

    for episode, scene in tqdm(scenes_to_score, desc="Scoring scenes"):
        try:
            all_candidates.extend(score_scene(episode, scene))
        except Exception as exc:
            print(f"\n[warn] ep{episode.number} scene{scene.number}: {exc}")
        time.sleep(pause_seconds)

    return all_candidates