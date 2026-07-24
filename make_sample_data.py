"""Generate a synthetic student-preference Excel whose choice-combinations are
drawn from REAL co-occurrence data (how often programmes are chosen together).

The two tables below are the observed top-20 most common two- and three-programme
combinations, with their counts. Students are sampled from these:

  * with probability (1 - tail_fraction): draw a whole three-programme
    combination from the triple table, weighted by its count;
  * otherwise: draw a common pair from the pair table, then add a third
    programme drawn from the data-derived marginal popularity.

The source tables are UNORDERED (a set of programmes, no rank), so a rank order
(Choice1 = first choice, etc.) is assigned by a random permutation per student.
Everything is derived from the provided counts and reproducible via `seed`.

Note: the provided data only covers 11 programmes; the five smaller ones
(all three TNW-zuid programmes, Klinische Technologie, Earth Climate & Tech)
do not appear in the top-20 tables, so by default they do not appear in the
sample either. Set include_rare=True to add them at a low baseline rate.
"""

import numpy as np
import pandas as pd
from campus_data import PROGRAM_TO_FACULTY

# --- observed data (top-20 combinations with counts) -----------------------
# Two-programme combinations:
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

# Three-programme combinations:
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

# programmes not present in the top-20 tables (the smaller ones)
_RARE = ["Earth, Climate and Technology", "Klinische Technologie",
         "Life Science and Technology", "Molecular Science and Technology",
         "Nanobiology"]

# sanity: every programme name used here must exist in the mapping
for combo, _ in PAIR_COMBOS + TRIPLE_COMBOS:
    for prog in combo:
        assert prog in PROGRAM_TO_FACULTY, f"unknown programme: {prog}"


def _marginal_popularity():
    """Programme -> total count over all pair and triple combinations that
    contain it (a data-derived popularity, used for the tail's third pick)."""
    marg = {}
    for combo, cnt in PAIR_COMBOS + TRIPLE_COMBOS:
        for prog in combo:
            marg[prog] = marg.get(prog, 0) + cnt
    return marg


def make(n: int = 100, path: str | None = "sample_students.xlsx",
         seed: int = 42, tail_fraction: float = 0.2,
         include_rare: bool = True) -> pd.DataFrame:
    """Deterministic sample based on the observed co-occurrence data.

    tail_fraction : share of students drawn from a common PAIR plus a third
                    programme (adds variety beyond the exact top-20 triples).
    include_rare  : if True (default), the five programmes absent from the data
                    appear at a low baseline rate so the whole campus (including
                    TNW-zuid) is represented.
    """
    rng = np.random.default_rng(seed)

    triples = [c for c, _ in TRIPLE_COMBOS]
    tri_w = np.array([w for _, w in TRIPLE_COMBOS], float)
    tri_w /= tri_w.sum()

    pairs = [c for c, _ in PAIR_COMBOS]
    pair_w = np.array([w for _, w in PAIR_COMBOS], float)
    pair_w /= pair_w.sum()

    marg = _marginal_popularity()
    if include_rare:
        floor = 0.4 * np.median(list(marg.values()))
        for p in _RARE:
            marg.setdefault(p, floor)
    marg_progs = list(marg.keys())
    marg_w = np.array([marg[p] for p in marg_progs], float)
    marg_w /= marg_w.sum()

    def draw_third(exclude):
        w = marg_w.copy()
        for p in exclude:
            if p in marg_progs:
                w[marg_progs.index(p)] = 0.0
        w /= w.sum()
        return marg_progs[rng.choice(len(marg_progs), p=w)]

    rows = []
    for i in range(n):
        if rng.random() >= tail_fraction:
            combo = list(triples[rng.choice(len(triples), p=tri_w)])
        else:
            a, b = pairs[rng.choice(len(pairs), p=pair_w)]
            combo = [a, b, draw_third((a, b))]
        order = rng.permutation(3)            # unordered source -> random ranks
        combo = [combo[j] for j in order]
        rows.append({
            "Student": f"Student_{i+1:03d}",
            "Choice1": combo[0], "Choice2": combo[1], "Choice3": combo[2],
        })

    df = pd.DataFrame(rows)
    if path is not None:
        df.to_excel(path, index=False)
    return df


def make_files(sizes=(20, 30, 40, 60), directory="."):
    """Write one Excel per size (each following the co-occurrence distribution,
    with a distinct reproducible seed) and return the list of paths."""
    import os
    paths = []
    for n in sizes:
        p = os.path.join(directory, f"sample_students_{n}.xlsx")
        make(n, path=p, seed=n)
        paths.append(p)
    return paths


if __name__ == "__main__":
    df = make(50)                          # default built-in example: 50 students
    print(df.head(8).to_string(index=False))
    print(f"\n{len(df)} students written to sample_students.xlsx")
