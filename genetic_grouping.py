import random, csv
import numpy as np

students = []

with open('CPSC3720_001.csv') as f:
    reader = csv.reader(f)
    
    for row in reader:        
        student = {"id": row[0], 
                   "partner": row[-1],
                   "gpa": float(row[-2]),
                   "ethic": float(row[-5]),
                   "leadership": int(row[6]),
                   "skills": [int(x) for x in row[1:11]]}
        
        students.append(student)

# # Example student data structure
# students = [
#     {"id": 1, "gpa": 3.5, "ethic": 8, "skills": [7, 6, 5, 4, 8, 7, 6, 5, 4, 3], "leadership": 3, "partner": 2},
#     {"id": 2, "gpa": 3.7, "ethic": 7, "skills": [6, 7, 8, 5, 6, 7, 8, 5, 6, 7], "leadership": 3, "partner": 1},
#     {"id": 3, "gpa": 2.9, "ethic": 6, "skills": [5, 4, 3, 2, 5, 6, 7, 8, 9, 2], "leadership": 3, "partner": None},
#     {"id": 4, "gpa": 3.2, "ethic": 9, "skills": [8, 7, 6, 5, 4, 3, 2, 1, 5, 6], "leadership": 3, "partner": None},
#     {"id": 5, "gpa": 3.3, "ethic": 8, "skills": [7, 6, 5, 4, 3, 2, 1, 9, 8, 7], "leadership": 3, "partner": 6},
#     {"id": 6, "gpa": 3.3, "ethic": 3, "skills": [7, 6, 5, 4, 3, 2, 1, 9, 8, 7], "leadership": 3, "partner": 5},
#     {"id": 7, "gpa": 2.0, "ethic": 2, "skills": [7, 6, 5, 4, 3, 2, 1, 9, 8, 7], "leadership": 3, "partner": None},
#     {"id": 8, "gpa": 4.0, "ethic": 2, "skills": [7, 6, 5, 4, 3, 2, 1, 9, 8, 7], "leadership": 3, "partner": None},
    
#     # Add more students as needed
# ]

group_size = 4  # Adjust as needed
num_groups = len(students) // group_size
skills_quant = 10

# Factor weights
gpa_weight = 5
ethic_weight = 3
leadership_weight = 2
skill_within_weight = 1
skill_between_weight = 1
partner_weight = 10


def initialize_population(pop_size=10):
    population = []
    for _ in range(pop_size):
        shuffled = students[:]
        random.shuffle(shuffled)
        groups = [shuffled[i:i+group_size] for i in range(0, len(shuffled), group_size)]
        population.append(groups)
    return population

def fitness(groups, desc_output=False):
    gpa_stddev = np.std([np.mean([s["gpa"] for s in group]) for group in groups])
    ethic_stddev = np.mean([np.std([s["ethic"] for s in group]) for group in groups])
    leadership_stddev = np.mean([np.std([s["leadership"] for s in group]) for group in groups])
    skill_stddev_within = np.mean([np.mean([np.std([s["skills"][i] for s in group]) for i in range(skills_quant)]) for group in groups])
    skill_stddev_between = np.std([np.mean([s["skills"][i] for s in group]) for i in range(skills_quant) for group in groups])
    # partner_bonus = sum(1 for group in groups for s in group if s.get("partner") in [x["id"] for x in group])
    partner_bonus = sum([1 for group in groups for s in group if s["partner"] in [x["id"] for x in group]])
        
    # Higher fitness is better
    fitness_val = (
        - (gpa_stddev * gpa_weight)
        - (ethic_stddev * ethic_weight)
        - (leadership_stddev * leadership_weight)
        + (skill_stddev_within * skill_within_weight)
        - (skill_stddev_between * skill_between_weight)
        + (partner_bonus * partner_weight)
    )
    
    if desc_output:
        print("\n")
        print("Groups: ")
        for group in groups:
            print(f"{[s['id'] for s in group]}")
        
        print(f"GPA STD: {gpa_stddev:0.3f}, Ethic STD: {ethic_stddev:0.3f} Partner Bonus: {partner_bonus:0.3f}")
        print(f"Skill STDW: {skill_stddev_within:0.3f}, Skill STDB: {skill_stddev_between:0.3f} ")
        print(f"GPA Weighted: \t\t{-(gpa_stddev * gpa_weight):.2f}")
        print(f"Ethic Weighted: \t{-(ethic_stddev * ethic_weight):.2f}")
        print(f"Leadership Weighted: \t{-(leadership_stddev * leadership_weight):.2f}")
        print(f"Partner Weighted: \t{(partner_bonus * partner_weight):.2f}")
        print(f"Skills Within: \t\t{-(skill_stddev_within * skill_within_weight):.2f}")
        print(f"Skills Between: \t{(skill_stddev_between * skill_between_weight):.2f}")
        print(f"Fitness: ", fitness_val)
        
    return fitness_val

def select_parents(population):
    # print("\n\n--NEW POP--")
    
    # for pop in sorted(population, key=fitness, reverse=True)[:2]:
    #     fitness(pop, True)
        # print(pop)
    return sorted(population, key=fitness, reverse=True)[:2]

def crossover(parent1, parent2):
    all_students = list({s["id"]: s for group in parent1 + parent2 for s in group}.values())  # Ensure uniqueness
    random.shuffle(all_students)
    child = [all_students[i:i+group_size] for i in range(0, len(all_students), group_size)]
    return child if len(child) == num_groups else parent1  # Ensure valid group count

def mutate(groups):
    if random.random() < 0.2:  # 20% mutation chance
        flat_students = list({s["id"]: s for group in groups for s in group}.values())  # Ensure uniqueness
        random.shuffle(flat_students)
        new_groups = [flat_students[i:i+group_size] for i in range(0, len(flat_students), group_size)]
        return new_groups if len(new_groups) == num_groups else groups
    return groups

def genetic_algorithm(generations=1000, pop_size=num_groups):
    population = initialize_population(pop_size)
    for _ in range(generations):
        parents = select_parents(population)
        children = [crossover(*parents) for _ in range(pop_size - len(parents))]
        population = parents + [mutate(child) for child in children]
    return sorted(population, key=fitness, reverse=True)[0]



if __name__ == "__main__":
    best_groups = genetic_algorithm()
    # fitness(best_groups, True)
    for i, group in enumerate(best_groups):
        print(f"Group {i+1}: {[s['id'] for s in group]}")
        # print(f"\tGPA Average: {np.mean([s['gpa'] for s in group])}")
        # print(f"\t\t GPAs: {[s['gpa'] for s in group]}")
        # print(f"\tEthic Average: {np.mean([s['ethic'] for s in group])}")