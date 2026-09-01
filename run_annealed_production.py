"""(b) Fresh from-scratch production batch using mutation_mode="annealed"
instead of the default "coarse", to see if it beats the existing 85.0
coarse-mode best as a from-scratch Option 2 candidate. Mirrors
genetic_grouping.py's run_attempt()/__main__ flow but doesn't touch the
main config block, since annealed mode isn't adopted as the default yet."""
import time
from multiprocessing import Pool

import genetic_grouping as g

GENERATIONS = 1000
POP_SIZE = 40
ATTEMPTS = 10

def run_attempt(attempt_id):
    g.highest_fitness = 0
    best_groups = g.genetic_algorithm(generations=GENERATIONS, pop_size=POP_SIZE, mutation_mode="annealed")
    best_fitness = g.fitness(best_groups)
    output_filename = f"groups/3720F26_groups_annealed_{GENERATIONS}gens_{best_fitness:.1f}.csv"
    print(f"Attempt #{attempt_id+1}: fitness {best_fitness:.2f} -> {output_filename}", flush=True)
    g.output_groups_to_csv(best_groups, output_filename)
    return best_fitness

if __name__ == "__main__":
    start = time.time()
    with Pool(processes=ATTEMPTS) as pool:
        results = pool.map(run_attempt, range(ATTEMPTS))
    elapsed = time.time() - start
    results.sort(reverse=True)
    print(f"\nDone in {elapsed:.1f}s. Fitness values: {[f'{r:.2f}' for r in results]}")
    print(f"Best: {results[0]:.2f}  Mean: {sum(results)/len(results):.2f}")
