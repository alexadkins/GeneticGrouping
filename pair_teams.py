import csv
import sys
from itertools import combinations

sys.path.insert(0, ".")
import genetic_grouping as g
import config as cfg  # TABLE_PRIORITY - see config.py ("EDIT PER SEMESTER" section)

rank_limit = len(g.partner_rank_weights)
one_sided_credit = 0 if g.strict_reciprocity else g.one_sided_partner_credit

def load_groups(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    groups = {}
    for r in rows:
        gid = r.get("Group", "").strip()
        name = r.get("name", "").strip()
        if not gid or gid == "Weights:" or not name:
            continue
        groups.setdefault(gid, []).append(name)
    return groups

def cross_team_score(groups, team_a, team_b):
    """Score for pairing team_a and team_b at the same table/area: reward
    preferred picks that span the two teams (same logic as fitness()'s
    within-team partner scoring, applied across the pair instead), penalize
    avoid_partner conflicts spanning the pair the same way."""
    names_a = set(groups[team_a])
    names_b = set(groups[team_b])
    score = 0.0
    detail = []
    # Iterate sorted (not raw set order) so `detail`'s order is deterministic
    # across runs - Python's per-process string hash randomization would
    # otherwise reorder it run to run for no reason.
    for side_names, other_names in [(sorted(names_a), names_b), (sorted(names_b), names_a)]:
        for name in side_names:
            student = g.students_by_name[name]
            plist = g.preferred_list(student)
            for rank, pick in enumerate(plist):
                if rank >= rank_limit:
                    break
                if pick in other_names:
                    other = g.students_by_name.get(pick)
                    reciprocated = other and student["name"] in g.preferred_list(other)
                    credit = 1.0 if reciprocated else one_sided_credit
                    weight = g.partner_rank_weights[rank] * credit
                    score += weight
                    detail.append((name, pick, rank + 1, reciprocated, weight))
            for ap in student["avoid_partners"]:
                if ap in other_names:
                    score += g.avoid_partner_weight
                    detail.append((name, ap, "AVOID", None, g.avoid_partner_weight))
    return score, detail

def best_pairing(groups):
    """Exhaustive search over all perfect matchings of the teams in `groups`
    into pairs (14 teams -> 135135 matchings total, fast enough to brute-force
    exactly). A same-size-only matching is impossible whenever the class size
    is odd (odd total split across an even team count always leaves an odd
    count of each team size, so at least one pair must cross sizes) - so the
    search instead MINIMIZES the number of cross-size pairs first, and
    maximizes total preference score as the tiebreaker among matchings that
    achieve that minimum."""
    team_ids = sorted(groups.keys(), key=int)
    sizes = {tid: len(groups[tid]) for tid in team_ids}

    pair_scores, pair_details = {}, {}
    for a, b in combinations(team_ids, 2):
        s, d = cross_team_score(groups, a, b)
        pair_scores[(a, b)] = s
        pair_details[(a, b)] = d

    def score_of(a, b):
        return pair_scores[(a, b)] if (a, b) in pair_scores else pair_scores[(b, a)]

    def is_cross_size(a, b):
        return sizes[a] != sizes[b]

    best_key, best_matching = None, None

    def search(remaining, current, current_score, current_cross_count):
        nonlocal best_key, best_matching
        if not remaining:
            key = (current_cross_count, -current_score)
            if best_key is None or key < best_key:
                best_key = key
                best_matching = list(current)
            return
        first = remaining[0]
        rest = remaining[1:]
        for i, other in enumerate(rest):
            current.append((first, other))
            search(rest[:i] + rest[i+1:], current,
                   current_score + score_of(first, other),
                   current_cross_count + (1 if is_cross_size(first, other) else 0))
            current.pop()

    search(team_ids, [], 0.0, 0)
    best_score = sum(score_of(a, b) for a, b in best_matching)
    return best_score, best_matching, pair_details, score_of

def print_pairing(groups, best_score, best_matching, pair_details, score_of):
    print(f"Best total cross-team preference score: {best_score:.2f}\n")
    for a, b in sorted(best_matching, key=lambda p: -score_of(*p)):
        s = score_of(a, b)
        size_a, size_b = len(groups[a]), len(groups[b])
        mixed_tag = "  [MIXED SIZE]" if size_a != size_b else ""
        print(f"Team {a} + Team {b}  ({size_a}+{size_b} people, score {s:+.2f}){mixed_tag}")
        key = (a, b) if (a, b) in pair_details else (b, a)
        for name, pick, rank, reciprocated, weight in pair_details[key]:
            if rank == "AVOID":
                print(f"    AVOID CONFLICT: {name} <-> {pick}  (penalty {weight:+.2f})")
            else:
                tag = "mutual" if reciprocated else "one-sided"
                print(f"    {name} -> rank-{rank} pick {pick} ({tag}, +{weight:.2f})")
        if not pair_details[key]:
            print("    (no direct preference links - paired for balance/leftover)")

def _padded_table_priority(table_priority, needed):
    """Extend table_priority with generic fallback labels ("Table 9", "Table
    10", ...) if it doesn't have enough entries for `needed` pairs (one
    table per pair - 2 teams/table). Keeps assign_tables() correct for any
    class size even if TABLE_PRIORITY was never updated for the room/roster
    actually in use - it'll just fall back to plain labels instead of
    crashing or silently dropping pairs."""
    if len(table_priority) >= needed:
        return list(table_priority)
    extra = [f"Table {i}" for i in range(len(table_priority) + 1, needed + 1)]
    return list(table_priority) + extra

def assign_tables(teams, best_matching, score_of, table_priority=cfg.TABLE_PRIORITY,
                   hard_seats=None, allowed_seats=None):
    """Assign each team-pair to one of the tables in `table_priority` (auto-
    extended with generic labels if it's shorter than the number of pairs -
    see _padded_table_priority - so this always produces a valid assignment
    regardless of class size). `hard_seats` maps a student name to the table
    letter their pair must occupy. `allowed_seats` maps a student name to a
    list of acceptable table letters for their pair (checked in priority
    order, earlier = preferred). Both are optional and student-agnostic -
    callers supply any real names via their own (typically gitignored)
    config, never hardcoded here. Pairs left over after constraints are
    placed by size (largest first) into tables in `table_priority` order."""
    hard_seats = hard_seats or {}
    allowed_seats = allowed_seats or {}
    pairs = [frozenset(p) for p in best_matching]
    table_priority = _padded_table_priority(table_priority, len(pairs))

    def pair_for_student(name):
        tid = next((t for t, names in teams.items() if name in names), None)
        return next((p for p in pairs if tid in p), None) if tid is not None else None

    table_of_pair = {}
    available = set(table_priority)

    for name, table in hard_seats.items():
        p = pair_for_student(name)
        if p is not None and p not in table_of_pair:
            table_of_pair[p] = table
            available.discard(table)

    for name, allowed in allowed_seats.items():
        p = pair_for_student(name)
        if p is None or p in table_of_pair:
            continue
        chosen = next((t for t in allowed if t in available), None)
        if chosen:
            table_of_pair[p] = chosen
            available.discard(chosen)

    def pair_size(p):
        a, b = tuple(p)
        return len(teams[a]) + len(teams[b])

    remaining = sorted((p for p in pairs if p not in table_of_pair), key=pair_size, reverse=True)
    table_order = [t for t in table_priority if t in available]
    for p, t in zip(remaining, table_order):
        table_of_pair[p] = t

    rows = []
    for p in pairs:
        a, b = sorted(p, key=int)  # deterministic display order, not just insertion-order-dependent set iteration
        table = table_of_pair[p]
        rows.append((table, a, b, len(teams[a]) + len(teams[b]), score_of(a, b)))
    rows.sort(key=lambda r: r[0])
    return rows

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: uv run python pair_teams.py groups/<file>.csv [more files...]")
    files = sys.argv[1:]
    summary = []
    for path in files:
        groups = load_groups(path)
        best_score, best_matching, pair_details, score_of = best_pairing(groups)
        team_fitness = path.rsplit("_", 1)[-1].replace(".csv", "")
        summary.append((path, team_fitness, best_score))
        print(f"\n{'='*70}\n{path}  (team fitness {team_fitness})\n{'='*70}")
        print_pairing(groups, best_score, best_matching, pair_details, score_of)

    if len(files) > 1:
        print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
        print(f"{'file':<55} {'team fitness':>12} {'pairing score':>14}")
        for path, tf, ps in sorted(summary, key=lambda r: -float(r[1])):
            print(f"{path:<55} {tf:>12} {ps:>14.2f}")
