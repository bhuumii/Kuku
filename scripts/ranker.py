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

Order these clips into a release schedule for posting on TikTok, Instagram Reels, and YouTube Shorts. The clip you post first should be the strongest scroll-stopper, the one most likely to grab a brand-new viewer. Later posts can include clips that need more context, or ones that build on earlier promos.

Think like a growth marketer. Consider:
- opening punch: does the hook work without any context?
- emotional stakes a stranger feels in 60 seconds
- variety across the release so you don't post three similar clips in a row
- building anticipation across the arc of the show

Here are the candidates, in no particular order:

{candidates}

Return ALL {n} candidates re-ordered by posting priority (rank 1 = post first). For each, write a one-line post_rationale explaining why it goes at that rank.

IMPORTANT writing rules for post_rationale and overall_strategy:
- Write like you are explaining to a colleague over coffee, not writing a marketing report.
- Use simple everyday words. No "high-impact", "cold-audience conversion", "instantly legible", "narrative fatigue", "institutional conspiracies".
- Short, direct sentences. Say what the clip shows and why it goes there.
- The overall_strategy should be 2-3 sentences that a non-marketer could understand."""

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