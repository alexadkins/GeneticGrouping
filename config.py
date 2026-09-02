"""Single place to configure this pipeline's per-semester settings.

prepare_data.py, genetic_grouping.py, and pair_teams.py all import from
here instead of defining their own copies. genetic_grouping.py uses
`from config import *` (not `import config as cfg`), since its internal
code already references these values by bare name throughout; the other
scripts use `import config as cfg` and prefix each reference.

Nothing below this docstring depends on any of this project's other
scripts - config.py stays a leaf module so there's no import cycle.
"""
import os

# ============================================================
# Shared / cross-script
# ============================================================

# Recommended worker-process count for any parallel batch in this project:
# one less than the machine's core count, not the full count. Matching
# `attempts`/`processes` exactly to the core count leaves no headroom for
# the OS, the parent process orchestrating the Pool, or anything else
# running on the machine - each worker then competes for CPU time instead
# of getting uncontended use of its own core, which in practice makes both
# the batch job AND the rest of the machine slower/jankier. Recomputed
# fresh on every run, so it's correct on whatever machine actually runs
# this - never hardcode a specific core count.
RECOMMENDED_PARALLELISM = max(1, (os.cpu_count() or 4) - 1)


# ============================================================
# prepare_data.py
# ============================================================

# Raw Qualtrics export (3 header rows: field names, question text, ImportId
# JSON) - DO NOT EDIT the file itself, just the path below if it moves.
raw_csv = "3720F26SurveyData.csv"

# prepare_data.py writes here; genetic_grouping.py's input_csv (below) reads
# from here - keep the two in sync if you ever rename this.
prepared_csv = "3720F26SurveyData_prepared.csv"

# Qualtrics "expertise" slider order (QID7_1..13) -> student dict keys
EXPERTISE_FIELDS = [
    "agile", "postman", "json_yaml", "apis", "aws", "lambda",
    "databases", "javascript", "python", "node", "git",
    "leadership", "presentation",
]

# Skill sliders rolled into the "skills_total" between-group balance metric.
# Leadership and presentation are soft skills, weighted separately - excluded here.
SKILLS_TOTAL_FIELDS = [
    "agile", "postman", "json_yaml", "apis", "aws", "lambda",
    "databases", "javascript", "python", "node", "git",
]


# ============================================================
# genetic_grouping.py
# ============================================================

# CSV file names. input_csv normally matches prepared_csv above (see note
# there) - kept as its own setting in case you ever want to point
# genetic_grouping.py at a different/hand-prepared CSV without re-running
# prepare_data.py.
input_csv = "3720F26SurveyData_prepared.csv"
output_csv = "3720F26_groups.csv"

#Number of desired students per group
group_size = 4

# If True, round the team count up by one whenever it would otherwise be odd
# (e.g. for pairing teams up at tables, cross-team activities, etc.). Never
# exceeds group_size for any team - the extra team absorbs students by making
# some teams one smaller instead, same as the existing uneven-class-size
# handling below.
enforce_even_teams = True

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
attempts = RECOMMENDED_PARALLELISM  #Number of times to re-run generation and produce output - defaults to (cores - 1) on whatever machine runs this, so all attempts run in one parallel wave without starving the rest of the machine. Override with a specific number if you want more/fewer.

# Mutation strategy: "coarse" (broad random reshuffling every mutation -
# explores well from scratch but can never do fine local refinement),
# "fine" (small bounded swaps only - local search near an existing
# solution), or "annealed" (starts coarse, shifts toward fine as
# generations progress - broad exploration early, local refinement late).
# See README's "Mutation strategy and polish" for the empirical comparison
# behind this default.
mutation_mode = "annealed"

# Exact local search polish applied to each attempt's final result: checks
# EVERY possible 2-student swap between every pair of teams (not a random
# sample like mutation does), and keeps applying whichever improves fitness
# the most until none do - a genuine, verified local optimum, not just "we
# tried some things." Cheap (seconds, since the swap neighborhood for a
# class this size is only ~1000 possibilities) and can only help or do
# nothing, so there's essentially no downside to leaving this on. Testing
# showed annealed+polish alone matches or beats a much more expensive
# dedicated "fine" refinement stage, so that extra stage isn't needed.
polish = True

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


# ============================================================
# pair_teams.py
# ============================================================

# --- EDIT PER SEMESTER: room/table layout ---
# Ordered list of table identifiers, from most spacious/preferred for larger
# team-pairs down to least preferred (e.g. a room's corners and open tables
# first, cramped or awkward ones last). Only the order matters - however
# many tiers or however irregular the actual room shape is, just rank them.
# Must have at least as many entries as there will be team-pairs. Update
# this whenever the class meets somewhere new; nothing else needs to change
# (assign_tables() auto-extends with generic labels if this is ever too
# short for the class size).
# Current room (3720RoomLayout.png): A, C, F, H are corners (most open);
# B, E, G are mid-wall edges; D is the sole fully-interior table.
TABLE_PRIORITY = ["A", "C", "F", "H", "B", "E", "G", "D"]
