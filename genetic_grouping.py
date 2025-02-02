import random, json
import numpy as np
import pandas as pd

input_csv = "001_data.csv"
output_csv = "001_groups.csv"

# Load student data from CSV
students_df = pd.read_csv(input_csv)
students = []

generations = 100        #Number of generations
population_size = 10    #Number of "classes" of groups
group_size = 4          #Number of desired students per group


graph_data = []

for _, row in students_df.iterrows():
    students.append({
        "name": row["name"],    #REQUIRED
        "gpa": row["gpa"],
        "leadership": row["leadership"],
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
        # KEEP PARTNER METRICS - not necessary for csv to contain them
        "primary_partner": row["primary_partner"] if pd.notna(row["primary_partner"]) else None,
        "additional_partners": row["additional_partners"].split(":") if pd.notna(row["additional_partners"]) else [],
        "avoid_partners": row["avoid_partners"].split(":") if pd.notna(row["avoid_partners"]) else []
    })


# "within" and "between"
#   Within to weigh within a group (e.g. time mgt for members of the group)
#   Between to weigh between groups (e.g. team's total skill avg across all teams)

# Negative values for low standard deviation (balanced distribution)
#   between/within groups should have similar avg numbers, e.g. GPA (between), time_mgt (within))
# Positive values for high standard devation (diverse distribution)
#   between/within groups should have different numbers, e.g. ?? (between), individual skills (within))
measures_weights = {
    "gpa": [-5, "between"],
    "leadership": [-3, "between"],
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
    "primary_partner": 15,
    "additional_partners": 3,
    "avoid_partners": -20
}


# STOP EDITING HERE

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

def fitness(groups):
    fitness_val = 0
    for metric, (weight, metric_type) in measures_weights.items():
        if metric_type == "between":
            stddev = np.std([np.mean([s[metric] for s in group]) for group in groups])
        else:
            stddev = np.mean([np.std([s[metric] for s in group]) for group in groups])
        fitness_val += weight * stddev
    
    for group in groups:
        for s in group:
            if s["primary_partner"] and s["primary_partner"] in [x["name"] for x in group]:
                fitness_val += partner_weights["primary_partner"]
            for ap in s["additional_partners"]:
                if ap in [x["name"] for x in group]:
                    fitness_val += partner_weights["additional_partners"]
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
    population = initialize_population(pop_size)
    for i in range(generations):
        # Keep top two parents; mutate them to create children
        keep_n_parents = 2
        parents = sorted(population, key=fitness, reverse=True)[:keep_n_parents]
        children = [mutate(parents[i%keep_n_parents]) for i in range(keep_n_parents,pop_size-1)]
        wildcard = initialize_population(1)     #Wildcard random generated class
        population = parents + children + wildcard

        p_fitness = fitness(parents[0])
        print(f"Best fitness at generation {i}: {p_fitness:.2f}")
        graph_data.append([i, p_fitness])
    
    # Print final classroom metrics
    for classroom in sorted(population, key=fitness, reverse=True):
        print(f"Final population fitnesses: {fitness(classroom):.2f}")

    # Return best fitted population
    return sorted(population, key=fitness, reverse=True)[0]


def output_groups_to_csv(groups, filename):
    output_data = []
    
    final_fitness = fitness(best_groups)
    weights = {metric: measures_weights[metric][0] for metric in measures_weights}
    output_data.append({
        "Group": "Weights:",
        "name": f"{generations} gens, {population_size} pop",
        **partner_weights,
        **weights, "Fitness": final_fitness})
    
    for i, group in enumerate(groups):
        group_metrics = {metric: np.mean([s[metric] for s in group]) for metric in measures_weights}
        fitness_score = fitness([group])
        output_data.append({"Group": i+1, **group_metrics, "Fitness": fitness_score})
        for student in group:
            output_data.append({"Group": i+1, **student})
        output_data.append({})
    df_output = pd.DataFrame(output_data)
    df_output.to_csv(filename, index=False)


# TEMP: remove
generations = 10        #Number of generations
population_size = 10    #Number of "classes" of groups

best_groups = genetic_algorithm(generations=generations, pop_size=population_size)
best_groups_fitness = fitness(best_groups)
print(f"Final Fitness: {best_groups_fitness:.2f}")
# output_groups_to_csv(best_groups, output_csv)

output_filename = f"groups/{output_csv.split('.csv')[0]}_{generations}gens_{best_groups_fitness:.1f}.csv"
print(f"Saving to {output_filename}")
output_groups_to_csv(best_groups, output_filename)

df_output = pd.DataFrame(graph_data)
df_output.to_csv(output_filename.split(".csv")[0]+"_graph.csv", index=False)
