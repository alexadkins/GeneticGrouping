import csv
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project root, so genetic_grouping/pair_teams/local_semester_config resolve regardless of cwd
import genetic_grouping as g

GENERATIONS = 1000
POP_SIZE = 40
# 4 configurations run at once (3 random-start modes + 1 seeded), so divide
# the machine's recommended parallelism across all 4 rather than per-mode.
ATTEMPTS_PER_MODE = max(1, g.RECOMMENDED_PARALLELISM // 4)

def run_random_start(args):
    mode, attempt_id = args
    best = g.genetic_algorithm(generations=GENERATIONS, pop_size=POP_SIZE, mutation_mode=mode)
    return mode, g.fitness(best)

def load_roster(path):
    teams = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            teams.setdefault(row["Team"], []).append(row["Name"])
    return teams

def build_seed_groups():
    import local_semester_config as cfg  # gitignored - real student names
    orig_teams = load_roster("3720F26_Teams_Final.csv")
    teams = {tid: list(names) for tid, names in orig_teams.items()}
    for tid, name in cfg.OPTION4_PULL["remove_map"].items():
        teams[tid] = [n for n in teams[tid] if n != name]
    teams[cfg.OPTION4_PULL["new_team_id"]] = list(cfg.OPTION4_PULL["new_team_names"])
    return [[g.students_by_name[n] for n in names] for names in teams.values()]

def run_seeded(args):
    mode, attempt_id = args
    seed_groups = build_seed_groups()
    seed_fitness = g.fitness(seed_groups)
    seed_pop = [seed_groups] + [g.mutate(seed_groups, max_swaps=3) for _ in range(POP_SIZE - 1)]
    best = g.genetic_algorithm(generations=GENERATIONS, pop_size=POP_SIZE, mutation_mode=mode,
                                initial_population=seed_pop)
    return mode, g.fitness(best), seed_fitness

def dispatch(job):
    kind = job[0]
    if kind == "random":
        return ("random",) + run_random_start(job[1:])
    return ("seeded",) + run_seeded(job[1:])

if __name__ == "__main__":
    print(f"=== Random-start comparison: coarse vs fine vs annealed, plus seeded+fine ===")
    print(f"{GENERATIONS} generations, pop {POP_SIZE}, {ATTEMPTS_PER_MODE} attempts per configuration\n", flush=True)

    random_jobs = [("random", mode, i) for mode in ["coarse", "fine", "annealed"] for i in range(ATTEMPTS_PER_MODE)]
    seeded_jobs = [("seeded", "fine", i) for i in range(ATTEMPTS_PER_MODE)]
    all_jobs = random_jobs + seeded_jobs

    start = time.time()
    with Pool(processes=len(all_jobs)) as pool:
        all_results = pool.map(dispatch, all_jobs)
    elapsed = time.time() - start

    random_results = [(item[1], item[2]) for item in all_results if item[0] == "random"]
    seeded_results = [(item[1], item[2], item[3]) for item in all_results if item[0] == "seeded"]

    by_mode = {}
    for mode, fit in random_results:
        by_mode.setdefault(mode, []).append(fit)

    for mode in ["coarse", "fine", "annealed"]:
        fits = sorted(by_mode[mode], reverse=True)
        print(f"{mode:<10} best={max(fits):.2f}  mean={sum(fits)/len(fits):.2f}  worst={min(fits):.2f}  all={['%.2f' % f for f in fits]}")

    print(f"\n=== Seeded (Option 4 roster) + fine mutation ===")
    seed_fitness = seeded_results[0][2]
    print(f"Seed fitness: {seed_fitness:.2f}")
    for mode, fit, _ in seeded_results:
        print(f"  attempt: {fit:.2f}  (delta vs seed: {fit - seed_fitness:+.2f})")
    best_seeded = max(fit for _, fit, _ in seeded_results)
    print(f"Best seeded+fine result: {best_seeded:.2f}  (delta vs seed: {best_seeded - seed_fitness:+.2f})")

    print(f"\nTotal wall time: {elapsed:.1f}s")
