"""
Streamlit frontend for the TU Delft campus tour optimizer.

Run with:  streamlit run app.py
"""

import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from campus_data import (
    FACULTIES, EXTRAS, NODES, _COORD, default_dwell, N_FAC,
    build_choice_matrix, PROGRAM_TO_FACULTY,
)
from make_sample_data import make
from model import Params, solve

st.set_page_config(page_title="TU Delft Tour Optimizer", layout="wide")
st.title("TU Delft Campus Tour Optimizer")
st.caption(
    "Upload the student preferences, set the parameters, press **Optimize**. "
    "The solver finds the provably best combination of tours and student "
    "assignment for the chosen weights."
)

# ---------------------------------------------------------------------------
# Sidebar: parameters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Tour structure")
    K = st.slider("Number of tours", 1, 6, 3)
    t_max = st.slider("Max tour duration (minutes)", 45, 240, 120, step=5)
    min_fac, max_fac = st.slider("Faculties per tour (min–max)", 1, 9, (2, 5))
    dwell_fac = st.slider("Time spent per faculty (min)", 5, 40, 15)
    dwell_extra = st.slider("Time spent per extra building (min)", 0, 30, 10)
    one_extra = st.checkbox("Exactly one extra building per tour", value=True,
                            help="Each tour includes exactly one of X, DreamHall "
                                 "or Library. Turn off to let the tool choose any "
                                 "number (including none).")

    st.header("What matters how much?")
    st.caption("All components are normalized, so weights are comparable.")
    alpha = st.slider("Student preferences", 0.0, 2.0, 1.0, 0.05)
    beta = st.slider("Faculty combinations (dependencies)", 0.0, 2.0, 0.4, 0.05)
    gamma = st.slider("Undervisited faculties", 0.0, 2.0, 0.3, 0.05)
    lam = st.slider("Shorter tours", 0.0, 2.0, 0.3, 0.05)
    mu = st.slider("Equal group sizes", 0.0, 2.0, 0.5, 0.05)

    with st.expander("Advanced"):
        rho1 = st.number_input("Weight of 1st choice", 0.0, 10.0, 3.0)
        rho2 = st.number_input("Weight of 2nd choice", 0.0, 10.0, 2.0)
        rho3 = st.number_input("Weight of 3rd choice", 0.0, 10.0, 1.0)
        w1 = st.number_input("Bonus: 1st-degree partner in same tour", 0.0, 10.0, 2.0)
        w2 = st.number_input("Bonus: 2nd-degree partner in same tour", 0.0, 10.0, 1.0)
        w3 = st.number_input("Bonus: designated extra building", 0.0, 10.0, 1.0)
        tlimit = st.number_input("Solver time limit (s)", 10, 600, 120)

# ---------------------------------------------------------------------------
# Main: data input
# ---------------------------------------------------------------------------
col_l, col_r = st.columns([1, 1])

with col_l:
    st.subheader("1 · Student preferences")
    st.markdown(
        "Excel with one row per student and columns Student, Choice1, "
        "Choice2, Choice3 (ranked bachelor programmes). Programmes are mapped "
        "to faculties automatically."
    )
    up = st.file_uploader("Upload Excel", type=["xlsx", "xls"])
    if up is not None:
        df = pd.read_excel(up)
    else:
        st.info("No file uploaded — using the built-in example (50 students, "
                "based on real programme co-occurrence data).")
        df = make(50, path=None)          # in-memory; no file written

    # column check (case-insensitive)
    have = {c.lower().strip(): c for c in df.columns}
    missing = [f"Choice{k}" for k in (1, 2, 3)
               if f"choice{k}" not in have]
    if missing:
        st.error("Missing column(s): " + ", ".join(missing) + ".")
        st.stop()
    # normalize the three choice columns to canonical names for the mapper
    ren = {have[f"choice{k}"]: f"Choice{k}" for k in (1, 2, 3)}
    df = df.rename(columns=ren)

    choices, unknown = build_choice_matrix(df)
    if unknown:
        preview = "; ".join(f"row {i + 2}: \"{v}\"" for i, _, v in unknown[:5])
        st.warning(
            f"{len(unknown)} entry(ies) could not be matched to a programme or "
            f"faculty and were ignored (e.g. {preview})."
        )
    n_multi = int(((choices >= 0).sum(axis=1) < 3).sum())
    st.write(f"{len(df)} students loaded, "
             f"{len(set(map(tuple, choices)))} distinct preference profiles.")
    st.caption("Bachelor programmes are automatically mapped to faculties; "
               "duplicate faculties within one student's list are merged.")
    st.dataframe(df.head(8), height=220)

with col_r:
    st.subheader("2 · Undervisited faculties")
    st.markdown("Give a bonus to faculties that should be visited more often "
                "(0 = no bonus).")
    bonus_df = st.data_editor(
        pd.DataFrame({"Faculty": FACULTIES, "Bonus": [0.0] * N_FAC}),
        hide_index=True, disabled=["Faculty"], height=360, key="bonus_editor",
    )
    b = bonus_df["Bonus"].to_numpy(dtype=float)

# ---------------------------------------------------------------------------
# Solve
# ---------------------------------------------------------------------------
st.subheader("3 · Optimize")
if st.button("Optimize", type="primary"):
    dwell = default_dwell()
    dwell[:N_FAC] = dwell_fac
    dwell[N_FAC:] = dwell_extra
    p = Params(
        n_tours=K, t_max=float(t_max), min_fac=min_fac, max_fac=max_fac,
        dwell=dwell, alpha=alpha, beta=beta, gamma=gamma, lam=lam, mu=mu,
        rho=(rho1, rho2, rho3), w1=w1, w2=w2, w3=w3, b=b,
        time_limit_s=float(tlimit), require_one_extra=one_extra,
    )
    with st.spinner("Solving to proven optimality (typically < 1 minute)..."):
        try:
            res = solve(choices, p)
        except (ValueError, RuntimeError) as e:
            st.error(str(e))
            st.stop()
    st.session_state["result"] = (res, df, p)

if "result" in st.session_state:
    res, df_used, p_used = st.session_state["result"]
    if len(df_used) != len(df):
        st.info("Data changed since last run — press Optimize again.")

    quality = ("proven optimal" if res.status == "OPTIMAL"
               else f"within {res.gap:.1%} of optimal (proven bound)")
    st.success(f"Solution is **{quality}**.")

    m1, m2, m3 = st.columns(3)
    rho_sum = sum(p_used.rho)
    m1.metric("Avg. satisfaction", f"{res.satisfaction.mean():.2f} / {rho_sum:g}")
    m2.metric("Students with none of their choices",
              int((res.satisfaction == 0).sum()))
    m3.metric("Longest tour", f"{max(t.duration for t in res.tours):.0f} min")

    # ---- students with none of their choices honored ------------------------
    name_col = df_used.columns[0]
    if res.zero_students:
        st.error(
            f"**{len(res.zero_students)} student(s) got none of their three "
            f"chosen faculties.** They still have a tour, but you may want to "
            f"review them:"
        )
        zdf = pd.DataFrame([{
            "Student": df_used.iloc[i][name_col],
            "Choice1": df_used.iloc[i].get("Choice1", ""),
            "Choice2": df_used.iloc[i].get("Choice2", ""),
            "Choice3": df_used.iloc[i].get("Choice3", ""),
            "Assigned tour": next(k + 1 for k, t in enumerate(res.tours)
                                  if i in t.students),
        } for i in res.zero_students])
        st.dataframe(zdf, hide_index=True)
    else:
        st.success("Every student got at least one of their chosen faculties.")

    # ---- per-tour details ---------------------------------------------------
    for k, t in enumerate(res.tours):
        with st.expander(
            f"Tour {k + 1}:  {'  →  '.join(t.route())}   "
            f"({t.duration:.0f} min, {len(t.students)} students)",
            expanded=True,
        ):
            st.write(f"Dependency bonus {t.dep_bonus:g} · "
                     f"undervisited bonus {t.under_bonus:g}")
            st.write(", ".join(str(df_used.iloc[i][name_col]) for i in t.students))

    # ---- satisfaction distribution + campus map ----------------------------
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Satisfaction distribution**")
        vals, cnts = np.unique(res.satisfaction, return_counts=True)
        st.bar_chart(pd.DataFrame({"students": cnts},
                                  index=[f"{v:g}" for v in vals]))
        st.caption("0 = none of the three chosen faculties are on the "
                   "assigned tour; higher = better-ranked choices honored.")
    with c2:
        st.markdown("**Campus map (schematic)**")
        fig, ax = plt.subplots(figsize=(5, 6))
        for nm, (x, y) in _COORD.items():
            if nm == "Aula":
                ax.scatter(x, -y, s=180, marker="*", color="#c00", zorder=5)
                ax.annotate("Aula", (x, -y), fontsize=8, fontweight="bold",
                            xytext=(4, 4), textcoords="offset points")
            else:
                ax.scatter(x, -y, s=30, color="#888")
                ax.annotate(nm, (x, -y), fontsize=7,
                            xytext=(3, 3), textcoords="offset points")
        colors = plt.cm.tab10.colors
        for k, t in enumerate(res.tours):
            xs = [_COORD[nm][0] for nm in t.route()]
            ys = [-_COORD[nm][1] for nm in t.route()]
            ax.plot(xs, ys, "-o", color=colors[k % 10], lw=2, ms=5,
                    label=f"Tour {k + 1}", alpha=0.75)
        ax.legend(fontsize=8)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        st.pyplot(fig)

    # ---- download -----------------------------------------------------------
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame([{
            "Tour": k + 1,
            "Route": " -> ".join(t.route()),
            "Duration (min)": round(t.duration),
            "Students": len(t.students),
        } for k, t in enumerate(res.tours)]).to_excel(
            xw, sheet_name="Tours", index=False)
        rows = []
        for k, t in enumerate(res.tours):
            for i in t.students:
                rows.append({
                    "Student": df_used.iloc[i][name_col],
                    "Tour": k + 1,
                    "Route": " -> ".join(t.route()),
                    "Satisfaction": res.satisfaction[i],
                    "GotAChoice": "no" if res.satisfaction[i] == 0 else "yes",
                })
        pd.DataFrame(rows).to_excel(xw, sheet_name="Assignments", index=False)

        # dedicated sheet listing students with no honored choice
        zrows = [{
            "Student": df_used.iloc[i][name_col],
            "Choice1": df_used.iloc[i].get("Choice1", ""),
            "Choice2": df_used.iloc[i].get("Choice2", ""),
            "Choice3": df_used.iloc[i].get("Choice3", ""),
            "AssignedTour": next(k + 1 for k, t in enumerate(res.tours)
                                 if i in t.students),
        } for i in res.zero_students]
        pd.DataFrame(zrows if zrows else [{"Student": "(none)"}]).to_excel(
            xw, sheet_name="NoChoiceHonored", index=False)
    st.download_button("Download result (Excel)", buf.getvalue(),
                       file_name="tour_assignment.xlsx")
