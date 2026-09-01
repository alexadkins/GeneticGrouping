import random, json
import numpy as np
import pandas as pd
from multiprocessing import Pool

# CSV file names
input_csv = "3720F26SurveyData_prepared.csv"
output_csv = "3720F26_groups.csv"

#Number of desired students per group
group_size = 4

# Algorithm values
# Tuned against this class's real data (49 students): fitness was still
# climbing well past 100 generations/pop 10 (the old defaults) - e.g. at
# pop_size=20, fitness kept improving from ~49 (gen 100) to ~68 (gen 300)
# before flattening out. A real 10-attempt production run at these settings
# (generations=300, population_size=20) takes ~30s on a 10-core machine and
# lands a best fitness around 70, vs. ~50 at the old 100/10 - a meaningful,
# not marginal, improvement for a one-time per-semester batch job. Push
# higher (e.g. population_size=40) for further gains if you have the ~2-4x
# longer runtime to spare; diminishing returns set in well past this point.
generations = 1000        #Number of generations (preference of 1000 because I'm extra)
population_size = 40       #Number of "classes" (populations) of groups
attempts = 10              #Number of times to re-run generation and produce output - matches this machine's 10 cores, so all attempts run in one parallel wave

# Run controls
parallelism = True     # Run all attempts in parallel with multiprocessing (DO NOT USE WITH PROGRESS)
progress = False        # Report run progress with fitness updates (DO NOT USE WITH PARALLELISM)
graph = False            # Generate fitness over generation data for graphing

# "within" and "between"
#   Within to weigh within a group (e.g. time mgt for members of the group)
#   Between to weigh between groups (e.g. team's total skill avg across all teams)

# Negative values for low standard deviation (balanced distribution)
#   between/within groups should have similar avg numbers, e.g. GPA (between), time_mgt (within))
# Positive values for high standard devation (diverse distribution)
#   between/within groups should have different numbers, e.g. ?? (between), individual skills (within))

# Each metric maps to a LIST of [weight, "between"/"within"] pairs, not just
# one - a metric can be scored multiple ways at once and the contributions
# add up. E.g. gpa below is scored both ways: keep team averages level
# (between, the fairness floor - no team gets stacked academically) AND mix
# GPA levels within each team (within, positive - same "diversify within a
# team" philosophy already used for every skill slider below). These two
# terms complement rather than fight each other. Most metrics only need one
# entry, but wrap it in a list regardless for a consistent format.
measures_weights = {
    "gpa": [[-6, "between"], [1.5, "within"]],
    "leadership": [[-4, "between"]],
    "time_mgt": [[-3, "within"]],
    "submission_time": [[-3, "within"]],
    "skills_total": [[-3, "between"]],
    "agile": [[1, "within"]],
    "postman": [[1, "within"]],
    "json_yaml": [[1, "within"]],
    "apis": [[1, "within"]],
    "aws": [[1, "within"]],
    "lambda": [[1, "within"]],
    "javascript": [[1, "within"]],
    "python": [[1, "within"]],
    "node": [[1, "within"]],
    "git": [[1, "within"]],
    "databases": [[1, "within"]],
    "presentation": [[1, "within"]]
}

# Do not delete
# Weight for a preferred pick (primary_partner + additional_partners, in that
# rank order) by its rank position - index 0 is your 1st choice, 1 is your
# 2nd, etc. Scaled to be a strong nudge comparable to a single
# measures_weights term (~1-4 typical), not an override: with ~68 partner
# requests active in a 49-student class, a flat +20/-20 per match totaled
# 200+ across a grouping - dwarfing the entire measures_weights block
# combined (~10-20) and making GPA/skill balance functionally irrelevant to
# the GA's choices. Extra ranks beyond this list's length score 0.
partner_rank_weights = [3, 1.5, 0.75]

# Credit for a preferred pick that ISN'T reciprocated (the survey told
# students "each preferred name indicated must also select you in their
# answer to be considered" - not everyone's picks lined up both ways).
# 1.0 = ignore reciprocation entirely, 0.5 = still worth something but less
# than a confirmed mutual match, 0.0 = a one-sided pick counts for nothing.
one_sided_partner_credit = 0.5

# Strict mode: only mutual (reciprocated) picks count at all, matching the
# survey's stated rule exactly. Overrides one_sided_partner_credit to 0
# regardless of its configured value above.
strict_reciprocity = False

# avoid_partners has no reciprocity concept - wanting to avoid someone
# doesn't need their consent to be honored. It's also enforced as a hard
# constraint (enforce_avoid_constraints, below), so this weight is mostly a
# backstop for the (essentially unreachable) case where that repair fails.
avoid_partner_weight = -4

# Availability overlap is a coverage metric (count of shared free slots), not a
# between/within variance metric, so it doesn't fit measures_weights - it gets
# its own weight here. Positive = more group-wide overlap is rewarded. No hard
# penalty for zero-overlap groups; they simply score 0 on this term. Scaled down
# for the same reason as the partner weights above - a fully-optimized grouping
# can have 20+ total shared slots across groups, which at weight 1 rivaled the
# entire measures_weights block.
availability_weight = 0.25

# Weekly availability: 4 time blocks (Morning/Early Afternoon/Late Afternoon/Evening)
# x 7 days (Sun-Sat) = 28 possible slots. Prepared CSV holds one column per time
# block (availability_1..4), each a comma-separated list of free days.
AVAILABILITY_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
AVAILABILITY_BLOCKS = 4
NUM_AVAILABILITY_SLOTS = AVAILABILITY_BLOCKS * len(AVAILABILITY_DAYS)

def parse_availability(row):
    slots = set()
    for block in range(AVAILABILITY_BLOCKS):
        val = row[f"availability_{block + 1}"]
        if pd.notna(val) and val:
            for day in val.split(","):
                day = day.strip()
                if day in AVAILABILITY_DAYS:
                    slots.add(block * len(AVAILABILITY_DAYS) + AVAILABILITY_DAYS.index(day))
    return slots

AVAILABILITY_BLOCK_LABELS = ["Morning", "Early Afternoon", "Late Afternoon", "Evening"]

def format_availability(slots):
    by_block = {}
    for slot in sorted(slots):
        block, day = divmod(slot, len(AVAILABILITY_DAYS))
        by_block.setdefault(AVAILABILITY_BLOCK_LABELS[block], []).append(AVAILABILITY_DAYS[day])
    return "; ".join(f"{block}: {','.join(days)}" for block, days in by_block.items())

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
        "time_mgt": row["time_mgt"],
        "submission_time": row["submission_time"],
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
        "databases": row["databases"],
        "presentation": row["presentation"],
        "availability": parse_availability(row),
        "primary_partner": row["primary_partner"] if pd.notna(row["primary_partner"]) else None,
        "additional_partners": row["additional_partners"].split(":") if pd.notna(row["additional_partners"]) else [],
        "avoid_partners": row["avoid_partners"].split(":") if pd.notna(row["avoid_partners"]) else []
    })

    # df.to_dict(orient="records").fillna({"primary_partner": None, ...})

# --- STOP EDITING HERE ---

highest_fitness = 0

# Z-score stats (population mean/std) per measures_weights metric, computed once
# against the whole class. fitness() scores metrics in these standardized units
# rather than raw values, so a metric's weight reflects its intended relative
# importance instead of being skewed by its raw scale (e.g. skills_total, a sum
# of 11 sliders, would otherwise dwarf gpa's narrow 0-4 range for the same weight).
metric_stats = {
    metric: (np.mean([s[metric] for s in students]), np.std([s[metric] for s in students]))
    for metric in measures_weights
}

def zscore(student, metric):
    mean, std = metric_stats[metric]
    return (student[metric] - mean) / std if std > 0 else 0.0

# Combined, rank-ordered preferred-partner list (primary_partner first, then
# additional_partners in rank order) - lets fitness() score any ranked pick
# through a single mechanism instead of two separate flat categories.
def preferred_list(student):
    picks = [student["primary_partner"]] if student.get("primary_partner") else []
    return picks + student.get("additional_partners", [])

# Readable single-column rendering of preferred_list, for output CSVs -
# replaces separate primary_partner/additional_partners columns with one
# rank-ordered column matching the ranking system fitness() actually scores.
def format_preferred_partners(student):
    return "; ".join(f"{i+1}. {name}" for i, name in enumerate(preferred_list(student)))

# Lookup by name, used to check whether a pick is reciprocated (i.e. whether
# the picked student has you anywhere in their own preferred list).
students_by_name = {s["name"]: s for s in students}

num_groups = len(students) // group_size
small_groups = 0

if len(students) % group_size != 0:
    num_groups += 1
    small_groups = group_size - len(students) % group_size

def print_json(json_obj: dict):
    print(json.dumps(json_obj, indent=2))

# avoid_partners is a hard constraint, not just a fitness penalty: a soft
# weight can only make violations unlikely, not guarantee "never." Checked
# both directions since avoid_partners isn't necessarily mutual (A avoiding B
# doesn't imply B avoided A).
def has_avoid_conflict(student, other_members):
    other_names = {m["name"] for m in other_members}
    if any(name in other_names for name in student["avoid_partners"]):
        return True
    return any(student["name"] in m["avoid_partners"] for m in other_members)

def group_has_conflict(group):
    return any(has_avoid_conflict(s, group[:i] + group[i+1:]) for i, s in enumerate(group))

def find_conflict(groups):
    for gi, group in enumerate(groups):
        for i, s in enumerate(group):
            if has_avoid_conflict(s, group[:i] + group[i+1:]):
                return gi, i
    return None

def enforce_avoid_constraints(groups, max_attempts=1000):
    groups = [list(group) for group in groups]
    for _ in range(max_attempts):
        loc = find_conflict(groups)
        if loc is None:
            return groups
        gi, i = loc
        student = groups[gi][i]
        candidates = [(gj, j) for gj in range(len(groups)) if gj != gi for j in range(len(groups[gj]))]
        random.shuffle(candidates)
        resolved = False
        for gj, j in candidates:
            other = groups[gj][j]
            trial_gi = groups[gi][:i] + [other] + groups[gi][i+1:]
            trial_gj = groups[gj][:j] + [student] + groups[gj][j+1:]
            if not group_has_conflict(trial_gi) and not group_has_conflict(trial_gj):
                groups[gi], groups[gj] = trial_gi, trial_gj
                resolved = True
                break
        if not resolved:
            # No single swap clears this conflict - perturb randomly to escape
            # the local deadlock and retry rather than looping on the same spot.
            gj, j = random.choice(candidates)
            groups[gi][i], groups[gj][j] = groups[gj][j], groups[gi][i]
    if find_conflict(groups) is not None:
        print("WARNING: could not fully resolve avoid_partners conflicts - "
              "constraints may be too dense for group_size", flush=True)
    return groups

def split_into_groups(students):
    groups = []
    for i in range(0, (num_groups-small_groups)*group_size, group_size):
        groups.append(students[i:i+group_size])
    for i in range((num_groups-small_groups)*group_size, len(students), group_size-1):
        groups.append(students[i:i+group_size-1])

    return enforce_avoid_constraints(groups)

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

    for metric, weight_specs in measures_weights.items():
        for weight, metric_type in weight_specs:
            if metric_type == "between":
                stddev = np.std([np.mean([zscore(s, metric) for s in group]) for group in groups])
            else:
                stddev = np.mean([np.std([zscore(s, metric) for s in group]) for group in groups])
            fitness_val += weight * stddev

    # Availability overlap bonus: for each group, count weekly time slots where
    # every member is free, and reward more shared availability.
    for group in groups:
        overlap = sum(all(slot in s["availability"] for s in group) for slot in range(NUM_AVAILABILITY_SLOTS))
        fitness_val += availability_weight * overlap

    # If testing whole population, not singular group:
    if len(groups) > 1:
        # Penalty for high variance in group fitness scores - ignores partners
        fitness_stddev = np.std([fitness([group], exclude_partners=True) for group in groups])
        fitness_val -= fitness_stddev 

    if exclude_partners:
        return fitness_val

    one_sided_credit = 0 if strict_reciprocity else one_sided_partner_credit

    for group in groups:
        names = [x["name"] for x in group]
        for s in group:
            for rank, pick in enumerate(preferred_list(s)):
                if rank >= len(partner_rank_weights):
                    break
                if pick in names:
                    reciprocated = s["name"] in preferred_list(students_by_name.get(pick, {}))
                    credit = 1.0 if reciprocated else one_sided_credit
                    fitness_val += partner_rank_weights[rank] * credit
            for ap in s["avoid_partners"]:
                if ap in names:
                    fitness_val += avoid_partner_weight

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
    # A metric with only one [weight, type] entry keeps its plain column name
    # (e.g. "leadership"); a metric scored multiple ways (e.g. gpa, scored
    # both between and within) gets one suffixed column per entry so both
    # weights are visible (e.g. "gpa_between", "gpa_within").
    weights = {}
    for metric, weight_specs in measures_weights.items():
        for weight, metric_type in weight_specs:
            key = metric if len(weight_specs) == 1 else f"{metric}_{metric_type}"
            weights[key] = weight
    partner_weights_display = {
        **{f"partner_rank_{i+1}_weight": w for i, w in enumerate(partner_rank_weights)},
        "one_sided_partner_credit": 0 if strict_reciprocity else one_sided_partner_credit,
        "avoid_partner_weight": avoid_partner_weight,
    }
    output_data.append({
        "Group": "Weights:",
        "Fitness": final_fitness,
        "name": f"{generations} gens, {population_size} pop",
        **partner_weights_display,
        **weights})
    
    for i, group in enumerate(groups):
        group_metrics = {metric: np.mean([s[metric] for s in group]) for metric in measures_weights}
        fitness_score = fitness([group])
        fitness_score_sans_partners = fitness([group], exclude_partners=True)
        shared_slots = sum(all(slot in s["availability"] for s in group) for slot in range(NUM_AVAILABILITY_SLOTS))
        output_data.append({"Group": i+1, **group_metrics, "Fitness": f"{fitness_score, fitness_score_sans_partners}", "shared_availability_slots": shared_slots})
        for student in group:
            display = {}
            for key, value in student.items():
                if key == "primary_partner":
                    display["preferred_partners"] = format_preferred_partners(student)
                elif key == "additional_partners":
                    continue
                elif key == "availability":
                    display["availability"] = format_availability(value)
                else:
                    display[key] = value
            output_data.append({"Group": i+1, **display})
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