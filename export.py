"""Build the downloadable Excel record of one optimization run.

The record is designed to be both readable per run and easy to stack and analyse
across many runs: every sheet carries the same `run_id`, so several runs can be
appended into master tabs and split apart again with a pivot or filter.

Privacy: student names are never written. Every student is a neutral id
(Student_001, ...), and no name<->id key is produced, so the file is fully
anonymised and carries no personal data.

Four sheets:
  Summary     one row per run: all inputs (settings + per-faculty bonus) and the
              headline outputs (objective, satisfaction, rank distribution).
  Tours       one row per tour: each stop in walking order (stop1, stop2, ...),
              the extra building, the sorted faculty set (a stable key for
              route-frequency counting), duration, group size, score bonuses.
  Input       one row per student (anonymised): the submitted programme choices
              and their mapped faculties.
  Assignment  one row per student (anonymised): assigned tour and, for each of
              their three ranked choices, whether that faculty was on the tour.
"""

from __future__ import annotations

import io
import numpy as np
import pandas as pd

from campus_data import FACULTIES, EXTRAS, N_FAC
from model import TOOL_VERSION


def _student_id(i: int) -> str:
    return f"Student_{i + 1:03d}"


def _achieved_rank(choices_row, member) -> int:
    """Best (lowest) honored rank 1..3 for a student, or 0 if none."""
    for r in range(3):
        f = choices_row[r]
        if f >= 0 and FACULTIES[f] in member:
            return r + 1
    return 0


def run_metadata(p, meta: dict) -> dict:
    """Flat dict of all run inputs (settings + bonuses), for the Summary row."""
    dwell_fac = float(p.dwell[0]) if len(p.dwell) else float("nan")
    dwell_extra = float(p.dwell[N_FAC]) if len(p.dwell) > N_FAC else float("nan")
    row = {
        "run_id": meta["run_id"],
        "timestamp": meta["timestamp"],
        "tool_version": meta.get("tool_version", TOOL_VERSION),
        "data_source": meta.get("data_source", ""),
        "seed": meta.get("seed", ""),
        "n_students": meta.get("n_students", ""),
        # tour structure
        "n_tours": p.n_tours,
        "max_tour_duration_min": p.t_max,
        "min_faculties_per_tour": p.min_fac,
        "max_faculties_per_tour": p.max_fac,
        "dwell_faculty_min": dwell_fac,
        "dwell_extra_min": dwell_extra,
        "exactly_one_extra": p.require_one_extra,
        "max_tours_per_faculty": p.max_tours_per_faculty,
        "max_extra_per_building": p.max_extra_per_building,
        # weights (same names as the app sliders, in plain terms)
        "w_student_preferences": p.alpha,
        "w_faculty_combinations": p.beta,
        "w_undervisited": p.gamma,
        "w_shorter_tours": p.lam,
        "w_equal_groups": p.mu,
        "rank_weight_1st": p.rho[0],
        "rank_weight_2nd": p.rho[1],
        "rank_weight_3rd": p.rho[2],
        "dep_w1_first_partner": p.w1,
        "dep_w2_second_partner": p.w2,
        "dep_w3_extra_building": p.w3,
    }
    # per-faculty undervisited bonus (0 when none given)
    for f, name in enumerate(FACULTIES):
        row[f"bonus_{name}"] = float(p.b[f]) if f < len(p.b) else 0.0
    return row


def build_workbook(res, p, meta: dict, df_used: pd.DataFrame,
                   choices: np.ndarray) -> bytes:
    """Return the .xlsx bytes for one run. `choices` is the (n,3) faculty-index
    matrix matching df_used (so the anonymised Input/Assignment stay aligned)."""
    run_id = meta["run_id"]
    n = len(df_used)
    rho_sum = float(sum(p.rho))

    # ---- per-student achieved rank (1/2/3/0) and assigned tour --------------
    assigned_tour = np.full(n, -1, dtype=int)
    achieved = np.zeros(n, dtype=int)
    for k, t in enumerate(res.tours):
        member = set(t.nodes)
        for i in t.students:
            assigned_tour[i] = k + 1
            achieved[i] = _achieved_rank(choices[i], member)

    got_first = int((achieved == 1).sum())
    got_second = int((achieved == 2).sum())
    got_third = int((achieved == 3).sum())
    got_none = int((achieved == 0).sum())

    # ---- Summary (one row) -------------------------------------------------
    # The "objective_total_score" is the single value the optimizer maximizes:
    #   alpha*SAT + beta*DEP + gamma*UNDER - lam*DUR - mu*BAL,
    # i.e. the weighted sum of the five normalized component scores below.
    summary = run_metadata(p, meta)
    summary.update({
        "objective_total_score": round(res.objective, 4),
        "solver_status": res.status,
        "satisfaction_mean": round(float(res.satisfaction.mean()), 3),
        "satisfaction_max_possible": rho_sum,
        # the five normalized [0,1] component scores (before weighting)
        "satisfaction_score_0to1": round(res.components.get("satisfaction"), 4),
        "faculty_combinations_score_0to1": round(res.components.get("dependency"), 4),
        "undervisited_score_0to1": round(res.components.get("undervisited"), 4),
        "tour_duration_score_0to1": round(res.components.get("duration"), 4),
        "group_balance_score_0to1": round(res.components.get("balance_dev"), 4),
        "students_got_1st_choice": got_first,
        "students_got_2nd_choice": got_second,
        "students_got_3rd_choice": got_third,
        "students_got_no_choice": got_none,
    })
    for k, t in enumerate(res.tours):           # one column per tour's group size
        summary[f"group_size_tour{k + 1}"] = len(t.students)
    summary_df = pd.DataFrame([summary])

    # ---- Tours (one row per tour) ------------------------------------------
    max_stops = max((len(t.nodes) for t in res.tours), default=0)
    tour_rows = []
    for k, t in enumerate(res.tours):
        facs = sorted(nm for nm in t.nodes if nm in FACULTIES)
        extras = [nm for nm in t.nodes if nm in EXTRAS]
        row = {
            "run_id": run_id,
            "tour": k + 1,
            "faculties_sorted": "|".join(facs),      # stable key for frequency counts
            "extra_building": "|".join(extras),
            "n_faculties": len(facs),
            "duration_min": round(t.duration, 1),
            "group_size": len(t.students),
            "dependency_bonus": round(t.dep_bonus, 3),
            "undervisited_bonus": round(t.under_bonus, 3),
        }
        # each visited location in walking order as its own cell (every tour
        # still starts and ends at the Aula, which is left implicit here)
        for s in range(max_stops):
            row[f"stop{s + 1}"] = t.nodes[s] if s < len(t.nodes) else ""
        tour_rows.append(row)
    stop_cols = [f"stop{s + 1}" for s in range(max_stops)]
    tours_df = pd.DataFrame(tour_rows)[
        ["run_id", "tour"] + stop_cols
        + ["extra_building", "faculties_sorted", "n_faculties", "duration_min",
           "group_size", "dependency_bonus", "undervisited_bonus"]
    ]

    # ---- Input (one row per student, anonymised) ---------------------------
    def prog(i, col):
        v = df_used.iloc[i].get(col, "")
        return "" if pd.isna(v) else v
    fac_name = lambda f: FACULTIES[f] if f >= 0 else ""
    input_rows = [{
        "run_id": run_id,
        "student_id": _student_id(i),
        "Choice1": prog(i, "Choice1"),
        "Choice2": prog(i, "Choice2"),
        "Choice3": prog(i, "Choice3"),
        "Faculty1": fac_name(choices[i, 0]),
        "Faculty2": fac_name(choices[i, 1]),
        "Faculty3": fac_name(choices[i, 2]),
    } for i in range(n)]
    input_df = pd.DataFrame(input_rows)

    # ---- Assignment (one row per student, anonymised) ----------------------
    # For each of the student's three ranked choices, whether that faculty was
    # on the tour they were assigned to (so all three are visible, not only the
    # best one). A blank means that rank had no distinct faculty (it mapped to
    # the same faculty as a higher-ranked choice and was merged).
    assign_rows = []
    for i in range(n):
        member = set(res.tours[assigned_tour[i] - 1].nodes)
        got_flags = {}
        n_received = 0
        for r in range(3):
            f = choices[i, r]
            if f < 0:
                got_flags[f"got_choice{r + 1}"] = ""        # merged / no distinct faculty
            elif FACULTIES[f] in member:
                got_flags[f"got_choice{r + 1}"] = "yes"
                n_received += 1
            else:
                got_flags[f"got_choice{r + 1}"] = "no"
        best = achieved[i]
        assign_rows.append({
            "run_id": run_id,
            "student_id": _student_id(i),
            "assigned_tour": int(assigned_tour[i]),
            **got_flags,
            "n_choices_received": n_received,
            "best_rank_received": best,                # 1/2/3, or 0 = none
            "satisfaction_score": float(res.satisfaction[i]),
        })
    assign_df = pd.DataFrame(assign_rows)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        summary_df.to_excel(xw, sheet_name="Summary", index=False)
        tours_df.to_excel(xw, sheet_name="Tours", index=False)
        input_df.to_excel(xw, sheet_name="Input", index=False)
        assign_df.to_excel(xw, sheet_name="Assignment", index=False)
    return buf.getvalue()
