"""
Campus data for the TU Delft tour optimizer.

Nodes
-----
DEPOT  = the Aula (building 20). Every tour starts and ends here, so it is a
         fixed node present in every tour (index N_NODES, appended last).
NODES  = 9 faculties + 3 auxiliary buildings (the "visitable" set, indices
         0..N_NODES-1).

Travel matrix
-------------
The Aula->node column is REAL (measured walking minutes supplied by the tour
office). The node<->node entries are ESTIMATES: each building is embedded as a
point in R^2 at its measured radius from the Aula, with an angle taken from
campus geography; pairwise times are the Euclidean distances between those
points (floored at 2 min). This construction

  * reproduces every measured Aula distance EXACTLY (radius = point norm), and
  * is automatically a metric (triangle inequality holds by construction),

but it is only a geographic approximation of true walking times. Replace the
node<->node block of TRAVEL_FULL with measured times when available; nothing
else in the pipeline changes.
"""

from __future__ import annotations
import numpy as np

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

FACULTIES = ["AE", "BK", "CITG", "EWI", "IO", "ME", "TNW-zuid", "TNW", "TBM"]
EXTRAS = ["X", "DreamHall", "Library"]
NODES = FACULTIES + EXTRAS            # visitable nodes, indices 0..11
DEPOT_NAME = "Aula"

N_FAC = len(FACULTIES)
N_NODES = len(NODES)                  # 12 visitable nodes
DEPOT = N_NODES                       # depot index = 12 (appended last)
N_ALL = N_NODES + 1                   # 13 including the Aula
IDX = {name: i for i, name in enumerate(NODES)}

# ---------------------------------------------------------------------------
# Travel matrix (walking minutes) -- MEASURED
# ---------------------------------------------------------------------------
# These are measured walking times supplied by the tour office (travel_times.csv).
# Rows/columns are ordered: the 12 visitable nodes, then the Aula (index DEPOT).
# Symmetric, zero diagonal. Real walking times need not satisfy the triangle
# inequality and this matrix does not (a detour can beat the direct path); the
# solver does not require metricity, so the numbers are used as-is.
MEASURED_TRAVEL_ROWS = [
    [0, 29, 18, 16, 21, 21,  5, 23, 22, 12, 18, 24, 22],   # AE
    [29,  0, 14, 15,  9, 10, 28, 14, 11, 19, 14, 10,  9],   # BK
    [18, 14,  0,  5,  8,  4, 15,  5, 11,  7,  1,  7,  5],   # CITG
    [16, 15,  5,  0,  9,  5, 22,  8, 10,  8,  6,  9,  7],   # EWI
    [21,  9,  8,  9,  0,  4, 27,  8,  2, 13,  9,  4,  3],   # IO
    [21, 10,  4,  5,  4,  0, 18,  6,  6, 10,  6,  5,  9],   # ME
    [5, 28, 15, 22, 27, 18,  0, 20, 24,  8, 15, 21, 19],    # TNW-zuid
    [23, 14,  5,  8,  8,  6, 20,  0, 11, 12,  5,  4,  5],   # TNW
    [22, 11, 11, 10,  2,  6, 24, 11,  0, 16, 11,  7,  6],   # TBM
    [12, 19,  7,  8, 13, 10,  8, 12, 16,  0,  7, 13, 11],   # X
    [18, 14,  1,  6,  9,  6, 15,  5, 11,  7,  0,  7,  6],   # DreamHall
    [24, 10,  7,  9,  4,  5, 21,  4,  7, 13,  7,  0,  2],   # Library
    [22,  9,  5,  7,  3,  9, 19,  5,  6, 11,  6,  2,  0],   # Aula (DEPOT)
]

TRAVEL_FULL = np.array(MEASURED_TRAVEL_ROWS, dtype=float)   # (13 x 13)
assert TRAVEL_FULL.shape == (N_ALL, N_ALL)
# Back-compat view over the 12 visitable nodes (node<->node block only).
TRAVEL = TRAVEL_FULL[:N_NODES, :N_NODES]

# Measured Aula->node minutes (the depot row), kept for the schematic map only.
AULA_MIN = {nm: float(TRAVEL_FULL[DEPOT, IDX[nm]]) for nm in NODES}

# Approximate campus bearings (deg, 0 = East, 90 = North). Used ONLY to lay out
# the schematic map; they play no role in the optimization, which uses the
# measured matrix above. Radius = measured Aula time, angle = bearing below.
_ANGLE = {
    "TNW":        70.0,   # just N/NE of the Aula
    "Library":   200.0,   # immediately S (under the hill)
    "CITG":       10.0,   # E, Stevinweg
    "ME":        250.0,   # S, Mekelweg 2
    "EWI":       240.0,   # SSE, Mekelweg 4
    "IO":        220.0,   # SSW, Landbergstraat
    "TBM":       195.0,   # W/WSW, Jaffalaan
    "BK":        120.0,   # NNW, Julianalaan (off on its own)
    "DreamHall":  12.0,   # E, Stevinweg 4 (next to CiTG)
    "X":         255.0,   # S, sports centre
    "TNW-zuid":  262.0,   # far S, Van der Maasweg
    "AE":        250.0,   # far S, Kluyverweg
}


def _coords() -> dict:
    """Schematic map only: Aula at the origin; each node at (r cos t, r sin t)
    with r its measured Aula time and t its bearing. Not used for solving."""
    c = {DEPOT_NAME: (0.0, 0.0)}
    for nm in NODES:
        r = AULA_MIN[nm]
        a = np.radians(_ANGLE[nm])
        c[nm] = (r * np.cos(a), r * np.sin(a))
    return c


_COORD = _coords()

# ---------------------------------------------------------------------------
# Manual / measured travel-time override (optional)
# ---------------------------------------------------------------------------
# To update times, edit them in a CSV and load it: the first row and first
# column are the labels (the 12 node names + "Aula"), the body is minutes.
# `export_travel_template()` writes the current matrix in exactly that layout,
# so you can open it in Excel, overwrite numbers, and load it back.

_LABELS = NODES + [DEPOT_NAME]          # row/column order for the CSV



def export_travel_template(path: str = "travel_times.csv") -> str:
    import csv
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([""] + _LABELS)
        for i, a in enumerate(_LABELS):
            w.writerow([a] + [f"{TRAVEL_FULL[i, j]:.1f}" for j in range(N_ALL)])
    return path


def load_travel_csv(path: str) -> np.ndarray:
    """Load a labelled, symmetric travel matrix and install it as TRAVEL_FULL.
    Returns the new matrix. Missing/blank cells fall back to the estimate."""
    import csv
    global TRAVEL_FULL, TRAVEL
    with open(path, newline="") as f:
        rows = [r for r in csv.reader(f) if r]
    header = rows[0][1:]
    pos = {name: k for k, name in enumerate(header)}
    M = TRAVEL_FULL.copy()
    for r in rows[1:]:
        a = r[0]
        if a not in _LABELS:
            continue
        ia = _LABELS.index(a)
        for name, cell in zip(header, r[1:]):
            if name not in _LABELS or cell.strip() == "":
                continue
            ib = _LABELS.index(name)
            M[ia, ib] = float(cell)
    M = np.maximum(M, M.T)              # enforce symmetry (max of the two)
    np.fill_diagonal(M, 0.0)
    TRAVEL_FULL = M
    TRAVEL = TRAVEL_FULL[:N_NODES, :N_NODES]
    return TRAVEL_FULL

# ---------------------------------------------------------------------------
# Dependency structure:
# faculty -> (first-degree partner, second-degree partner, extra building)
# ---------------------------------------------------------------------------

DEPENDENCIES = {
    "AE":       ("ME",       "CITG", "X"),
    "BK":       ("CITG",     "IO",   "DreamHall"),
    "CITG":     ("IO",       "TBM",  "DreamHall"),
    "EWI":      ("TNW",      "ME",   "Library"),
    "IO":       ("TBM",      "BK",   "Library"),
    "ME":       ("EWI",      "AE",   "DreamHall"),
    "TNW-zuid": ("TNW",      "ME",   "X"),
    "TNW":      ("TNW-zuid", "AE",   "X"),
    "TBM":      ("CITG",     "BK",   "Library"),
}

# Default dwell (service) times in minutes.
DEFAULT_DWELL_FACULTY = 15.0
DEFAULT_DWELL_EXTRA = 10.0
DEFAULT_DWELL_DEPOT = 0.0


def default_dwell() -> np.ndarray:
    """Length-N_NODES dwell vector over the visitable nodes (depot handled
    separately via DEFAULT_DWELL_DEPOT)."""
    s = np.empty(N_NODES)
    s[:N_FAC] = DEFAULT_DWELL_FACULTY
    s[N_FAC:] = DEFAULT_DWELL_EXTRA
    return s


# ---------------------------------------------------------------------------
# Bachelor programme  ->  faculty mapping
# ---------------------------------------------------------------------------
# Students submit BACHELOR PROGRAMMES, not faculties. Several programmes map to
# the same faculty (a tour visits the faculty building, not the programme).

PROGRAM_TO_FACULTY = {
    "Aerospace Engineering":            "AE",
    "Bouwkunde":                        "BK",
    "Civiele Techniek":                 "CITG",
    "Earth, Climate and Technology":    "CITG",
    "Computer Science and Engineering": "EWI",
    "Electrical Engineering":           "EWI",
    "Technische Wiskunde":              "EWI",
    "Industrieel Ontwerpen":            "IO",
    "Klinische Technologie":            "ME",
    "Maritieme Techniek":               "ME",
    "Werktuigbouwkunde":                "ME",
    "Life Science and Technology":      "TNW-zuid",
    "Molecular Science and Technology": "TNW-zuid",
    "Nanobiology":                      "TNW-zuid",
    "Technische Natuurkunde":           "TNW",
    "Technische Bestuurskunde":         "TBM",
}


def _norm(s: str) -> str:
    """Case/space/punctuation-insensitive key: lowercase, '&'->'and', drop
    commas, collapse whitespace."""
    s = str(s).lower().replace("&", "and").replace(",", " ")
    return " ".join(s.split())


# normalized lookup: programme names AND bare faculty codes both resolve
_RESOLVE = {_norm(k): v for k, v in PROGRAM_TO_FACULTY.items()}
_RESOLVE.update({_norm(f): f for f in FACULTIES})   # accept faculty codes too


def to_faculty(cell) -> str | None:
    """Resolve a raw cell (a bachelor programme or a faculty code) to a faculty
    code, or None if blank/unrecognized."""
    if cell is None:
        return None
    if isinstance(cell, float) and np.isnan(cell):
        return None
    key = _norm(cell)
    return _RESOLVE.get(key) if key else None


def build_choice_matrix(df, cols=("Choice1", "Choice2", "Choice3")):
    """Map a student table to an (n, 3) array of faculty indices (ranked),
    -1 = empty. Duplicates within a student's list (two programmes in the same
    faculty) are dropped at their lower rank; the weight of a choice always
    follows the position the student wrote it in.

    Returns (choices, unknown) where `unknown` lists (row, column, raw value)
    for non-blank cells that could not be mapped.
    """
    import numpy as _np
    n = len(df)
    choices = _np.full((n, 3), -1, dtype=int)
    unknown = []
    for i in range(n):
        seen = set()
        for r, col in enumerate(cols):
            if col not in df.columns:
                continue
            raw = df[col].iloc[i]
            fac = to_faculty(raw)
            if fac is None:
                if raw is not None and str(raw).strip() != "" and str(raw).strip().lower() != "nan":
                    unknown.append((i, col, raw))
                continue
            if fac in seen:            # same faculty already ranked higher
                continue
            seen.add(fac)
            choices[i, r] = IDX[fac]   # faculty index == node index for faculties
    return choices, unknown
