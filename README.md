For use with Qualtrics exported questionnaire data. Tested and developed with Python 3.10.0.
Uses [uv](https://docs.astral.sh/uv/) for dependencies - run scripts with `uv run python <script>.py`.

## Preparing the Data (csv file):

Run `prepare_data.py` to convert a raw Qualtrics export CSV into the clean CSV
`genetic_grouping.py` expects:
- Set `raw_csv` to the raw Qualtrics export file name.
- Set `prepared_csv` to the desired clean-CSV output name.
- Run `uv run python prepare_data.py`.

It expects the export's machine-name column headers to include: `name`, `gpa`,
`time_mgt_1`/`time_mgt_2` (Likert), `expertise_1`..`expertise_13` (the skill
sliders, in survey order - see `EXPERTISE_FIELDS`), `availability_1`..`4`
(comma-separated free days per time block), and the teammate drag-and-drop
`teammates_0_GROUP`/`teammates_1_GROUP` columns (preferred/avoid picks, already
rank-ordered). Adjust `EXPERTISE_FIELDS`/`SKILLS_TOTAL_FIELDS` if the survey's
skill questions change.

If prepping by hand instead (no raw Qualtrics export, or a non-Qualtrics
source):
- Mandatory column names: `name`
- Delete all but one header column. Rename header column values to desired fitness metrics. 
- Remove duplicates. 
- Add missing students. Look up and enter GPA. Fill in 0s for remaining values.
- Ensure any metrics to be used for weighting are in numerical format.

#### Accounting for Partners: (optional)
- Under `primary_partner` column, put desired partner's full name so that it exactly matches the user's name in the data. 
- For `additional_partners`, include other desired teammates separated by a colon (:). Do the same for `avoid_partners`.

#### Accounting for Availability: (optional)
- Add `availability_1` through `availability_4` columns (one per time block -
  Morning/Early Afternoon/Late Afternoon/Evening), each holding a
  comma-separated list of free weekdays (`Sunday`..`Saturday`) for that block.
- `genetic_grouping.py` rewards groups for the number of weekly slots (of the
  4 blocks x 7 days = 28 possible) where every member is free, via
  `availability_weight` - a standalone fitness term (not part of
  `measures_weights`, since it's a coverage metric rather than a variance one).

## Preparing the Script (genetic_grouping.py)
- Set `input_csv` to prepared data file name
  - Ensure data file is in same directory as script, or set to full path
- Set `output_csv` to desired output root file name
  - Generated group csvs default to `groups/` folder
  - Generated file names include number of generations and final population fitness
- Set `group_size` to desired team size

#### Extracting Student Data
- Adjust student dictionary key/values to match csv headers. Remove unwanted metrics.
- `name` is required
 
#### Setting Weights
- Ensure weight keys match student metrics. Remove unwanted metrics.
- Ensure weight values are in `[weight(int), "between/within"(str)` format.
  - Negative weights encourage low variance
  - Positive weights encourage high variance
  - `between` evaluates weights across groups
  - `within` evaluates weights within individual groups
- Keep `partner_weights` (not required in input CSV, will show up as empty in output CSV)

#### Adjusting the Algorithm (optional)
- Set `generations` to number of generations to run. Improvements are negligable after ~300
- Set `attempts` to number of times to re-run algorithm

## Understanding the Output
- Group csv(s) will be output to `groups/` subdirectory.
- Population fitness & weights on 2nd row
- Groups are listed with their fitness (including then excluding partner weights), mean metric values, and `shared_availability_slots` (weekly slots where every group member is free)
- Group members are listed under each group header, with `availability` shown as a readable "Block: Day,Day" summary
