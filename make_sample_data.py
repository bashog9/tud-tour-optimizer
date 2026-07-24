"""Generate a synthetic student-preference Excel whose choice-combinations are
drawn from REAL co-occurrence data (how often programmes are chosen together),
with a guaranteed minimum presence for the five smaller programmes.

The bulk of the students are drawn from the observed top-20 two- and three-
programme combinations (weighted by their counts). On top of that, a reserved
"rare budget" guarantees that each of the five programmes absent from the data
(the TNW-zuid trio, Klinische Technologie, Earth) appears at least once in every
file, with a tiered frequency: MST and LST most, Klinische Technologie less,
Nanobiology and Earth least.

Source combinations are UNORDERED, so a rank order (Choice1 = first choice) is
assigned by a random permutation per student. Everything is reproducible via
`seed`.
"""

import numpy as np
import pandas as pd
from campus_data import PROGRAM_TO_FACULTY

# --- observed data (top-20 combinations with counts) -----------------------
PAIR_COMBOS = [
    (("Bouwkunde", "Industrieel Ontwerpen"), 411),
    (("Civiele Techniek", "Werktuigbouwkunde"), 402),
    (("Aerospace Engineering", "Werktuigbouwkunde"), 383),
    (("Bouwkunde", "Civiele Techniek"), 293),
    (("Electrical Engineering", "Werktuigbouwkunde"), 276),
    (("Bouwkunde", "Werktuigbouwkunde"), 257),
    (("Industrieel Ontwerpen", "Werktuigbouwkunde"), 244),
    (("Computer Science and Engineering", "Electrical Engineering"), 240),
    (("Civiele Techniek", "Industrieel Ontwerpen"), 239),
    (("Technische Natuurkunde", "Werktuigbouwkunde"), 225),
    (("Maritieme Techniek", "Werktuigbouwkunde"), 217),
    (("Aerospace Engineering", "Computer Science and Engineering"), 212),
    (("Civiele Techniek", "Technische Bestuurskunde"), 193),
    (("Aerospace Engineering", "Electrical Engineering"), 193),
    (("Technische Natuurkunde", "Technische Wiskunde"), 187),
    (("Technische Bestuurskunde", "Werktuigbouwkunde"), 178),
    (("Aerospace Engineering", "Technische Natuurkunde"), 177),
    (("Civiele Techniek", "Maritieme Techniek"), 173),
    (("Aerospace Engineering", "Civiele Techniek"), 167),
    (("Aerospace Engineering", "Maritieme Techniek"), 162),
]

TRIPLE_COMBOS = [
    (("Bouwkunde", "Civiele Techniek", "Werktuigbouwkunde"), 98),
    (("Bouwkunde", "Civiele Techniek", "Industrieel Ontwerpen"), 85),
    (("Bouwkunde", "Industrieel Ontwerpen", "Werktuigbouwkunde"), 80),
    (("Civiele Techniek", "Industrieel Ontwerpen", "Werktuigbouwkunde"), 78),
    (("Aerospace Engineering", "Electrical Engineering", "Werktuigbouwkunde"), 75),
    (("Aerospace Engineering", "Civiele Techniek", "Werktuigbouwkunde"), 73),
    (("Civiele Techniek", "Maritieme Techniek", "Werktuigbouwkunde"), 67),
    (("Computer Science and Engineering", "Electrical Engineering", "Werktuigbouwkunde"), 67),
    (("Civiele Techniek", "Technische Bestuurskunde", "Werktuigbouwkunde"), 66),
    (("Aerospace Engineering", "Maritieme Techniek", "Werktuigbouwkunde"), 65),
    (("Aerospace Engineering", "Bouwkunde", "Werktuigbouwkunde"), 59),
    (("Aerospace Engineering", "Technische Natuurkunde", "Werktuigbouwkunde"), 58),
    (("Civiele Techniek", "Electrical Engineering", "Werktuigbouwkunde"), 57),
    (("Bouwkunde", "Civiele Techniek", "Technische Bestuurskunde"), 50),
    (("Civiele Techniek", "Technische Natuurkunde", "Werktuigbouwkunde"), 49),
    (("Aerospace Engineering", "Bouwkunde", "Civiele Techniek"), 49),
    (("Industrieel Ontwerpen", "Technische Bestuurskunde", "Werktuigbouwkunde"), 47),
    (("Bouwkunde", "Maritieme Techniek", "Werktuigbouwkunde"), 46),
    (("Bouwkunde", "Industrieel Ontwerpen", "Technische Bestuurskunde"), 45),
    (("Civiele Techniek", "Industrieel Ontwerpen", "Technische Bestuurskunde"), 43),
]

# The five programmes absent from the data, with tiered relative frequency
# (MST, LST most; Klinische Technologie less; Nanobiology, Earth least).
RARE_WEIGHTS = {
    "Molecular Science and Technology": 3,
    "Life Science and Technology": 3,
    "Klinische Technologie": 2,
    "Nanobiology": 1,
    "Earth, Climate and Technology": 1,
}

# sanity: every programme name used here must exist in the mapping
for combo, _ in PAIR_COMBOS + TRIPLE_COMBOS:
    for prog in combo:
        assert prog in PROGRAM_TO_FACULTY, f"unknown programme: {prog}"
for prog in RARE_WEIGHTS:
    assert prog in PROGRAM_TO_FACULTY, f"unknown rare programme: {prog}"


def _marginal_common():
    """Common-programme popularity from the data (rare programmes excluded):
    programme -> total count over all pair and triple combinations."""
    marg = {}
    for combo, cnt in PAIR_COMBOS + TRIPLE_COMBOS:
        for prog in combo:
            marg[prog] = marg.get(prog, 0) + cnt
    return marg


def make(n: int = 50, path: str | None = "sample_students.xlsx",
         seed: int = 42, tail_fraction: float = 0.2,
         rare_fraction: float = 0.2) -> pd.DataFrame:
    """Deterministic sample based on the observed co-occurrence data, with a
    guaranteed minimum presence for the five smaller programmes.

    tail_fraction : share of the COMMON students drawn from a pair + a third
                    programme (adds variety beyond the exact top-20 triples).
    rare_fraction : target share of students reserved for the five rare
                    programmes; each rare programme is guaranteed at least once,
                    and any surplus is allotted by the tiered RARE_WEIGHTS.
    """
    rng = np.random.default_rng(seed)

    triples = [c for c, _ in TRIPLE_COMBOS]
    tri_w = np.array([w for _, w in TRIPLE_COMBOS], float); tri_w /= tri_w.sum()
    pairs = [c for c, _ in PAIR_COMBOS]
    pair_w = np.array([w for _, w in PAIR_COMBOS], float); pair_w /= pair_w.sum()

    marg = _marginal_common()
    marg_progs = list(marg.keys())
    marg_w = np.array([marg[p] for p in marg_progs], float); marg_w /= marg_w.sum()

    def draw_from_marginal(k, exclude):
        w = marg_w.copy()
        for p in exclude:
            if p in marg_progs:
                w[marg_progs.index(p)] = 0.0
        w /= w.sum()
        idx = rng.choice(len(marg_progs), size=k, replace=False, p=w)
        return [marg_progs[i] for i in idx]

    # ---- rare budget: guarantee one of each, allot the surplus by tier ------
    rares = list(RARE_WEIGHTS)
    budget = min(n, max(len(rares), round(rare_fraction * n)))
    counts = {r: 1 for r in rares} if budget >= len(rares) else {}
    if budget < len(rares):                      # tiny n: fit as many as we can
        for r in rares[:budget]:
            counts[r] = 1
    surplus = budget - sum(counts.values())
    # D'Hondt / Jefferson apportionment of the surplus: repeatedly give the next
    # unit to the programme maximizing weight / (current allocation + 1). This
    # favours the higher-weight programmes, so MST and LST lead, then Klinische
    # Technologie, then Nanobiology and Earth.
    alloc = {r: 0 for r in rares}
    for _ in range(max(0, surplus)):
        best = max(rares, key=lambda r: (RARE_WEIGHTS[r] / (alloc[r] + 1),
                                         RARE_WEIGHTS[r], -rares.index(r)))
        alloc[best] += 1
    for r in rares:
        if r in counts:
            counts[r] += alloc[r]

    n_rare = sum(counts.values())
    n_common = n - n_rare

    students = []
    # common students from the co-occurrence distribution
    for _ in range(n_common):
        if rng.random() >= tail_fraction:
            combo = list(triples[rng.choice(len(triples), p=tri_w)])
        else:
            a, b = pairs[rng.choice(len(pairs), p=pair_w)]
            combo = [a, b, draw_from_marginal(1, (a, b))[0]]
        students.append(combo)
    # rare students: rare programme + two common companions
    for r, c in counts.items():
        for _ in range(c):
            students.append([r] + draw_from_marginal(2, (r,)))

    rng.shuffle(students)                        # mix rare among common
    rows = []
    for i, combo in enumerate(students):
        order = rng.permutation(3)               # unordered source -> random ranks
        combo = [combo[j] for j in order]
        rows.append({"Student": f"Student_{i+1:03d}",
                     "Choice1": combo[0], "Choice2": combo[1], "Choice3": combo[2]})

    df = pd.DataFrame(rows)
    if path is not None:
        df.to_excel(path, index=False)
    return df


def make_files(sizes=(20, 30, 40, 60), directory="."):
    """Write one Excel per size (each following the distribution, with a
    distinct reproducible seed) and return the list of paths."""
    import os
    paths = []
    for n in sizes:
        p = os.path.join(directory, f"sample_students_{n}.xlsx")
        make(n, path=p, seed=n)
        paths.append(p)
    return paths


if __name__ == "__main__":
    df = make(50)                                # default built-in example
    print(df.head(8).to_string(index=False))
    print(f"\n{len(df)} students written to sample_students.xlsx")
