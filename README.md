# TU Delft Campus Tour Optimizer

Design a set of guided campus tours and assign every student to a tour, so that
students see the faculties they asked for, related faculties are grouped
sensibly, tours stay short, and the groups come out roughly equal in size.

Every tour starts and ends at the Aula (building 20). The tool does not guess or
approximate the answer: for the settings you choose it returns a provably
optimal plan.

---

## Quick start

```bash
# 1. (optional) create a clean environment
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. run the app
streamlit run app.py
```

A browser tab opens. Upload the student Excel (or use the built-in sample), set
the sliders, and press "Optimize". See `USER_GUIDE.md` for what every slider
does — no technical background needed.

To run without the interface (a quick console check):

```bash
python test_run.py      # solves the bundled sample and prints a report
python verify.py        # runs the correctness checks (see below)
```

---

## Input format

An Excel file, one row per student, with a name column plus three ranked
choices. Students submit bachelor programmes; the tool maps them to faculties
automatically.

| Student      | Choice1           | Choice2                | Choice3   |
|--------------|-------------------|------------------------|-----------|
| Student_001  | Werktuigbouwkunde | Electrical Engineering | Bouwkunde |

Faculty codes (`AE, BK, CITG, EWI, IO, ME, TNW-zuid, TNW, TBM`) are also
accepted directly. If a student lists several programmes from the same faculty,
that faculty is counted once, at its best rank. `sample_students.xlsx` is a
ready-made example with 50 students, generated from real programme
co-occurrence data (which programmes are commonly chosen together); the app uses
it automatically when no file is uploaded. `make_sample_data.make_files(...)`
writes additional examples of other sizes.

The programme-to-faculty mapping lives in `campus_data.py`
(`PROGRAM_TO_FACULTY`); edit it there if a programme is added or renamed.

---

## What you get back

- One route per tour, written as `Aula -> ... -> Aula`, with its total time.
- The list of students on each tour.
- A clear list of students who got none of their three chosen faculties.
- A satisfaction chart and a campus map with the real building positions.
- An Excel download with sheets `Tours`, `Assignments`, and `NoChoiceHonored`.

---

## Files

| File                 | What it is |
|----------------------|------------|
| `app.py`             | The Streamlit web interface. |
| `model.py`           | The solver: route pre-computation and the optimization. |
| `campus_data.py`     | Faculties, programme mapping, the Aula travel-time matrix, faculty pairings. |
| `make_sample_data.py`| Generates a synthetic 100-student Excel from real programme co-occurrence data. |
| `test_run.py`        | Console end-to-end run on the sample. |
| `verify.py`          | Independent correctness checks (proof the answer is right). |
| `travel_times.csv`   | Editable walking-time matrix (see "Travel times" below). |
| `HOW_IT_WORKS.md`    | A gentle explanation of the method. |
| `WALKTHROUGH.md`     | An extensive, rigorous "why it works" walkthrough. |
| `USER_GUIDE.md`      | Plain-language guide to the sliders, for the operator. |

---

## Travel times

All walking times (building-to-building and to/from the Aula) are measured
values, stored in `travel_times.csv` and baked into `campus_data.py`. To update
them, edit the numbers and load the file:

```python
import campus_data
campus_data.export_travel_template("travel_times.csv")  # writes the current matrix
# edit travel_times.csv in Excel, then:
campus_data.load_travel_csv("travel_times.csv")         # installs your numbers
```

Nothing else changes — the rest of the tool adapts automatically.

---

## Correctness

`verify.py` checks four things independently of the solver:

1. Turning on the internal speed-up ("pruning") gives the same answer as
   leaving it off.
2. The reported score, recomputed from scratch, matches the solver's score.
3. Every student is assigned exactly once and every tour respects its limits.
4. Each tour's travel time is confirmed optimal by brute force (checking every
   possible visiting order).

All four pass on the bundled sample.
