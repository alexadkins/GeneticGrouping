Genetic-algorithm team formation from a Qualtrics skill/preference survey.
Built for CPSC 3720, but works for any Qualtrics survey exporting a `name`
column plus numeric skill/preference metrics. Tested and developed with
Python 3.10.0. Uses [uv](https://docs.astral.sh/uv/) for dependencies - run
scripts with `uv run python <script>.py` from the project root.

## Quick start (each semester)

1. **Set up the survey.** In Qualtrics, import `CPSC3720_Project_Skill_Survey_TEMPLATE.qsf`
   as a new survey. It's a scrubbed template (no real student data) - before
   sending it out, fill in `QID16`'s and `QID18`'s Choices with this
   semester's actual roster, one entry per student, in the same
   `Last, First Middle` format used throughout this pipeline. Adjust the
   GPA/skill/availability questions if they've changed since last semester.
2. **Export responses.** Once the survey closes, export a CSV from Qualtrics
   with numeric values (Qualtrics's default "use numeric values" export
   option) - it should have the usual 3 header rows (field names, question
   text, ImportId JSON).
3. **Prepare the data:**
   ```
   uv run python prepare_data.py
   ```
   (set `raw_csv`/`prepared_csv` at the top of the script first)
4. **Run the grouping algorithm:**
   ```
   uv run python genetic_grouping.py
   ```
   (set `input_csv` and review the config block at the top of the script
   first - see below)
5. Group assignments land in `groups/`, one CSV per attempt (`attempts`
   controls how many independent attempts run).

## Preparing the data (`prepare_data.py`)

Converts the raw Qualtrics export into the clean CSV `genetic_grouping.py`
expects. Set `raw_csv`/`prepared_csv` at the top, then run it. If a student
submitted more than once (resubmission, browser back button, etc.), it
prints what differs between their submissions and prompts interactively for
which one to keep - the differences can be substantive (different slider
values, availability, etc.), so this isn't resolved automatically.

It expects the export's machine-name column headers to include: `name`,
`gpa`, `time_mgt_1`/`time_mgt_2` (Likert), `expertise_1`..`expertise_13` (the
skill sliders, in survey order - see `EXPERTISE_FIELDS`), `availability_1`..`4`
(comma-separated free days per time block), `EndDate` (Qualtrics's standard
response-timestamp column - used to derive `submission_time`, hours between
the survey window opening and each student's submission, a behavioral
procrastination proxy scored the same way as `time_mgt`), and the teammate
drag-and-drop `teammates_0_GROUP`/`teammates_1_GROUP` columns (preferred/avoid
picks, already rank-ordered). Adjust `EXPERTISE_FIELDS`/`SKILLS_TOTAL_FIELDS`
if the survey's skill questions change.

If prepping by hand instead (no raw Qualtrics export, or a non-Qualtrics
source), the clean CSV just needs:
- Mandatory column: `name`
- Numeric columns for any metric used in `measures_weights`
- GPA looked up/entered for any student missing it; 0s elsewhere

#### Partner preferences (optional)
- `primary_partner` holds one name, exactly matching another student's `name`
  in the data. `additional_partners`/`avoid_partners` hold colon-separated
  lists of names.
- `primary_partner` and `additional_partners` (in that order) are treated as
  one combined, rank-ordered preferred list. `avoid_partners` is separate and
  unranked.

#### Availability (optional)
- `availability_1` through `availability_4` (one per time block - Morning/
  Early Afternoon/Late Afternoon/Evening), each a comma-separated list of
  free weekdays (`Sunday`..`Saturday`) for that block.

## Configuring the grouping script (`genetic_grouping.py`)

Everything below "STOP EDITING HERE" in the script is derived/internal -
only touch the config block above it.

- `input_csv`/`output_csv` - prepared data file and output name root.
  Generated group CSVs go to `groups/`, named with generation count and
  final fitness.
- `group_size` - desired team size.
- `generations`/`population_size`/`attempts` - algorithm tuning.
  Improvements often continue well past a couple hundred generations,
  especially at low `population_size`; check convergence for your class size
  before trusting the defaults. `attempts` independent runs execute in
  parallel (`parallelism = True`), one per CPU core - matching `attempts` to
  your core count uses one parallel wave, no wasted time.
- `progress`/`graph` - optional per-generation console output / fitness CSV.

#### `measures_weights` - GPA, skills, and other numeric metrics
Each metric maps to a **list** of `[weight, type]` pairs, not just one - most
metrics only need a single entry, but a metric can be scored multiple ways at
once and the contributions add. For example `gpa` is scored both `between`
(keep team averages level - the fairness floor, no team stacked
academically) and `within` (mix GPA levels inside each team, positive weight -
same "diversify within a team" idea already used for the skill sliders).
- `type: "between"` compares each team's *average* for that metric across all
  teams. `type: "within"` compares the spread *inside* each individual team.
- Negative weight rewards low variance (balance/similarity); positive weight
  rewards high variance (diversity/spread).
- Every metric is z-score normalized against the whole class before its
  variance is measured, so weight values are comparable across metrics
  regardless of raw scale (e.g. `skills_total`, a sum of many sliders, won't
  automatically dominate `gpa`, a 0-4 value, just because its raw numbers are
  bigger) - a weight of `-6` means "6x as important as a weight of `-1`," not
  "6x the raw stddev."

#### Partner weights and reciprocity
- `partner_rank_weights` - a list scoring a preferred pick by its rank
  position (1st/2nd/3rd choice, etc.), replacing a flat primary-vs-additional
  split. Picks beyond the list's length score 0.
- `one_sided_partner_credit` - fraction of a pick's rank weight awarded when
  it *isn't* reciprocated (the other student doesn't have you anywhere in
  their own preferred list). `strict_reciprocity = True` forces one-sided
  picks to count for nothing, overriding this value. This only affects
  scoring, not membership - a one-sided pair can still land in the same team
  by chance/other constraints, it just won't be rewarded for it.
- `avoid_partner_weight` - unlike the above, `avoid_partners` is a **hard
  constraint**, not just a scoring weight: `enforce_avoid_constraints`
  actively repairs any team that would put a flagged pair together, so a
  violation should never appear in the output regardless of weighting. This
  weight is mostly a backstop for the (essentially unreachable) case where
  the repair can't fully resolve a very dense avoid graph - watch for a
  printed `WARNING` in that case.
- `partner_rank_weights`/`avoid_partner_weight`/`availability_weight` are
  deliberately kept close to the magnitude of a single `measures_weights`
  term (roughly 1-4), not the combined block. Partner requests scale with
  class size (a 49-student class can have 60+ active requests), so even a
  modest per-request weight adds up - weights an order of magnitude larger
  can make a single honored request outweigh the *entire* `measures_weights`
  block, making GPA/skill balance functionally irrelevant to the GA. If you
  want partner requests to matter more (or less) than skill/GPA balance,
  scale these relative to `measures_weights`, not in isolation.

#### Availability weight
- `availability_weight` - reward per weekly time slot (of the 4 blocks x 7
  days = 28 possible) where every team member is free. A standalone fitness
  term, not part of `measures_weights`, since it's a coverage metric rather
  than a variance one.

## Understanding the output

- Group CSV(s) land in `groups/`. Population fitness & weights on row 2.
- Groups are listed with their fitness (including then excluding partner
  weights), mean metric values, and `shared_availability_slots` (weekly slots
  where every group member is free).
- Group members are listed under each group header, with `availability`
  shown as a readable "Block: Day,Day" summary and `preferred_partners` as a
  rank-ordered "1. Name; 2. Name" summary (combining the old
  primary/additional columns into one).
