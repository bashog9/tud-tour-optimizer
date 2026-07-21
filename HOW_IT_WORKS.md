# How it works — a gentle walkthrough

This explains the method in layers: first the idea, then the moving parts, then
where each part lives in the code. You do not need to read `model.py` to follow
it. Notation is kept light; the precise formulas are in the docstrings.

Throughout, names in quotes like "Number of tours" or "alpha" refer to a
specific slider or variable you can actually set.

---

## 1. The problem in one paragraph

We have about 100 students. Each submitted three bachelor programmes they'd like
to visit, in order of preference. We must build a handful of walking tours (say
3), each starting and ending at the Aula, and put every student on exactly one
tour. A good plan sends students to tours that contain the faculties they asked
for, keeps the tours short, groups faculties that belong together, and makes the
groups roughly equal in size. Two decisions are tangled together: which
faculties each tour visits, and which tour each student joins.

---

## 2. From programmes to faculties

Students choose bachelor programmes, but a tour visits faculty buildings, not
programmes. So the first thing the tool does is translate each programme to its
faculty, e.g. "Werktuigbouwkunde", "Maritieme Techniek" and "Klinische
Technologie" all become the faculty "ME". Several programmes can share a
faculty.

One consequence: a student might list three programmes that all belong to the
same faculty. After translation they effectively asked for one faculty, so we
merge duplicates — the faculty is counted once, at the best (highest) rank the
student gave it. The weight of a choice always follows the position the student
wrote it in (first choice counts most). This mapping lives in
`campus_data.py` (`PROGRAM_TO_FACULTY`, `build_choice_matrix`).

---

## 3. The one insight that makes it easy

The order in which a tour visits its faculties does not matter for how happy
students are — only which faculties are on the tour. A student who wanted EWI is
equally happy whether EWI is stop 2 or stop 5.

So we can describe a tour by the set of places it visits, ignoring order. Order
matters for exactly one thing: how long the tour takes. Visiting the same four
faculties in a bad order means more walking — but that is a self-contained
puzzle we can solve once, up front, for every possible set.

This split — "which places" is the real decision, "in what order" is a
precomputation — is what turns a scary problem into an easy one.

---

## 4. Step one: how long does each possible tour take?

There are 12 places in total (9 faculties + 3 extra buildings), so there are
`2^12 = 4096` possible sets of places. For every one of those 4096 sets we
compute, once, the shortest possible walking time of a tour that starts at the
Aula, visits all places in the set, and returns to the Aula. Add the time spent
inside each building ("dwell time") and we know the duration of every
conceivable tour.

That 4096 is worth being precise about: it is the number of place-sets we
pre-compute a travel time for. It is not the number of plans — we come back to
that in section 8.

Finding the shortest route through a set of points is the classic travelling-
salesman puzzle. For a handful of stops you could try all orders by hand; we use
a standard technique (Held–Karp) that does it exactly and fast for all 4096 sets
at once. "Exactly" is the important word: no shortcuts, no guessing.

> Example: the set {ME, EWI, IO} might take 41 minutes as
> `Aula -> ME -> EWI -> IO -> Aula` and 47 minutes in a worse order. We keep 41.

After this step, "duration" is just a number we can look up for any set.

---

## 5. Step two: score every possible tour

A tour is a set of faculties together with a choice of extra buildings. Now we
give each candidate a score built from things we can measure without knowing the
students yet:

- Faculty pairings (dependencies). Each faculty has a natural partner, a second-
  best partner, and a related extra building (for example AE pairs strongly with
  ME, less strongly with CITG, and with the "X" sports building). A tour that
  contains a faculty and its partner earns a bonus. This is what makes tours feel
  coherent instead of random. Its weight is "beta".
- Under-visited bonus. You can hand some faculties an extra weight (the "Bonus"
  column in the app) to encourage the plan to include them — useful if a faculty
  was skipped last week. Its weight is "gamma".
- Duration penalty. Longer tours lose points, gently, with weight "lam". A
  90-minute tour beats a 110-minute one unless the extra 20 minutes buy enough of
  the good stuff above. This is the "shorter is better, but not at all costs"
  rule.

A hard time ceiling ("Max tour duration", the variable "t_max") simply throws
away any set that is too long to be a real tour; the gentle penalty does the
fine-tuning below that ceiling.

### One extra building per tour

By default each tour includes exactly one extra building ("X", "DreamHall" or
"Library") — never zero, never two. For each set of faculties the tool simply
picks the single best extra: the one whose pairing bonus, minus its walking and
dwell cost, is highest. This is decided before the main optimization and then
fixed, so it does not enlarge the search. It is exact because an extra building
affects only two things — the pairing bonus (it is the "related extra building"
above) and the duration — and nothing else (students don't rank extras, and
extras don't touch the under-visited bonus or the balance). So the best extra
for a faculty set can be chosen on its own, independently of which tour it
becomes or who is assigned to it.

If you prefer, the checkbox "Exactly one extra building per tour" can be turned
off; the tool then chooses any number of extras (none, one, two or all three),
again optimally and by the same argument.

---

## 6. Step three: match students to tours

Only now do the students enter. For a given tour and a student, we score the
match by their preferences: a big reward if their first choice is on the tour,
less for their second, less again for their third, nothing if none are. The
rewards are "3, 2, 1" by default (the "rho" weights, adjustable under
"Advanced"). The overall weight on student happiness is "alpha".

Two tricks keep this fast:

- Group identical students. Many students submit the same three choices in the
  same order. We treat each distinct triple once and remember how many students
  have it, then decide how many of each type go on each tour rather than tracking
  individuals.
- Throw away dominated tours. If some faculty set A is contained in a bigger set
  B, and B scores at least as well on the tour score from section 5, then B
  satisfies every student at least as well as A — so A can never be the better
  choice and we delete it. This safely removes most candidates before the hard
  work starts.

---

## 7. Step four: balance the groups

Left alone, the optimizer might pile 60 students onto the single most attractive
tour. We don't want a 60-person procession, so we add a balance penalty that
grows the further the group sizes drift from equal (from "number of students"
divided by "Number of tours"). It is a soft rule: the plan may still tilt the
groups a little if that clearly makes students much happier, but it won't produce
a lopsided split for no reason. How hard it pushes is the "mu" slider ("Equal
group sizes").

---

## 8. Putting it together: one honest optimization

Everything above becomes a single objective the computer maximizes:

```
   total score  =   alpha * (student happiness)
                  +  beta * (faculty pairings)
                  + gamma * (under-visited bonus)
                  -   lam * (total tour time)
                  -    mu * (group imbalance)
```

Each of the five ingredients is first rescaled to sit between 0 and 1, so the
five weights ("alpha", "beta", "gamma", "lam", "mu") are directly comparable —
doubling "alpha" really does make student happiness twice as important as before.

### How big is the real search space?

This is where the factor of "K" (the "Number of tours") comes in. Section 4's
4096 was only the menu of possible individual place-sets, used to look up
durations. After the size limits, the time ceiling and the dominance step, a few
hundred of those survive as genuine candidate tours (about 115 in the bundled
example). A plan then picks "K" of those candidates — one per tour — and assigns
the students. Choosing the tours alone is already on the order of
`(candidates)^K`, e.g. `115^3` ≈ 1.5 million combinations, and on top of that
come astronomically many ways to split the students. That, not 4096, is the
space we are really searching.

Because that space is far too large to check by hand, we hand the objective and
the rules to a solver (a mixed-integer linear program, solved by HiGHS, which is
built into scipy). Crucially it returns a proof of optimality: not "a good plan"
but "the best possible plan for these weights", typically in under a minute.

---

## 9. Why you can trust the output

Because the method is exact end to end, we can check it independently, and
`verify.py` does exactly that (see the README). The most reassuring check is the
brute-force one: for each tour it actually tries every visiting order and
confirms the tour time we used is the true minimum. If any shortcut were wrong,
this would catch it.

---

## 10. About the travel times

The walking times between all buildings (and to and from the Aula) are measured
values supplied by the tour office, stored in `travel_times.csv` and baked into
`campus_data.py`. Real walking times need not obey the "a detour is never
shorter" rule, and these don't in a few spots; the method does not require it,
so the numbers are used exactly as given. If a time ever changes, edit
`travel_times.csv` and load it (see the README) — nothing else changes.

---

## 11. Where each piece lives in the code

| Concept in this document                    | In the code (`model.py` unless noted) |
|---------------------------------------------|----------------------------------------|
| Programmes, faculties, travel times, pairings | `campus_data.py` |
| Map programmes to faculties, merge duplicates | `campus_data.py`, `build_choice_matrix()` |
| Shortest tour time for every set (section 4)  | `shortest_tours()` |
| Recover the actual visiting order             | `recover_order()` |
| Score every candidate, pick best extras (5)   | `build_candidates()` |
| Throw away dominated tours (6)                | `build_candidates()`, "pass 3" |
| Group identical students (6)                  | `aggregate_types()` |
| The full optimization (7 and 8)               | `solve()` |
| Independent correctness checks (9)            | `verify.py` |

If you want the precise mathematics (the exact objective, the linear
constraints, the normalization constants), each function's docstring states it.
This document is the map; the docstrings are the territory.
