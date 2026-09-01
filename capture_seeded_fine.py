"""(a) Capture an actual usable roster for the seeded+fine result, not just
a fitness number - reruns the seeded+fine experiment (seed = Option 4's
roster), keeps the best of several attempts, and saves it via the normal
output_groups_to_csv() so it can be evaluated/used like any other candidate."""
import csv
import time
from multiprocessing import Pool

import genetic_grouping as g

GENERATIONS = 1000
POP_SIZE = 40
ATTEMPTS = 5

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

def run_attempt(attempt_id):
    seed_groups = build_seed_groups()
    seed_pop = [seed_groups] + [g.mutate(seed_groups, max_swaps=3) for _ in range(POP_SIZE - 1)]
    best_groups = g.genetic_algorithm(generations=GENERATIONS, pop_size=POP_SIZE, mutation_mode="fine",
                                       initial_population=seed_pop)
    return g.fitness(best_groups), best_groups

if __name__ == "__main__":
    seed_fitness = g.fitness(build_seed_groups())
    print(f"Seed (Option 4) fitness: {seed_fitness:.2f}")

    start = time.time()
    with Pool(processes=ATTEMPTS) as pool:
        results = pool.map(run_attempt, range(ATTEMPTS))
    elapsed = time.time() - start

    results.sort(key=lambda r: r[0], reverse=True)
    print(f"Done in {elapsed:.1f}s. Fitness values: {[f'{r[0]:.2f}' for r in results]}")

    best_fitness, best_groups = results[0]
    output_filename = f"groups/3720F26_groups_seededfine_{GENERATIONS}gens_{best_fitness:.1f}.csv"
    print(f"Best: {best_fitness:.2f} (delta vs seed: {best_fitness - seed_fitness:+.2f}) -> {output_filename}")
    g.output_groups_to_csv(best_groups, output_filename)
