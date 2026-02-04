import random, json
import numpy as np
import pandas as pd
from multiprocessing import Pool

# CSV file names
input_csv = "s26_data.csv"
output_csv = "2_s26_groups_lowergrpweights_v2.csv"

#Number of desired students per group
group_size = 4

# Load student data from CSV - DO NOT EDIT
students_df = pd.read_csv(input_csv)
students = []
graph_data = []

# Desired student information from csv - remote unwanted metrics
for _, row in students_df.iterrows():
    students.append({
        "name": row["name"],    #REQUIRED
        "gpa": row["gpa"],
        "leadership": row["leadership"],
        "leadership2": row["leadership"],
        "time_mgt": row["time_mgt"],
        "skills_total": row["skills_total"],
        "agile": row["agile"],
        "postman": row["postman"],
        "json_yaml": row["json_yaml"],
        "apis": row["apis"],
        "aws": row["aws"],
        "lambda": row["lambda"],
        "javascript": row["javascript"],
        "python": row["python"],
        "node": row["node"],
        "git": row["git"],
        "primary_partner": row["primary_partner"] if pd.notna(row["primary_partner"]) else None,
        "additional_partners": row["additional_partners"].split(":") if pd.notna(row["additional_partners"]) else [],
        "avoid_partners": row["avoid_partners"].split(":") if pd.notna(row["avoid_partners"]) else []
    })

    # df.to_dict(orient="records").fillna({"primary_partner": None, ...})


# "within" and "between"
#   Within to weigh within a group (e.g. time mgt for members of the group)
#   Between to weigh between groups (e.g. team's total skill avg across all teams)

# Negative values for low standard deviation (balanced distribution)
#   between/within groups should have similar avg numbers, e.g. GPA (between), time_mgt (within))
# Positive values for high standard devation (diverse distribution)
#   between/within groups should have different numbers, e.g. ?? (between), individual skills (within))
measures_weights = {
    "gpa": [0, "between"],
    "leadership": [-4, "between"],
    "leadership2": [4, "within"],
    "time_mgt": [-3, "within"],
    "skills_total": [-3, "between"],
    "agile": [1, "within"],
    "postman": [1, "within"],
    "json_yaml": [1, "within"],
    "apis": [1, "within"],
    "aws": [1, "within"],
    "lambda": [1, "within"],
    "javascript": [1, "within"],
    "python": [1, "within"],
    "node": [1, "within"],
    "git": [1, "within"]
}

# Do not delete
partner_weights = {
    "primary_partner": 10,
    "additional_partners": 3,
    "avoid_partners": -20
}

# Algorithm values
generations = 1000        #Number of generations (preference of 1000 because I'm extra)
population_size = 10       #Number of "classes" (populations) of groups
attempts = 10              #Number of times to re-run generation and produce output (preference of 10 because I'm extra)

# Run controls
parallelism = True              # Run all attempts in parallel with multiprocessing (DO NOT USE WITH PROGRESS)
progress = not parallelism      # Report run progress with fitness updates (DO NOT USE WITH PARALLELISM)
graph = True                    # Generate fitness over generation data for graphing

# --- STOP EDITING HERE ---

highest_fitness = 0

num_groups = len(students) // group_size
small_groups = 0

if len(students) % group_size != 0:
    num_groups += 1
    small_groups = group_size - len(students) % group_size

def print_json(json_obj: dict):
    print(json.dumps(json_obj, indent=2))

def split_into_groups(students):
    groups = []
    for i in range(0, (num_groups-small_groups)*group_size, group_size):
        groups.append(students[i:i+group_size])
    for i in range((num_groups-small_groups)*group_size, len(students), group_size-1):
        groups.append(students[i:i+group_size-1])

    return groups

# Create n classrooms of groups for population
def initialize_population(pop_size=10):
    population = []
    for _ in range(pop_size):
        shuffled = students[:]
        random.shuffle(shuffled)
        groups = split_into_groups(shuffled)
        population.append(groups)
    return population

def fitness(groups, exclude_partners = False):
    fitness_val = 0
    # stddev = (np.std if metric_type == "between" else np.mean)([(np.mean if metric_type == "between" else np.std)([s[metric] for s in group]) for group in groups])
    # getattr(np, "mean" if metric_type == "between" else "std")

    for metric, (weight, metric_type) in measures_weights.items():
        if metric_type == "between":
            stddev = np.std([np.mean([s[metric] for s in group]) for group in groups])
        else:
            stddev = np.mean([np.std([s[metric] for s in group]) for group in groups])
        fitness_val += weight * stddev

    # If testing whole population, not singular group:
    if len(groups) > 1:
        # Penalty for high variance in group fitness scores - ignores partners
        fitness_stddev = np.std([fitness([group], exclude_partners=True) for group in groups])
        fitness_val -= fitness_stddev 

    if exclude_partners:
        return fitness_val
    
    for group in groups:
        for s in group:
            if "primary_partner" in s and s["primary_partner"] and s["primary_partner"] in [x["name"] for x in group]:
                fitness_val += partner_weights["primary_partner"]
            if "additional_partners" in s:
                for ap in s["additional_partners"]:
                    if ap in [x["name"] for x in group]:
                        fitness_val += partner_weights["additional_partners"]
            if "avoid_partners" in s:
                for ap in s["avoid_partners"]:
                    if ap in [x["name"] for x in group]:
                        fitness_val += partner_weights["avoid_partners"]

    return fitness_val

def mutate(groups):
    # Get ordered student list from parent
    flat_students = list({s["name"]: s for group in groups for s in group}.values())
    
    # Randomly swap some students in parent to create new child
    mutation_level = random.random()
    swaps = int(mutation_level * len(flat_students))
    for _ in range(swaps):
        s1 = random.randint(0,len(flat_students)-1)
        s2 = random.randint(0,len(flat_students)-1)
        flat_students[s1], flat_students[s2] = flat_students[s2], flat_students[s1]

    # Split students back into groups with proper sizes
    new_groups = split_into_groups(flat_students)

    return new_groups

def genetic_algorithm(generations=100, pop_size=10):
    global highest_fitness
    population = initialize_population(pop_size)
    for gen in range(generations):
        # Keep top n parents; mutate them to create children
        keep_n_parents = 3
        # parents = sorted(population, key=fitness, reverse=True)[:keep_n_parents]

        parents = sorted(population, key=fitness, reverse=True)
        top_parents = [parents[0]]

        # Ignore duplicate parents
        i = 1
        while len(top_parents) < keep_n_parents and i < len(parents):
            if parents[i] not in top_parents:
                top_parents.append(parents[i])
            i += 1

        # Unless there are too many duplicates
        if len(top_parents) != keep_n_parents:
            parents = sorted(population, key=fitness, reverse=True)[:keep_n_parents]
        else:
            parents = top_parents

        # Mutate children. Add one completely random wildcard.
        children = [mutate(parents[i%keep_n_parents]) for i in range(keep_n_parents,pop_size-1)]
        wildcard = initialize_population(1)     #Wildcard random generated class
        population = parents + children + wildcard

        if graph or progress:
            # For outputting highest found fitness 
            p_fitness = fitness(parents[0])

            if progress:
                if p_fitness > highest_fitness:
                    print(f"Best fitness updated at generation {gen}: {p_fitness:.2f}", flush=True)
                    highest_fitness = p_fitness
        
            if graph:
                # For graphing highest fitness per generation
                graph_data.append([gen, p_fitness])
    
    if progress:
        # Print final classroom/population metrics
        for classroom in sorted(population, key=fitness, reverse=True):
            print(f"Final population fitnesses: {fitness(classroom):.2f}")

    # Return best fitted population
    return sorted(population, key=fitness, reverse=True)[0]

def output_groups_to_csv(groups, filename):
    output_data = []
    
    final_fitness = fitness(groups)
    weights = {metric: measures_weights[metric][0] for metric in measures_weights}
    output_data.append({
        "Group": "Weights:",
        "Fitness": final_fitness,
        "name": f"{generations} gens, {population_size} pop",
        **partner_weights,
        **weights})
    
    for i, group in enumerate(groups):
        group_metrics = {metric: np.mean([s[metric] for s in group]) for metric in measures_weights}
        fitness_score = float(fitness([group]))
        fitness_score_sans_partners = float(fitness([group], exclude_partners=True))
        output_data.append({"Group": i+1, **group_metrics, "Fitness": f"{fitness_score, fitness_score_sans_partners}"})
        for student in group:
            output_data.append({"Group": i+1, **student})
        output_data.append({})
    df_output = pd.DataFrame(output_data)
    df_output.to_csv(filename, index=False)

def run_attempt(attempt_id):
    global highest_fitness
    highest_fitness = 0
    
    best_groups = genetic_algorithm(generations=generations, pop_size=population_size)
    best_groups_fitness = fitness(best_groups)

    output_filename = f"groups/{output_csv.split('.csv')[0]}_{generations}gens_{best_groups_fitness:.1f}.csv"

    print(f"""\nAttempt #{attempt_id+1}\n\tFinal Fitness: {best_groups_fitness:.2f}\n\tSaving to {output_filename}""", flush=True)

    output_groups_to_csv(best_groups, output_filename)

    # Output fitness per generation - for graphing purposes
    global graph_data
    df_output = pd.DataFrame(graph_data)
    graph_data = []
    df_output.to_csv(output_filename.split(".csv")[0]+"_graph.csv", index=False)

if __name__ == "__main__":
    if parallelism:
        with Pool(processes=attempts) as pool:
            pool.map(run_attempt, range(attempts))
        
    else:
        for i in range(attempts):
            run_attempt(i)