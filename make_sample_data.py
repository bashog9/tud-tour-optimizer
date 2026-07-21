"""Generate a synthetic student-preference Excel in the expected format:
one row per student, columns Student, Choice1, Choice2, Choice3, where each
choice is a BACHELOR PROGRAMME (as students actually submit). The tool maps
programmes to faculties on load."""

import numpy as np
import pandas as pd
from campus_data import PROGRAM_TO_FACULTY

PROGRAMS = list(PROGRAM_TO_FACULTY.keys())
# mild popularity skew across programmes (purely for a realistic-looking sample)
_POP = np.array([3.0, 2.0, 1.5, 1.0, 3.0, 2.0, 1.5, 2.0,
                 1.0, 1.0, 2.5, 1.5, 1.2, 1.0, 1.5, 1.2])
_POP = _POP / _POP.sum()


def make(n: int = 100, path: str | None = "sample_students.xlsx",
         seed: int = 42) -> pd.DataFrame:
    """Deterministic synthetic sample: the same `seed` always yields the same
    students, so re-running in the app does NOT change the data underneath you.
    Only the optimizer settings you change will change the result."""
    rng = np.random.default_rng(seed)      # fresh, seeded RNG every call
    rows = []
    for i in range(n):
        picks = rng.choice(len(PROGRAMS), size=3, replace=False, p=_POP)
        rows.append({
            "Student": f"Student_{i+1:03d}",
            "Choice1": PROGRAMS[picks[0]],
            "Choice2": PROGRAMS[picks[1]],
            "Choice3": PROGRAMS[picks[2]],
        })
    df = pd.DataFrame(rows)
    if path is not None:              # None -> just return the DataFrame
        df.to_excel(path, index=False)
    return df


if __name__ == "__main__":
    df = make()
    print(df.head())
    print(f"\n{len(df)} students written to sample_students.xlsx")
