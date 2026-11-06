import json
from pathlib import Path

from scripts.parser import parse_all_episodes
from scripts.beat_scorer import score_all_episodes
from scripts.promo_builder import deduplicate, filter_minimum_quality, diversify_by_episode
from scripts.ranker import rank_shortlist
from scripts.cross_episode import find_montages
from scripts.evaluator import run_evaluation


DATA_ROOT = Path("data")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

SHORTLIST_SIZE = 15


def discover_show_folder() -> Path:
    candidates = [p for p in DATA_ROOT.iterdir() if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No show folder found inside {DATA_ROOT}/")
    return sorted(candidates)[0]


def main():
    show_folder = discover_show_folder()
    show_name = show_folder.name
    print(f"Show: {show_name}")

    print("Parsing episodes...")
    episodes = parse_all_episodes(show_folder)
    print(f"  {len(episodes)} episodes, "
          f"{sum(len(e.scenes) for e in episodes)} scenes, "
          f"{sum(len(s.beats) for e in episodes for s in e.scenes)} beats")

    print("\nScoring candidate windows across all scenes...")
    raw_candidates = score_all_episodes(episodes)
    print(f"  {len(raw_candidates)} raw candidates scored")

    (OUTPUT_DIR / "raw_candidates.json").write_text(
        json.dumps([c.model_dump() for c in raw_candidates], indent=2)
    )

    print("\nFiltering, deduplicating, diversifying...")
    kept = filter_minimum_quality(raw_candidates, min_score=6.5)
    print(f"  {len(kept)} above quality bar")
    kept = deduplicate(kept)
    print(f"  {len(kept)} after dedup")
    kept = diversify_by_episode(kept, max_per_episode=2)
    print(f"  {len(kept)} after diversity cap")
    kept = sorted(kept, key=lambda c: c.overall_score, reverse=True)[:SHORTLIST_SIZE]
    print(f"  {len(kept)} in final shortlist")

    (OUTPUT_DIR / "shortlist.json").write_text(
        json.dumps([c.model_dump() for c in kept], indent=2)
    )

    print("\nRanking shortlist into release order...")
    ranking = rank_shortlist(kept, show_name=show_name, episode_count=len(episodes))
    (OUTPUT_DIR / "ranked_promos.json").write_text(ranking.model_dump_json(indent=2))

    print("\nFinding cross-episode thematic montages...")
    montages = find_montages(kept, show_name=show_name, episode_count=len(episodes))
    (OUTPUT_DIR / "montages.json").write_text(montages.model_dump_json(indent=2))
    print(f"  {len(montages.montages)} montages found")

    manifest = {
        "show_name": show_name,
        "episode_count": len(episodes),
        "scene_count": sum(len(e.scenes) for e in episodes),
        "beat_count": sum(len(s.beats) for e in episodes for s in e.scenes),
        "raw_candidate_count": len(raw_candidates),
        "shortlist_count": len(kept),
        "montage_count": len(montages.montages),
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nDone. Top 5 release order:\n")
    for p in ranking.promos[:5]:
        print(f"#{p.rank}  [{p.overall_score:.1f}]  Ep{p.episode_number} {p.start_seconds:.1f}s-{p.end_seconds:.1f}s")
        print(f"       Hook: {p.hook_description}")
        print(f"       Why:  {p.post_rationale}\n")

    print(f"Strategy: {ranking.overall_strategy}\n")
    print("\nRunning quality evaluation...")
    eval_report = run_evaluation(OUTPUT_DIR, {e.number: e for e in episodes})
    print(f"  Timestamp issues: {eval_report['timestamp_check']['issues_found']}")
    print(f"  Episodes with no strong candidate: {len(eval_report['coverage']['episodes_with_no_strong_candidate'])}/{eval_report['coverage']['episodes_total']}")
    print(f"  LLM judge agreement: {eval_report['llm_judge']['scorer_judge_agreement']}")
    print(f"  Mean score delta (scorer vs judge): {eval_report['llm_judge']['mean_score_delta']}")
    print(f"Outputs saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()