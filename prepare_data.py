import pandas as pd

import config as cfg  # raw_csv, prepared_csv, EXPERTISE_FIELDS, SKILLS_TOTAL_FIELDS - see config.py

TIME_MGT_SCALE = {"Strongly Disagree": 1, "Disagree": 2, "Neutral": 3, "Agree": 4, "Strongly Agree": 5}

# Qualtrics admin/metadata columns - excluded when diffing duplicate
# submissions, since these always differ (timestamps, response IDs, IP) but
# aren't answer content the instructor needs to weigh.
ADMIN_COLS = {
    "StartDate", "EndDate", "Status", "IPAddress", "Progress",
    "Duration (in seconds)", "Finished", "RecordedDate", "ResponseId",
    "RecipientLastName", "RecipientFirstName", "RecipientEmail",
    "ExternalReference", "LocationLatitude", "LocationLongitude",
    "DistributionChannel", "UserLanguage", "Last Seen Flow Element ID",
    "Last Seen Question IDs",
}


def resolve_duplicates(df):
    """A student can submit the survey more than once (resubmission, browser
    back button, etc.), and the submissions can genuinely differ - not safe
    to auto-resolve. Prompts the instructor to pick which one to keep."""
    dup_names = df["name"][df["name"].duplicated(keep=False)].unique()
    if len(dup_names) == 0:
        return df

    keep_indices = list(df.index[~df["name"].isin(dup_names)])
    for name in dup_names:
        rows = df[df["name"] == name]
        print(f"\nMultiple submissions found for {name!r}:")
        for i, (_, row) in enumerate(rows.iterrows(), start=1):
            print(f"  [{i}] submitted {row['EndDate']}  (took {row['Duration (in seconds)']}s)")

        diff_cols = [c for c in df.columns if c not in ADMIN_COLS and rows[c].astype(str).nunique() > 1]
        if diff_cols:
            print("  Differing answers:")
            for c in diff_cols:
                print(f"    {c}: {list(rows[c])}")
        else:
            print("  (submissions are otherwise identical)")

        choice = None
        while choice is None:
            raw_choice = input(f"  Which submission should be kept for {name}? [1-{len(rows)}]: ").strip()
            if raw_choice.isdigit() and 1 <= int(raw_choice) <= len(rows):
                choice = int(raw_choice)
            else:
                print(f"  Please enter a number from 1 to {len(rows)}.")
        keep_indices.append(rows.index[choice - 1])

    resolved = df.loc[sorted(keep_indices)].reset_index(drop=True)
    print(f"\nResolved {len(dup_names)} duplicate name(s); dropped {len(df) - len(resolved)} row(s).\n")
    return resolved


def parse_ranked_names(field):
    """Qualtrics drag-and-drop GROUP field: comma-joined "Last, First Middle" names,
    already in rank order. Names always contain exactly one comma, so pair up
    tokens two at a time."""
    if pd.isna(field) or not field:
        return []
    tokens = [t.strip() for t in field.split(",")]
    return [f"{tokens[i]}, {tokens[i + 1]}" for i in range(0, len(tokens) - 1, 2)]


def main():
    df = pd.read_csv(cfg.raw_csv, header=0, skiprows=[1, 2])
    df = resolve_duplicates(df)

    out = pd.DataFrame()
    out["name"] = df["name"]
    out["gpa"] = pd.to_numeric(df["gpa"])
    out["time_mgt"] = (
        df["time_mgt_1"].map(TIME_MGT_SCALE) + df["time_mgt_2"].map(TIME_MGT_SCALE)
    ) / 2

    # Behavioral procrastination proxy, complementing the self-reported
    # time_mgt above: hours between the survey window opening (earliest
    # response in this export) and when each student submitted. 0 = right
    # when it opened, larger = closer to the last response in the data.
    end_dates = pd.to_datetime(df["EndDate"])
    out["submission_time"] = (end_dates - end_dates.min()).dt.total_seconds() / 3600

    for i, field in enumerate(cfg.EXPERTISE_FIELDS, start=1):
        out[field] = pd.to_numeric(df[f"expertise_{i}"])

    out["skills_total"] = out[cfg.SKILLS_TOTAL_FIELDS].sum(axis=1)

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

    out.to_csv(cfg.prepared_csv, index=False)
    print(f"Wrote {len(out)} students to {cfg.prepared_csv}")


if __name__ == "__main__":
    main()
