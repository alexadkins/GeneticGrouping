For use with Qualtrics exported questionnaire data. Tested and developed with Python 3.10.0.

## Preparing the Data (csv file):
- Mandatory column names: `name`
- Delete all but one header column. Rename header column values to desired fitness metrics. 
- Remove duplicates. 
- Add missing students. Look up and enter GPA. Fill in 0s for remaining values.
- Ensure any metrics to be used for weighting are in numerical format.

#### Accounting for Partners: (optional)
- Under `primary_partner` column, put desired partner's full name so that it exactly matches the user's name in the data. 
- For `additional_partners`, include other desired teammates separated by a colon (:). Do the same for `avoid_partners`.

## Preparing the Script (genetic_grouping.py)
- Set `input_csv` to prepared data file name
  - Ensure data file is in same directory as script, or set to full path
- Set `output_csv` to desired output root file name
  - Generated group csvs default to groups/ folder
  - Generated file names include number of generations and final population fitness
- Set `group_size` to desired team size

#### Extracting Student Data
- Adjust student dictionary key/values to match csv headers. Remove unwanted metrics.
- `name` is required
 
#### Setting Weights
- Ensure weight keys match student metrics. Remove unwanted metrics.
- Ensure wegiht values are in `[weight(int), "between/within"(str)` format.
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
- Groups are listed with their fitness (including then excluding partner weights) and mean metric values
- Group members are listed under each group header
