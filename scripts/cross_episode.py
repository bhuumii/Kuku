from pydantic import BaseModel, Field
from scripts.beat_scorer import PromoCandidate
from scripts.llm_client import call_structured


class MontageSegment(BaseModel):
    episode_number: int
    scene_number: int
    start_seconds: float
    end_seconds: float
    what_happens: str


class ThematicMontage(BaseModel):
    theme: str = Field(description="Short, hook-worthy name for the montage (e.g. 'Juliana's Cold Defiance')")
    audience_pitch: str = Field(description="One-sentence pitch that would appear as the TikTok caption")
    segments: list[MontageSegment] = Field(description="3-6 short clips from different episodes, in posting order")
    cliffhanger_segment_note: str = Field(description="What makes the final segment leave viewers wanting more")
    editorial_rationale: str


class MontageSet(BaseModel):
    montages: list[ThematicMontage]
    discovery_notes: str


_MONTAGE_PROMPT = """You are a social media strategist for a short-form drama platform. You've been given a pool of {n} high-scoring moments from the first {episode_count} episodes of "{show_name}".

Find 3-5 thematic montages that could be stitched together as cross-episode promo clips. These are the "character supercut" or "every time X happens" videos that drive binge-watching on TikTok and Instagram Reels.

A good montage:
- has a clear theme a viewer can name in 4 words
- draws 3-6 moments from different episodes
- builds in emotional intensity across the segments
- ends on the most jaw-dropping moment so viewers want to watch the full show

Each segment should be a roughly 8-15 second slice of an existing moment, not the whole clip.

Here is the pool of high-scoring moments:

{moments}

Return 3-5 montages. For each, pick 3-6 segments from the pool above, name the theme, write a punchy audience pitch, and explain why this montage works. End with discovery_notes describing what patterns you noticed.

IMPORTANT writing rules:
- Write like you are explaining to a colleague, not writing an essay.
- Use everyday words. No "binary emotional states", "institutional conspiracies", "cohesive narrative of persecution", "cold-audience conversion".
- Short, direct sentences. A smart 15-year-old should be able to read it.
- Audience pitches should sound like actual TikTok captions, not corporate copy."""

def _format_moment(c: PromoCandidate) -> str:
    return (
        f"Ep{c.episode_number} Sc{c.scene_number} [{c.start_seconds:.1f}s-{c.end_seconds:.1f}s, "
        f"score={c.overall_score:.1f}]\n"
        f"  Hook: {c.hook_description}\n"
        f"  Cliff: {c.cliffhanger_description}"
    )


def find_montages(candidates: list[PromoCandidate], show_name: str, episode_count: int, pool_size: int = 40) -> MontageSet:
    pool = sorted(candidates, key=lambda c: c.overall_score, reverse=True)[:pool_size]
    moments_block = "\n\n".join(_format_moment(c) for c in pool)
    prompt = _MONTAGE_PROMPT.format(
        n=len(pool),
        show_name=show_name,
        episode_count=episode_count,
        moments=moments_block,
    )
    return call_structured(prompt, MontageSet)