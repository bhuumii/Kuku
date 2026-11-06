from pydantic import BaseModel, Field

from scripts.beat_scorer import PromoCandidate
from scripts.llm_client import call_structured


class RankedPromo(BaseModel):
    rank: int
    episode_number: int
    scene_number: int
    start_seconds: float
    end_seconds: float
    overall_score: float
    hook_description: str
    cliffhanger_description: str
    post_rationale: str = Field(description="Why this promo should be posted at this position in the release order")


class Ranking(BaseModel):
    promos: list[RankedPromo]
    overall_strategy: str


_RANK_PROMPT = """You are the head of social media for a short-form drama platform. A scorer has given you a shortlist of {n} candidate promo clips from the first {episode_count} episodes of "{show_name}".

Your job: order these clips into a RELEASE SCHEDULE for posting on TikTok, Instagram Reels, and YouTube Shorts. The clip you post FIRST should be the single strongest scroll-stopper — the one most likely to convert a brand-new viewer. Later posts can include more context-dependent or lower-ceiling clips, or ones that build on earlier promos.

Think like a growth marketer, not a critic. Consider:
- opening punch (does the hook work without ANY context?)
- emotional stakes a stranger feels in 60 seconds
- novelty across the release (don't stack three similar clips in a row)
- building anticipation across the arc of the show

Here are the candidates, in no particular order:

{candidates}

Return ALL {n} candidates re-ordered by posting priority (rank 1 = post first). For each, write a one-line post_rationale explaining WHY it goes at that rank. End with a 2-3 sentence overall_strategy describing the release logic."""


def _format_candidate(c: PromoCandidate, idx: int) -> str:
    return (
        f"[{idx}] Ep{c.episode_number} Sc{c.scene_number} | {c.start_seconds:.1f}s-{c.end_seconds:.1f}s ({c.duration:.0f}s)\n"
        f"    overall={c.overall_score:.1f} hook={c.hook_score:.1f} cliff={c.cliffhanger_score:.1f} standalone={c.standalone_score:.1f}\n"
        f"    Hook:  {c.hook_description}\n"
        f"    Cliff: {c.cliffhanger_description}\n"
        f"    Note:  {c.rationale}"
    )


def rank_shortlist(candidates: list[PromoCandidate], show_name: str, episode_count: int) -> Ranking:
    if not candidates:
        return Ranking(promos=[], overall_strategy="No candidates met the quality bar.")

    block = "\n\n".join(_format_candidate(c, i + 1) for i, c in enumerate(candidates))
    prompt = _RANK_PROMPT.format(
        n=len(candidates),
        show_name=show_name,
        episode_count=episode_count,
        candidates=block,
    )
    return call_structured(prompt, Ranking)