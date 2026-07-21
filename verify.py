"""
Independent verification of the solver -- a rigorous version of the original
"test whether the solution is correct or whether a better one exists" idea:

1.  PRUNING CHECK: solve with and without dominance pruning; the optima must
    coincide (pruning is claimed exact).
2.  RECOMPUTATION CHECK: recompute the objective of the returned solution
    from scratch through an independent code path; must match the solver.
3.  FEASIBILITY CHECK: assignment is a partition of the students; every tour
    respects t_max and the faculty-count bounds.
4.  DURATION ORACLE: for each chosen tour, brute-force all node orderings
    and confirm the Held-Karp duration and recovered order are optimal.

Run:  python verify.py
"""

from dataclasses import replace
from itertools import permutations

import numpy as np

from model import Params, solve, shortest_tours, build_candidates
from campus_data import FACULTIES, IDX, TRAVEL_FULL, DEPOT, DEFAULT_DWELL_DEPOT
from make_sample_data import make
from test_run import load_choices


def recompute_objective(res, choices, p: Params) -> float:
    """Recompute the normalized weighted objective from the extracted
    solution only (no solver internals)."""
    n, K = len(choices), p.n_tours
    rho = np.array(p.rho)
    C = build_candidates(replace(p, prune=False), shortest_tours())

    sat_max = n * rho.sum()
    bal_norm = 2 * n * (K - 1) if K > 1 else 1.0

    total = p.alpha * res.satisfaction.sum() / sat_max
    for t in res.tours:
        mask = 0
        for name in t.nodes:
            mask |= 1 << IDX[name]
        c = C.full_masks.index(mask)
        total += (p.beta * C.dep[c] / C.dep_norm
                  + p.gamma * C.under[c] / C.under_norm
                  - p.lam * C.dur[c] / C.dur_norm)
    total -= p.mu * sum(abs(K * len(t.students) - n) for t in res.tours) / bal_norm
    return total


def brute_force_duration(node_names, p: Params) -> float:
    """Exact closed-tour duration: min over orderings of
    Aula -> perm -> Aula, plus dwell times and the depot buffer."""
    idxs = [IDX[nm] for nm in node_names]
    if not idxs:
        return 0.0
    best = np.inf
    for perm in permutations(idxs):
        walk = TRAVEL_FULL[DEPOT, perm[0]] + TRAVEL_FULL[perm[-1], DEPOT]
        walk += sum(TRAVEL_FULL[perm[i], perm[i + 1]]
                    for i in range(len(perm) - 1))
        best = min(best, walk)
    return best + DEFAULT_DWELL_DEPOT + sum(p.dwell[j] for j in idxs)


def main():
    df = make(100)
    choices = load_choices(df)
    p = Params(t_max=120.0, b=np.array([0, 0, 1., 0, 0, 0, 2., 1., 1.5]),
               mip_rel_gap=1e-6)

    print("solve (pruned)...")
    res = solve(choices, p)
    print(f"  {res.status}, objective {res.objective:.6f}, gap {res.gap:.1e}")

    print("solve (pruning disabled)...")
    res2 = solve(choices, replace(p, prune=False))
    assert abs(res.objective - res2.objective) < 1e-5, \
        f"pruned {res.objective} != unpruned {res2.objective}"
    print(f"  pruning check OK ({res2.objective:.6f})")

    obj2 = recompute_objective(res, choices, p)
    assert abs(obj2 - res.objective) < 1e-5, f"{obj2} vs {res.objective}"
    print(f"  objective recomputation OK ({obj2:.6f})")

    seen = sorted(i for t in res.tours for i in t.students)
    assert seen == list(range(len(choices))), "assignment not a partition"
    from campus_data import EXTRAS
    for t in res.tours:
        nfac = sum(1 for nm in t.nodes if nm in FACULTIES)
        assert p.min_fac <= nfac <= p.max_fac
        assert t.duration <= p.t_max + 1e-9
        if p.require_one_extra:
            nextra = sum(1 for nm in t.nodes if nm in EXTRAS)
            assert nextra == 1, f"{t.nodes}: expected exactly one extra, got {nextra}"
    print("  feasibility OK")

    for t in res.tours:
        bf = brute_force_duration(t.nodes, p)
        assert abs(bf - t.duration) < 1e-9, f"{t.nodes}: {bf} vs {t.duration}"
        # the recovered order must itself achieve that closed-tour time
        idxs = [IDX[nm] for nm in t.nodes]
        walk = (TRAVEL_FULL[DEPOT, idxs[0]] + TRAVEL_FULL[idxs[-1], DEPOT]
                + sum(TRAVEL_FULL[idxs[i], idxs[i + 1]]
                      for i in range(len(idxs) - 1)))
        assert abs(walk + DEFAULT_DWELL_DEPOT
                   + sum(p.dwell[j] for j in idxs) - bf) < 1e-9
    print("  duration oracle OK (brute-force orderings match Held-Karp)")

    print("\nALL VERIFICATION CHECKS PASSED")


if __name__ == "__main__":
    main()
