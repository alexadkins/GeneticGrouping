"""Does exhaustive_local_search() let us drop the expensive dedicated "fine"
GA stage entirely? Compares:
  A) annealed(1000gen) + polish            - cheap, no fine stage
  B) annealed(1000gen) + fine(300gen) + polish - current rebalanced pipeline, now with polish added
Same attempt count for both, so wall time and result quality are directly
comparable. Jobs run through a Pool sized to RECOMMENDED_PARALLELISM so
excess jobs queue onto free workers rather than oversubscribing cores."""
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project root, so genetic_grouping/pair_teams/local_semester_config resolve regardless of cwd
import genetic_grouping as g

ATTEMPTS_PER_CONFIG = g.RECOMMENDED_PARALLELISM
POP_SIZE = 40

CONFIGS = {
    "A_annealed_polish": [
        {"generations": 1000, "mutation_mode": "annealed"},
    ],
    "B_annealed_fine_polish": [
        {"generations": 1000, "mutation_mode": "annealed"},
        {"generations": 300, "mutation_mode": "fine", "fine_max_swaps": 3},
    ],
}

def run_job(args):
    config_name, attempt_id = args
    start = time.time()
    best = g.staged_genetic_algorithm(CONFIGS[config_name], pop_size=POP_SIZE)
    elapsed = time.time() - start
    return config_name, g.fitness(best), elapsed, best

if __name__ == "__main__":
    jobs = [(name, i) for name in CONFIGS for i in range(ATTEMPTS_PER_CONFIG)]
    print(f"Running {len(jobs)} jobs ({ATTEMPTS_PER_CONFIG} per config) through {g.RECOMMENDED_PARALLELISM} workers\n")

    start = time.time()
    with Pool(processes=g.RECOMMENDED_PARALLELISM) as pool:
        results = pool.map(run_job, jobs)
    total_elapsed = time.time() - start

    by_config = {}
    for name, fit, elapsed, groups in results:
        by_config.setdefault(name, []).append((fit, elapsed, groups))

    print(f"Total wall time: {total_elapsed:.1f}s\n")
    for name, entries in by_config.items():
        fits = [e[0] for e in entries]
        times = [e[1] for e in entries]
        print(f"{name}: best={max(fits):.2f}  mean={sum(fits)/len(fits):.2f}  worst={min(fits):.2f}  "
              f"avg_attempt_time={sum(times)/len(times):.1f}s  all={['%.2f' % f for f in fits]}")

    print(f"\nReference: current best-ever is 88.77 (seeded+fine from Option 4)")

    for name, entries in by_config.items():
        best_fit, best_time, best_groups = max(entries, key=lambda e: e[0])
        out_path = f"groups/3720F26_groups_{name}_{best_fit:.1f}.csv"
        g.output_groups_to_csv(best_groups, out_path)
        print(f"Saved best {name} ({best_fit:.2f}) -> {out_path}")
