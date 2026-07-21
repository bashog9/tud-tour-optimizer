# System walkthrough — why it works

A complete, self-contained account of the model and the reasoning behind every
step, meant for someone who wants to fully understand (and defend) the tool.
It is more rigorous than "HOW_IT_WORKS.md" but still reads top to bottom.

Names in quotes such as "alpha" or "Max tour duration" refer to a concrete
variable or slider. Formulas are written in plain notation; the code puts the
same formulas in each function's docstring.

Contents:
1. The problem, stated precisely
2. The modelling idea that makes it tractable
3. Step A — exact tour durations (Held–Karp)
4. Step B — candidate tours and the extra building
5. Step C — students, types, and satisfaction
6. The objective and its normalization
7. The optimization and why it is provably optimal
8. Four correctness arguments in full
9. What the tool assumes, and where it can be wrong
10. A tiny worked example

---

## 1. The problem, stated precisely

We are given:

- A set of 9 faculties and 3 extra buildings (12 "places" in total), plus a
  fixed depot, the Aula. Between every pair of places we know a walking time in
  minutes; these times are stored in a measured matrix.
- About 100 students. Each student submitted three bachelor programmes in order
  of preference. Programmes are translated to faculties (a tour visits a faculty
  building, not a programme), and duplicate faculties inside one student's list
  are merged, keeping the best rank.
- A number of tours "K" to build (for example 3).

We must decide two things at once:

1. The design: which places each of the K tours visits. Each tour is a walking
   loop that starts and ends at the Aula.
2. The assignment: which single tour each student joins. Every student is
   assigned to exactly one tour.

A plan is good if students end up on a tour that contains the faculties they
asked for, if faculties that belong together travel together, if tours are not
too long, and if the K groups are roughly equal in size. Sections 5–6 turn each
of those wishes into a measurable term; section 6 combines them.

The two decisions are coupled: the design determines what a student can possibly
get, and the assignment determines who actually gets it. Solving them separately
(design first, then assign) is not guaranteed to be optimal, so we solve them
jointly.

---

## 2. The modelling idea that makes it tractable

The objective does not depend on the order in which a tour visits its places —
only on which places are in the tour. (A student who wanted EWI is equally happy
whether EWI is visited second or fifth; a faculty pairing is present or not
regardless of order.) Order matters for exactly one quantity: the walking time
of the loop.

This single observation splits the problem cleanly:

- "Which places" is a combinatorial choice over subsets. A tour is fully
  described by a subset of the 12 places.
- "In what order" is a shortest-loop question we can answer once, in advance,
  for every subset — because there are only 2^12 = 4096 subsets.

So we precompute the exact duration of every possible subset (Step A), then
treat each subset as an atomic "candidate tour" with a known duration, and let
the optimizer choose K of them and assign the students (Steps B, C and the
optimization). Nothing in this chain is heuristic.

---

## 3. Step A — exact tour durations (Held–Karp)

For a subset S of places, the tour duration is

    d(S) = (dwell time inside each place in S)
         + (shortest closed walk Aula -> ... -> Aula visiting exactly S).

The dwell times are fixed inputs ("Time spent per faculty" and "per extra
building"). The second term is a travelling-salesman loop with a fixed start and
end at the depot. We compute it exactly for all subsets at once with the
Held–Karp dynamic program:

    dp[{j}][j]      = dist(Aula, j)                        (start leg)
    dp[S][j]        = min over i in S\{j} of dp[S\{j}][i] + dist(i, j)
    d_walk(S)       = min over j in S of dp[S][j] + dist(j, Aula)   (closing leg)

dp[S][j] is the shortest walk that starts at the Aula, visits exactly the places
in S, and ends at place j. The recurrence is exhaustive over "which place is
visited last", so it explores every ordering implicitly; there is no
approximation. Complexity is on the order of 2^12 · 12^2, which is instant.

Two consequences worth stating:
- d({j}) = 2 · dist(Aula, j): visiting a single place means walking there and
  back.
- The walking times are measured and need not satisfy the triangle inequality
  (a detour can be faster than the direct edge because of stairs or buildings).
  Held–Karp does not assume metricity, so this is fine; the duration it returns
  is still the true minimum over orderings.

The function `recover_order` re-runs the same DP with parent pointers to read
back one optimal visiting order, which is what the app displays as
"Aula -> ... -> Aula".

---

## 4. Step B — candidate tours and the extra building

Not every subset is a sensible tour. We keep a subset as a candidate only if the
number of faculties is within "Faculties per tour (min–max)" and its duration is
within "Max tour duration" ("t_max"). This produces a menu of candidate tours.

The extra buildings ("X", "DreamHall", "Library") are handled separately from the
faculties, and this is a deliberate, exact simplification.

Observation: an extra building influences only two of the five objective terms —
the dependency bonus (an extra building is the "related building" of some
faculties) and the duration. It does not influence student satisfaction
(students do not rank extra buildings), the under-visited bonus (that is defined
over faculties), or the balance (that is about student counts). Moreover, the
extra buildings chosen for one tour do not affect any other tour or the
assignment.

Therefore, for a fixed faculty set F, the best extra building can be chosen on
its own, without reference to anything else in the problem:

    e*(F) = argmax over admissible e of [ beta·DEP(F ∪ e) − lam·DUR(F ∪ e) ]

(both terms in their normalized form; see section 6). By default the tool
requires exactly one extra building per tour ("Exactly one extra building per
tour" is on), so e ranges over the three singletons; a faculty set whose cheapest
single-extra completion still exceeds "t_max" cannot form a valid tour and is
dropped. If the option is off, e ranges over all subsets of the three extras
(including none), and the same argument gives the best subset.

Because this choice is exact and local, we make it once per faculty set before
the optimization. This is what "it disappears from the optimization step" means:
the optimizer never sees the extra-building decision; it only sees completed
candidate tours, each already carrying its best extra building, its duration, and
its dependency bonus.

Finally we apply dominance pruning: a candidate whose faculty set is a subset of
another candidate's faculty set with an equal-or-better tour value can be dropped
(argument in section 8). This shrinks the menu substantially — in the bundled
example from a few hundred to around a hundred — with no effect on the optimum.

---

## 5. Step C — students, types, and satisfaction

A student's satisfaction with a tour is a rank-weighted count of their honored
choices. With rank weights "rho" = (3, 2, 1) by default, a student earns 3 if
their first-choice faculty is on their tour, 2 for their second, 1 for their
third, and these add up (so all three honored gives 6). If none of the three are
present, they earn 0.

Two reductions keep the model small without changing the optimum.

Type aggregation. Many students submit the identical ranked triple. We group
them into "types" and keep only the count of each type. The satisfaction and the
balance depend on the assignment only through how many students of each type go
to each tour, never through their identities, so we can use integer count
variables n[t,k] (students of type t assigned to tour k) instead of one binary
per student. This turns ~100 individual assignments into a handful of counts per
type.

Satisfaction as a linear expression. For type t, rank r (with faculty f), and
tour k we introduce a variable g[t,r,k] with

    0 ≤ g ≤ n[t,k]                  (can't honor more students than are there)
    0 ≤ g ≤ count(t) · z[k,f]       (can't honor anyone unless f is on tour k)

where z[k,f] is 1 if faculty f is on tour k and 0 otherwise (itself pinned by the
chosen candidate). The objective rewards g with a positive coefficient, so at the
optimum g takes the largest value both constraints allow:

    g = n[t,k]   if f is on tour k   (because n[t,k] ≤ count(t)),
    g = 0        otherwise.

That is exactly "the number of type-t students on tour k who see faculty f".
Summed over ranks and tours and weighted by "rho", it reconstructs the true
rank-weighted satisfaction — as a set of linear constraints, which is what the
solver needs. (Section 8 proves the "g lands on the right value" step.)

---

## 6. The objective and its normalization

The plan is scored by five terms. Writing S_1..S_K for the chosen tours, n_k for
the number of students on tour k, and n for the total number of students:

    SAT   = ( sum over students of their rank-weighted honored choices )
            / ( n · (rho_1 + rho_2 + rho_3) )

    DEP   = ( sum over tours of the dependency bonus of the tour )
            / ( K · max dependency bonus achievable by one tour )

    UNDER = ( sum over tours of the under-visited bonus of the tour )
            / ( K · max under-visited bonus achievable by one tour )

    DUR   = ( sum over tours of the tour duration )
            / ( K · t_max )

    BAL   = ( sum over tours of | K·n_k − n | )
            / ( 2 · n · (K − 1) )

Each numerator is divided by the largest value it could take, so every term is a
pure number between 0 and 1: SAT = 1 would mean every student got all three
choices; DUR = 1 would mean every tour ran exactly to the time ceiling; BAL = 0
means perfectly equal groups, BAL = 1 the most lopsided split possible.

The plan maximizes

    alpha·SAT + beta·DEP + gamma·UNDER − lam·DUR − mu·BAL.

Because the five terms live on the same 0–1 scale, the weights are directly
comparable and behave like exchange rates: doubling "alpha" makes a unit of
satisfaction worth twice as much relative to everything else. Only the ratios of
the weights matter, not their absolute size — multiplying all five weights by the
same constant gives the identical optimal plan. Section 9 of "HOW_IT_WORKS.md"
and the user guide translate this into everyday language for operators.

The dependency bonus of a tour is a weighted count of satisfied pairings: for
each faculty in the tour, "w1" if its first-degree partner is also in the tour,
"w2" for its second-degree partner, "w3" for its designated extra building. The
under-visited bonus of a tour is the sum of the per-faculty bonuses "b" (the
"Bonus" column) over the faculties in the tour.

---

## 7. The optimization and why it is provably optimal

Collecting the pieces, the tool solves a mixed-integer linear program (MILP):

Decision variables:
- y[k,c] ∈ {0,1}: tour k uses candidate c. Exactly one candidate per tour.
- z[k,f] ∈ {0,1}: faculty f is on tour k. Pinned by an equality to the y's, so it
  is determined once the candidate is chosen.
- n[t,k] ∈ integers ≥ 0: how many students of type t go to tour k. For each type
  these sum to the type's count (every student assigned).
- g[t,r,k] ≥ 0: honored-satisfaction counts from section 5.
- dev_k ≥ 0: the balance deviation, with dev_k ≥ K·n_k − n and dev_k ≥ n − K·n_k.

Objective: the normalized weighted sum from section 6, written entirely in these
variables. Every constraint and the objective are linear, and the only variables
forced to be integer are y and n.

The solver is HiGHS (bundled inside scipy as "scipy.optimize.milp"). It uses
branch-and-bound with linear-programming relaxations. In plain terms it keeps two
numbers: the best complete plan found so far (a lower bound on the achievable
score, since we maximize) and a bound on the best score any unexplored plan could
still reach (from the LP relaxation). It keeps branching until these two numbers
meet. When they coincide (up to "mip_rel_gap"), the best plan found is proven
optimal: no other plan, among the astronomically many, can score higher. That is
the meaning of the "proven optimal" badge in the app.

Note the scale of what is being searched. The 4096 subsets from section 3 are
only the durations lookup. After filtering, a few hundred candidate tours remain;
a plan chooses K of them and splits the students, so the number of possible plans
is on the order of (candidates)^K times the number of ways to divide the
students — far beyond hand-checking. The MILP navigates that space with a proof,
typically in well under a minute.

---

## 8. Four correctness arguments in full

These are the claims that make "provably optimal" honest. Each is also checked
empirically by "verify.py".

Argument 1 — Held–Karp returns the true minimum duration. dp[S][j] is defined as
the minimum over all orderings of S that end at j; the recurrence covers every
possible last-before-j place, so by induction on |S| it equals that minimum. The
closing step adds the return leg to the Aula and minimizes over the endpoint, so
d(S) is the exact shortest closed tour. "verify.py" confirms this independently by
brute-forcing all orderings of each chosen tour and matching the number.

Argument 2 — choosing the extra building per faculty set is exact. Fix a faculty
set F used on some tour. The extra building enters the objective only through
that tour's DEP and DUR terms, which are added to the objective with fixed
coefficients and do not appear in any other tour's terms, in the satisfaction, in
the under-visited term, or in the balance. Hence, holding the rest of the plan
fixed, the contribution of the extra choice is exactly beta·DEP(F∪e) −
lam·DUR(F∪e) (normalized), which is maximized by e*(F) independent of everything
else. Since this holds for whatever the rest of the plan is, precomputing e*(F)
loses nothing.

Argument 3 — dominance pruning is safe. Suppose faculty set F is a strict subset
of F', and the tour value val(F') ≥ val(F), where val = beta·DEP + gamma·UNDER −
lam·DUR (normalized, each on its completed candidate). Take any feasible plan that
uses F on some tour slot and replace F by F' on that slot, leaving the assignment
and all other tours unchanged. The candidate-value term does not decrease
(val(F') ≥ val(F)). Every student on that slot keeps all the faculties they had
(F' contains all of F's faculties), so no student's satisfaction decreases. The
balance is unchanged (student counts per slot are untouched). Hence the objective
does not decrease, and F' is feasible, so an optimum exists that does not use F.
Therefore F can be removed. "verify.py" additionally solves the model with pruning
switched off and checks the optimum is identical.

Argument 4 — type aggregation and the satisfaction linearization are exact. The
satisfaction and balance depend on the assignment only through the counts n[t,k],
so replacing per-student binaries by per-type integer counts describes the same
set of achievable objective values. For the linearization: g[t,r,k] is bounded by
n[t,k] and by count(t)·z[k,f], and enters the maximized objective with a positive
coefficient, so at any optimum it equals the smaller bound. If z[k,f] = 1 that
smaller bound is n[t,k] (since n[t,k] ≤ count(t)); if z[k,f] = 0 it is 0. Either
way g equals the true number of honored type-t students at rank r on tour k, so
the summed term is exactly the rank-weighted satisfaction. (g need not be declared
integer: at the optimum it already equals an integer quantity.)

Together these four say: the durations are exact, the extras and the pruning
throw nothing away, and the compact student model reproduces the true objective.
Nothing between the input and the "proven optimal" plan is approximate.

---

## 9. What the tool assumes, and where it can be wrong

Being exact about the model does not make the model reality. The honest caveats:

- Travel times are measured inputs. If a number is wrong, the plan is optimal for
  the wrong data. They live in one editable file ("travel_times.csv").
- Weights are a policy choice, not a fact. The tool finds the best plan for the
  weights you set; it cannot tell you which weights are "right". Different weights
  give different optimal plans, all equally provably optimal for their own
  weights.
- Maximizing total satisfaction can leave a few students with none of their
  choices honored, especially with skewed demand. The tool reports these students
  explicitly rather than hiding them; it does not (currently) add a fairness term
  that actively avoids them.
- Balance is a soft penalty, not a hard cap. Under strong demand skew the groups
  can still tilt if that clearly raises satisfaction; "mu" controls the trade-off.
- Requiring exactly one extra building per tour excludes faculty sets whose
  cheapest single-extra completion exceeds "t_max". That is the intended
  consequence of the rule, but it can quietly remove otherwise-good short tours
  when the time ceiling is tight; raising "Max tour duration" brings them back.
- The programme-to-faculty mapping is a fixed table; a new or renamed programme
  must be added to it, or its choices are ignored (and reported).

---

## 10. A tiny worked example

Take K = 2 tours, three students, and pretend there are only four faculties
A, B, C, D with rank weights (3, 2, 1) and, for simplicity, no dependency,
under-visited, duration or balance terms (alpha = 1, the rest 0).

Students:
- S1: A, B, C
- S2: A, C, D
- S3: B, D, A

Suppose the two candidate tours under consideration are {A, C} and {B, D}.

Assign S1 and S2 to {A, C}, S3 to {B, D}:
- S1 sees A (rank 1 -> 3) and C (rank 3 -> 1): 4.
- S2 sees A (rank 1 -> 3) and C (rank 2 -> 2): 5.
- S3 sees B (rank 1 -> 3) and D (rank 2 -> 2): 5.
Total = 14, out of a maximum 3·6 = 18, so SAT = 14/18 ≈ 0.78.

Any other assignment of these three students to these two tours scores lower
(for instance putting S3 on {A, C} gives S3 only A at rank 3 -> 1). The MILP does
this comparison for all candidate tours and all assignments simultaneously and
returns the combination with the highest SAT — here, the one above — with a proof
that nothing scores higher. Scale this from 4 faculties and 3 students to 12
places and 100 students, add the other four objective terms, and that is exactly
what the tool is doing.
