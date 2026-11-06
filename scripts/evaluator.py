import json
import random
from pathlib import Path
from statistics import mean, stdev
from pydantic import BaseModel, Field

from scripts.parser import parse_all_episodes, Episode
from scripts.llm_client import call_structured


class JudgeVerdict(BaseModel):
    agrees_with_scorer: bool
    judge_overall_score: float = Field(ge=0, le=10)
    judge_reasoning: str
    would_post: bool


class JudgeBatch(BaseModel):
    verdicts: list[JudgeVerdict]


def check_timestamps(shortlist: list[dict], episodes: dict[int, Episode]) -> dict:
    issues = []
    for p in shortlist:
        ep = episodes.get(p["episode_number"])
        if not ep:
            issues.append(f"Ep{p['episode_number']} not found in parsed data")
            continue
        duration = p["end_seconds"] - p["start_seconds"]
        if duration < 20 or duration > 60:
            issues.append(f"Ep{p['episode_number']} window is {duration:.1f}s (outside 20-60s)")
        if p["start_seconds"] >= p["end_seconds"]:
            issues.append(f"Ep{p['episode_number']} has start >= end")
        if p["end_seconds"] > ep.total_duration + 1:
            issues.append(f"Ep{p['episode_number']} ends at {p['end_seconds']:.1f}s, episode ends at {ep.total_duration:.1f}s")

    return {"total_checked": len(shortlist), "issues_found": len(issues), "issues": issues}


def check_score_distribution(raw_candidates: list[dict]) -> dict:
    overall = [c["overall_score"] for c in raw_candidates]
    hook = [c["hook_score"] for c in raw_candidates]
    cliff = [c["cliffhanger_score"] for c in raw_candidates]
    standalone = [c["standalone_score"] for c in raw_candidates]

    def _stats(xs: list[float]) -> dict:
        return {
            "mean": round(mean(xs), 2),
            "std": round(stdev(xs), 2) if len(xs) > 1 else 0.0,
            "min": round(min(xs), 1),
            "max": round(max(xs), 1),
            "high_scoring": sum(1 for x in xs if x >= 8),
            "low_scoring": sum(1 for x in xs if x < 5),
        }

    return {
        "n": len(raw_candidates),
        "overall": _stats(overall),
        "hook": _stats(hook),
        "cliffhanger": _stats(cliff),
        "standalone": _stats(standalone),
    }


def check_coverage(raw_candidates: list[dict], episodes: dict[int, Episode]) -> dict:
    scored_episodes = {c["episode_number"] for c in raw_candidates}
    all_episodes = set(episodes.keys())
    missing = sorted(all_episodes - scored_episodes)

    high_quality = {c["episode_number"] for c in raw_candidates if c["overall_score"] >= 7.5}
    no_strong_pick = sorted(all_episodes - high_quality)

    return {
        "episodes_total": len(all_episodes),
        "episodes_with_any_candidate": len(scored_episodes),
        "episodes_with_no_candidate": missing,
        "episodes_with_strong_candidate": len(high_quality),
        "episodes_with_no_strong_candidate": no_strong_pick,
    }


_JUDGE_PROMPT = """You are a skeptical social media consultant hired to AUDIT promo clips chosen by an AI scorer. You have no loyalty to the previous scorer — your job is to catch bad picks.

For each promo below, independently judge:
- Is this actually scroll-stopping, or does it only sound like one?
- Would you really post it on TikTok?
- Give your own 0-10 overall score and say whether you agree with the scorer.

Be honest. A promo that overpromises is worse than one that underpromises, because real editors will lose trust in the tool.

{candidates_block}

Return a verdict for each, in order."""


def _format_for_judge(p: dict) -> str:
    return (
        f"--- PROMO (Ep{p['episode_number']}, {p['start_seconds']:.1f}s-{p['end_seconds']:.1f}s) ---\n"
        f"Scorer gave overall={p['overall_score']:.1f} "
        f"(hook={p['hook_score']:.1f}, cliff={p['cliffhanger_score']:.1f}, standalone={p['standalone_score']:.1f})\n"
        f"Hook: {p['hook_description']}\n"
        f"Cliff: {p['cliffhanger_description']}\n"
        f"Scorer's reasoning: {p['rationale']}"
    )


def llm_judge_spot_check(shortlist: list[dict], sample_size: int = 5) -> dict:
    random.seed(42)
    sample = random.sample(shortlist, min(sample_size, len(shortlist)))
    block = "\n\n".join(_format_for_judge(p) for p in sample)
    prompt = _JUDGE_PROMPT.format(candidates_block=block)
    result = call_structured(prompt, JudgeBatch)

    agreement = sum(1 for v in result.verdicts if v.agrees_with_scorer)
    would_post = sum(1 for v in result.verdicts if v.would_post)
    score_deltas = [
        abs(result.verdicts[i].judge_overall_score - sample[i]["overall_score"])
        for i in range(len(sample))
    ]

    return {
        "sample_size": len(sample),
        "scorer_judge_agreement": f"{agreement}/{len(sample)}",
        "would_post_on_tiktok": f"{would_post}/{len(sample)}",
        "mean_score_delta": round(mean(score_deltas), 2) if score_deltas else 0.0,
        "sampled_promos": [
            {
                "episode": sample[i]["episode_number"],
                "scorer_score": sample[i]["overall_score"],
                "judge_score": round(result.verdicts[i].judge_overall_score, 1),
                "judge_agrees": result.verdicts[i].agrees_with_scorer,
                "would_post": result.verdicts[i].would_post,
                "judge_reasoning": result.verdicts[i].judge_reasoning,
            }
            for i in range(len(sample))
        ],
    }


def run_evaluation(output_dir: Path, episodes: dict[int, Episode]) -> dict:
    raw = json.loads((output_dir / "raw_candidates.json").read_text())
    shortlist = json.loads((output_dir / "shortlist.json").read_text())

    report = {
        "timestamp_check": check_timestamps(shortlist, episodes),
        "score_distribution": check_score_distribution(raw),
        "coverage": check_coverage(raw, episodes),
        "llm_judge": llm_judge_spot_check(shortlist, sample_size=5),
    }

    (output_dir / "evaluation.json").write_text(json.dumps(report, indent=2))
    return report