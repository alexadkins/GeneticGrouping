import pandas as pd

# Raw Qualtrics export (3 header rows: field names, question text, ImportId JSON) - DO NOT EDIT
raw_csv = "3720F26SurveyData.csv"
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

TIME_MGT_SCALE = {"Strongly Disagree": 1, "Disagree": 2, "Neutral": 3, "Agree": 4, "Strongly Agree": 5}


def parse_ranked_names(field):
    """Qualtrics drag-and-drop GROUP field: comma-joined "Last, First Middle" names,
    already in rank order. Names always contain exactly one comma, so pair up
    tokens two at a time."""
    if pd.isna(field) or not field:
        return []
    tokens = [t.strip() for t in field.split(",")]
    return [f"{tokens[i]}, {tokens[i + 1]}" for i in range(0, len(tokens) - 1, 2)]


def main():
    df = pd.read_csv(raw_csv, header=0, skiprows=[1, 2])

    out = pd.DataFrame()
    out["name"] = df["name"]
    out["gpa"] = pd.to_numeric(df["gpa"])
    out["time_mgt"] = (
        df["time_mgt_1"].map(TIME_MGT_SCALE) + df["time_mgt_2"].map(TIME_MGT_SCALE)
    ) / 2

    for i, field in enumerate(EXPERTISE_FIELDS, start=1):
        out[field] = pd.to_numeric(df[f"expertise_{i}"])

    out["skills_total"] = out[SKILLS_TOTAL_FIELDS].sum(axis=1)

    for block in range(1, 5):
        out[f"availability_{block}"] = df[f"availability_{block}"]

    # Drop self-references (e.g. a respondent accidentally dragging their own
    # name into a bin) - harmless to fitness() since it's a constant, but not
    # a real preference.
    preferred = [
        [n for n in parse_ranked_names(field) if n != name]
        for name, field in zip(df["name"], df["teammates_0_GROUP"])
    ]
    avoid = [
        [n for n in parse_ranked_names(field) if n != name]
        for name, field in zip(df["name"], df["teammates_1_GROUP"])
    ]
    out["primary_partner"] = [names[0] if names else None for names in preferred]
    out["additional_partners"] = [":".join(names[1:]) or None for names in preferred]
    out["avoid_partners"] = [":".join(names) or None for names in avoid]

    out.to_csv(prepared_csv, index=False)
    print(f"Wrote {len(out)} students to {prepared_csv}")


if __name__ == "__main__":
    main()
