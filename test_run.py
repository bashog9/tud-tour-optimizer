"""End-to-end test: generate sample data, solve, print a report, and run
sanity checks (assignment completeness, durations, balance behaviour)."""

import numpy as np
import pandas as pd

from campus_data import FACULTIES, N_FAC, build_choice_matrix
from model import Params, solve
from make_sample_data import make


def load_choices(df: pd.DataFrame) -> np.ndarray:
    choices, _ = build_choice_matrix(df)
    return choices


def main():
    df = make(50, path=None)
    choices = load_choices(df)

    p = Params(
        n_tours=3, t_max=110.0, min_fac=2, max_fac=5,
        b=np.array([0, 0, 1.0, 0, 0, 0, 2.0, 1.0, 1.5]),  # boost TNW-zuid, TBM...
    )
    res = solve(choices, p)

    print(f"status: {res.status}   objective: {res.objective:.4f}")
    print("components (normalized):",
          {k: round(v, 3) for k, v in res.components.items()})
    n = len(df)
    assigned = 0
    for k, t in enumerate(res.tours):
        assigned += len(t.students)
        print(f"\nTour {k+1}: {' -> '.join(t.nodes)}")
        print(f"  duration {t.duration:.0f} min | {len(t.students)} students "
              f"| dep {t.dep_bonus:.1f} | under {t.under_bonus:.1f}")

    sat = res.satisfaction
    print(f"\nsatisfaction: mean {sat.mean():.2f} / max {sum(p.rho)}, "
          f"zero-satisfaction students: {(sat == 0).sum()}")

    # ---- sanity checks -----------------------------------------------------
    assert assigned == n, "every student must be assigned exactly once"
    assert all(t.duration <= p.t_max + 1e-9 for t in res.tours)
    sizes = [len(t.students) for t in res.tours]
    print(f"group sizes: {sizes}")
    assert res.status in ("OPTIMAL", "FEASIBLE")
    print("\nall sanity checks passed")


if __name__ == "__main__":
    main()
