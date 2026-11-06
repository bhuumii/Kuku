from scripts.beat_scorer import PromoCandidate


_OVERLAP_THRESHOLD = 0.6


def _overlap_fraction(a: PromoCandidate, b: PromoCandidate) -> float:
    if a.episode_number != b.episode_number or a.scene_number != b.scene_number:
        return 0.0
    overlap = max(0.0, min(a.end_seconds, b.end_seconds) - max(a.start_seconds, b.start_seconds))
    shorter = min(a.duration, b.duration)
    return overlap / shorter if shorter > 0 else 0.0


def deduplicate(candidates: list[PromoCandidate]) -> list[PromoCandidate]:
    ranked = sorted(candidates, key=lambda c: c.overall_score, reverse=True)
    kept: list[PromoCandidate] = []
    for cand in ranked:
        if any(_overlap_fraction(cand, k) >= _OVERLAP_THRESHOLD for k in kept):
            continue
        kept.append(cand)
    return kept


def filter_minimum_quality(candidates: list[PromoCandidate], min_score: float = 6.0) -> list[PromoCandidate]:
    return [c for c in candidates if c.overall_score >= min_score]


def diversify_by_episode(candidates: list[PromoCandidate], max_per_episode: int = 2) -> list[PromoCandidate]:
    ranked = sorted(candidates, key=lambda c: c.overall_score, reverse=True)
    counts: dict[int, int] = {}
    out: list[PromoCandidate] = []
    for c in ranked:
        n = counts.get(c.episode_number, 0)
        if n >= max_per_episode:
            continue
        out.append(c)
        counts[c.episode_number] = n + 1
    return out