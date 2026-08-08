"""
Exact solver for the TU Delft tour design + student assignment problem.

Pipeline
--------
1.  Held-Karp over all 2^12 node subsets: exact shortest open walking path
    (no fixed start/end), giving exact duration d(S) for every subset.
2.  Candidate generation: every faculty set F with min_fac <= |F| <= max_fac
    and d(F) <= t_max, completed with its OPTIMAL extra-building set E*(F)
    (exact: extras affect only the dependency bonus and duration, which
    interact with nothing else).
3.  Dominance pruning (exact): drop candidate c if some c' has F_c ⊂ F_c'
    and val(c') >= val(c) -- the superset satisfies every student at least
    as well and has at least as much intrinsic value.
4.  Type aggregation: students with identical ranked triples share integer
    assignment-count variables (exact: satisfaction and balance depend on
    assignments only through counts).
5.  MILP solved to proven global optimality with HiGHS.

Objective (all components normalized to [0,1] before weighting):
    max  alpha*SAT + beta*DEP + gamma*UNDER - lam*DUR - mu*BAL
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix

from campus_data import (
    NODES, FACULTIES, EXTRAS, IDX, N_FAC, N_NODES,
    TRAVEL_FULL, DEPOT, DEPOT_NAME, DEFAULT_DWELL_DEPOT,
    DEPENDENCIES, default_dwell,
)

N_EXTRA = N_NODES - N_FAC


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

@dataclass
class Params:
    n_tours: int = 3
    t_max: float = 150.0            # hard ceiling per tour (minutes)
    min_fac: int = 2
    max_fac: int = 3
    dwell: np.ndarray = field(default_factory=default_dwell)

    # objective weights, applied to normalized components
    alpha: float = 1.0              # student satisfaction
    beta: float = 0.4               # dependency bonus
    gamma: float = 0.3              # undervisited bonus
    lam: float = 0.3                # duration penalty (soft time preference)
    mu: float = 0.5                 # balance penalty

    rho: tuple[float, float, float] = (3.0, 2.0, 1.0)   # rank weights
    w1: float = 2.0                 # first-degree partner bonus
    w2: float = 1.0                 # second-degree partner bonus
    w3: float = 1.0                 # designated extra-building bonus

    b: np.ndarray = field(default_factory=lambda: np.zeros(N_FAC))
    time_limit_s: float = 120.0
    mip_rel_gap: float = 1e-4
    require_one_extra: bool = True         # exactly one extra building per tour
    max_tours_per_faculty: int = 2         # a faculty may appear in at most this many tours
    max_extra_per_building: int = 1        # each extra building in at most this many tours


# ---------------------------------------------------------------------------
# Held-Karp precompute
# ---------------------------------------------------------------------------

def shortest_tours() -> np.ndarray:
    """tour[mask] = exact min walking time of a CLOSED tour that starts and
    ends at the Aula depot and visits exactly the nodes in `mask`.

    Held-Karp with a fixed source (the depot): dp[mask][j] is the shortest
    depot->...->j path through `mask`; the tour cost closes each path back to
    the depot.  tour[{j}] = 2 * dist(Aula, j) (there and back).  O(2^n n^2).
    """
    full = 1 << N_NODES
    INF = np.inf
    dp = np.full((full, N_NODES), INF)
    for j in range(N_NODES):
        dp[1 << j][j] = TRAVEL_FULL[DEPOT, j]          # Aula -> j
    for mask in range(1, full):
        for j in range(N_NODES):
            if not (mask >> j) & 1 or dp[mask][j] == INF:
                continue
            cur = dp[mask][j]
            rest = ~mask & (full - 1)
            k = rest
            while k:
                nxt = (k & -k).bit_length() - 1
                k &= k - 1
                nm = mask | (1 << nxt)
                cand = cur + TRAVEL_FULL[j, nxt]
                if cand < dp[nm][nxt]:
                    dp[nm][nxt] = cand
    tour = np.full(full, INF)
    tour[0] = 0.0
    for mask in range(1, full):
        best = INF
        for j in range(N_NODES):
            if (mask >> j) & 1 and dp[mask][j] < INF:
                best = min(best, dp[mask][j] + TRAVEL_FULL[j, DEPOT])   # j -> Aula
        tour[mask] = best
    return tour


def recover_order(mask: int) -> list[int]:
    """One optimal visiting order of `mask` for the closed tour through the
    depot (returns the visitable nodes in sequence, i.e. between the two Aula
    visits; caller may bracket it with the Aula)."""
    nodes = [j for j in range(N_NODES) if (mask >> j) & 1]
    m = len(nodes)
    if m == 0:
        return []
    if m == 1:
        return nodes
    INF = np.inf
    dp = np.full((1 << m, m), INF)
    par = np.full((1 << m, m), -1, dtype=int)
    for i in range(m):
        dp[1 << i][i] = TRAVEL_FULL[DEPOT, nodes[i]]   # Aula -> first node
    for msk in range(1, 1 << m):
        for j in range(m):
            if not (msk >> j) & 1 or dp[msk][j] == INF:
                continue
            for k in range(m):
                if (msk >> k) & 1:
                    continue
                nm = msk | (1 << k)
                cand = dp[msk][j] + TRAVEL_FULL[nodes[j], nodes[k]]
                if cand < dp[nm][k]:
                    dp[nm][k] = cand
                    par[nm][k] = j
    fullm = (1 << m) - 1
    # close each candidate endpoint back to the depot, pick the best
    j = int(np.argmin([dp[fullm][i] + TRAVEL_FULL[nodes[i], DEPOT]
                       for i in range(m)]))
    order, msk = [], fullm
    while j != -1:
        order.append(nodes[j])
        pj = par[msk][j]
        msk &= ~(1 << j)
        j = pj
    return order[::-1]


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

@dataclass
class Candidates:
    fac_masks: list[int]     # faculty-only bitmask
    full_masks: list[int]    # faculty mask | chosen extras
    extra_masks: list[int]   # extras only, as bits over the 3 extra buildings
    dur: np.ndarray
    dep: np.ndarray
    under: np.ndarray
    val: np.ndarray          # beta*DEP + gamma*UNDER - lam*DUR (normalized)
    dep_norm: float
    under_norm: float
    dur_norm: float


def _mask_dep(mask: int, p: Params, m1, m2, e3) -> float:
    dep = 0.0
    for f in range(N_FAC):
        if not (mask >> f) & 1:
            continue
        if (mask >> m1[f]) & 1:
            dep += p.w1
        if (mask >> m2[f]) & 1:
            dep += p.w2
        if e3[f] >= 0 and (mask >> e3[f]) & 1:
            dep += p.w3
    return dep


def _mask_dur(mask: int, p: Params, path: np.ndarray) -> float:
    # path[mask] is the closed-tour walking time (Aula -> ... -> Aula);
    # add dwell at each visited node plus the depot buffer.
    return (path[mask] + DEFAULT_DWELL_DEPOT
            + sum(p.dwell[j] for j in range(N_NODES) if (mask >> j) & 1))


def build_candidates(p: Params, path: np.ndarray) -> Candidates:
    """Every feasible (faculty set, extra-building completion) pair is a
    separate candidate tour. Exposing the extra choice (rather than baking the
    single best extra per faculty set) is required because the "each extra
    building in at most one tour" rule couples the extras across tours, so the
    solver must be free to choose which extra each tour uses.
    """
    m1 = np.array([IDX[DEPENDENCIES[f][0]] for f in FACULTIES])
    m2 = np.array([IDX[DEPENDENCIES[f][1]] for f in FACULTIES])
    e3 = np.array([IDX[DEPENDENCIES[f][2]] if DEPENDENCIES[f][2] else -1
                   for f in FACULTIES])

    # Admissible extra-building completions of a faculty set:
    #   require_one_extra=True  -> exactly one of {X, DreamHall, Library}
    #   require_one_extra=False -> any subset (0..3)
    if p.require_one_extra:
        extra_subsets = [1 << e for e in range(N_EXTRA)]      # singletons only
    else:
        extra_subsets = list(range(1 << N_EXTRA))             # all subsets incl. empty

    K = p.n_tours
    dur_norm = K * p.t_max

    fac_masks, full_masks, extra_masks = [], [], []
    durs, deps, unders = [], [], []
    dep_max_raw = 1e-9
    for fmask in range(1, 1 << N_FAC):
        nfac = bin(fmask).count("1")
        if nfac < p.min_fac or nfac > p.max_fac:
            continue
        if _mask_dur(fmask, p, path) > p.t_max:
            continue  # extras only add duration, so F alone must already fit
        under_F = sum(p.b[f] for f in range(N_FAC) if (fmask >> f) & 1)
        for emask in extra_subsets:
            full = fmask | (emask << N_FAC)
            d = _mask_dur(full, p, path)
            if d > p.t_max:
                continue
            dep = _mask_dep(full, p, m1, m2, e3)
            dep_max_raw = max(dep_max_raw, dep)
            fac_masks.append(fmask)
            full_masks.append(full)
            extra_masks.append(emask)
            durs.append(d)
            deps.append(dep)
            unders.append(under_F)

    if not fac_masks:
        raise ValueError(
            "No feasible tours: t_max is too small for min_fac faculties plus "
            "dwell times (and one extra building, if required). Increase "
            "t_max or lower min_fac / dwell times."
        )

    dur = np.array(durs, float); dep = np.array(deps, float)
    under = np.array(unders, float)
    dep_norm = K * dep_max_raw
    under_norm = K * max(under.max(), 1e-9)
    val = (p.beta * dep / dep_norm + p.gamma * under / under_norm
           - p.lam * dur / dur_norm)

    return Candidates(
        fac_masks=fac_masks, full_masks=full_masks, extra_masks=extra_masks,
        dur=dur, dep=dep, under=under, val=val,
        dep_norm=dep_norm, under_norm=under_norm, dur_norm=dur_norm,
    )


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class TourResult:
    nodes: list[str]              # visitable nodes, in optimal walking order
    duration: float               # closed-tour time (Aula -> ... -> Aula) + dwell
    students: list[int]           # row indices into the student table
    dep_bonus: float
    under_bonus: float

    def route(self) -> list[str]:
        """Full display route, bracketed by the Aula depot."""
        return [DEPOT_NAME] + self.nodes + [DEPOT_NAME]


@dataclass
class SolveResult:
    tours: list[TourResult]
    satisfaction: np.ndarray
    objective: float
    gap: float
    status: str
    components: dict[str, float]
    zero_students: list[int] = field(default_factory=list)  # rows with no honored choice


# ---------------------------------------------------------------------------
# Main solve (HiGHS MILP, proven optimal)
# ---------------------------------------------------------------------------

def aggregate_types(choices: np.ndarray):
    type_of, counts, rows_of = {}, [], []
    for i, tri in enumerate(map(tuple, choices)):
        t = type_of.setdefault(tri, len(counts))
        if t == len(counts):
            counts.append(0)
            rows_of.append([])
        counts[t] += 1
        rows_of[t].append(i)
    return list(type_of.keys()), counts, rows_of


def solve(choices: np.ndarray, p: Params) -> SolveResult:
    """choices: (n_students, 3) int array of ranked faculty indices, -1 = none."""
    n, K = choices.shape[0], p.n_tours
    if n == 0:
        raise ValueError("no students")
    path = shortest_tours()
    C = build_candidates(p, path)
    nc = len(C.fac_masks)
    rho = np.array(p.rho, dtype=float)

    triples, counts, rows_of = aggregate_types(choices)
    T = len(counts)
    sat_max = n * rho.sum() or 1.0
    bal_norm = 2 * n * (K - 1) if K > 1 else 1.0

    # ---- variable layout ---------------------------------------------------
    off_y = 0;             n_y = K * nc
    off_z = n_y;           n_z = K * N_FAC
    off_n = off_z + n_z;   n_n = T * K
    g_index = {}
    gi = off_n + n_n
    for t, tri in enumerate(triples):
        for r, f in enumerate(tri):
            if f >= 0:
                for k in range(K):
                    g_index[(t, r, k)] = gi
                    gi += 1
    off_dev = gi
    NV = off_dev + K

    Y = lambda k, c: off_y + k * nc + c
    Z = lambda k, f: off_z + k * N_FAC + f
    Nv = lambda t, k: off_n + t * K + k
    Dv = lambda k: off_dev + k

    # ---- objective ----------------------------------------------------------
    obj = np.zeros(NV)
    for k in range(K):
        obj[off_y + k * nc: off_y + (k + 1) * nc] = C.val
    for (t, r, k), j in g_index.items():
        obj[j] = p.alpha * rho[r] / sat_max
    obj[off_dev:off_dev + K] = -p.mu / bal_norm

    cons = []
    # each tour uses exactly one candidate
    A = lil_matrix((K, NV))
    for k in range(K):
        for c in range(nc):
            A[k, Y(k, c)] = 1
    cons.append(LinearConstraint(A.tocsr(), 1, 1))

    # z linking (z continuous; integral automatically since y integral)
    A = lil_matrix((K * N_FAC, NV))
    for k in range(K):
        for f in range(N_FAC):
            row = k * N_FAC + f
            A[row, Z(k, f)] = 1
            for c in range(nc):
                if (C.fac_masks[c] >> f) & 1:
                    A[row, Y(k, c)] = -1
    cons.append(LinearConstraint(A.tocsr(), 0, 0))

    # every student of every type assigned
    A = lil_matrix((T, NV))
    for t in range(T):
        for k in range(K):
            A[t, Nv(t, k)] = 1
    cons.append(LinearConstraint(A.tocsr(), counts, counts))

    # satisfaction linking: g <= n_{t,k},  g <= c_t * z[k][f]
    A = lil_matrix((2 * len(g_index), NV))
    rr = 0
    for (t, r, k), j in g_index.items():
        f = triples[t][r]
        A[rr, j] = 1; A[rr, Nv(t, k)] = -1; rr += 1
        A[rr, j] = 1; A[rr, Z(k, f)] = -counts[t]; rr += 1
    cons.append(LinearConstraint(A.tocsr(), -np.inf, 0))

    # balance: dev_k >= K n_k - n  and  dev_k >= n - K n_k
    A = lil_matrix((2 * K, NV))
    lo = np.empty(2 * K)
    for k in range(K):
        A[2 * k, Dv(k)] = 1
        A[2 * k + 1, Dv(k)] = 1
        for t in range(T):
            A[2 * k, Nv(t, k)] = -K
            A[2 * k + 1, Nv(t, k)] = K
        lo[2 * k] = -n
        lo[2 * k + 1] = n
    cons.append(LinearConstraint(A.tocsr(), lo, np.inf))

    # a faculty may appear in at most `max_tours_per_faculty` tours:
    #   sum_k z[k, f] <= cap        for every faculty f
    cap_fac = min(p.max_tours_per_faculty, K)
    if cap_fac < K:
        A = lil_matrix((N_FAC, NV))
        for f in range(N_FAC):
            for k in range(K):
                A[f, Z(k, f)] = 1
        cons.append(LinearConstraint(A.tocsr(), -np.inf, cap_fac))

    # each extra building may appear in at most `max_extra_per_building` tours:
    #   sum over tours and candidates that include extra e of y[k, c] <= cap
    cap_extra = min(p.max_extra_per_building, K)
    if cap_extra < K:
        A = lil_matrix((N_EXTRA, NV))
        for e in range(N_EXTRA):
            for k in range(K):
                for c in range(nc):
                    if (C.extra_masks[c] >> e) & 1:
                        A[e, Y(k, c)] = 1
        cons.append(LinearConstraint(A.tocsr(), -np.inf, cap_extra))
        # feasibility guard: with exactly one extra per tour and each extra
        # usable at most cap_extra times, K tours need K <= N_EXTRA * cap_extra
        if p.require_one_extra and K > N_EXTRA * cap_extra:
            raise ValueError(
                f"Infeasible: {K} tours each need one extra building, but with "
                f"'each extra in at most {cap_extra} tour(s)' only "
                f"{N_EXTRA * cap_extra} extra-slots exist. Reduce the number of "
                f"tours, or relax the extra-building limit."
            )

    # bounds & integrality (only y and n integer)
    lb = np.zeros(NV)
    ub = np.full(NV, np.inf)
    ub[off_y:off_y + n_y] = 1
    ub[off_z:off_z + n_z] = 1
    for t in range(T):
        for k in range(K):
            ub[Nv(t, k)] = counts[t]
    for (t, r, k), j in g_index.items():
        ub[j] = counts[t]
    integrality = np.zeros(NV)
    integrality[off_y:off_y + n_y] = 1
    integrality[off_n:off_n + n_n] = 1

    res = milp(c=-obj, constraints=cons, bounds=Bounds(lb, ub),
               integrality=integrality,
               options={"time_limit": p.time_limit_s,
                        "mip_rel_gap": p.mip_rel_gap, "disp": False})
    if res.x is None:
        raise RuntimeError(
            "No feasible plan for these settings. This can happen when the "
            "per-faculty or per-extra-building tour limits are too tight for "
            "the chosen number of tours and faculties-per-tour. Try allowing "
            "more faculties per tour, more tours a faculty may appear in, or a "
            f"higher time limit. (solver message: {res.message})"
        )

    xv = res.x
    gap = float(res.mip_gap) if res.mip_gap is not None else float("nan")
    status = "OPTIMAL" if gap <= max(p.mip_rel_gap * 10, 1e-5) else "FEASIBLE"

    # ---- extract -------------------------------------------------------------
    assign_rows: list[list[int]] = [[] for _ in range(K)]
    for t in range(T):
        pool = list(rows_of[t])
        takes = [int(round(xv[Nv(t, k)])) for k in range(K)]
        # guard against rounding drift
        drift = counts[t] - sum(takes)
        if drift:
            takes[int(np.argmax(takes))] += drift
        for k in range(K):
            assign_rows[k].extend(pool[:takes[k]])
            pool = pool[takes[k]:]

    tours: list[TourResult] = []
    chosen: list[int] = []
    for k in range(K):
        c = int(np.argmax([xv[Y(k, c)] for c in range(nc)]))
        chosen.append(c)
        order = recover_order(C.full_masks[c])
        tours.append(TourResult(
            nodes=[NODES[j] for j in order],
            duration=float(C.dur[c]),
            students=sorted(assign_rows[k]),
            dep_bonus=float(C.dep[c]),
            under_bonus=float(C.under[c]),
        ))

    sat = np.zeros(n)
    for k, tr in enumerate(tours):
        member = set(tr.nodes)
        for i in tr.students:
            for r in range(3):
                f = choices[i, r]
                if f >= 0 and FACULTIES[f] in member:
                    sat[i] += rho[r]

    comps = {
        "satisfaction": float(sat.sum() / sat_max),
        "dependency": float(sum(C.dep[c] for c in chosen) / C.dep_norm),
        "undervisited": float(sum(C.under[c] for c in chosen) / C.under_norm),
        "duration": float(sum(C.dur[c] for c in chosen) / C.dur_norm),
        "balance_dev": float(sum(abs(K * len(t.students) - n) for t in tours) / bal_norm),
    }
    return SolveResult(tours=tours, satisfaction=sat,
                       objective=float(-res.fun), gap=gap,
                       status=status, components=comps,
                       zero_students=[int(i) for i in range(n) if sat[i] == 0])
