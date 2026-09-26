# Your workflow, confirmed — with one correction

## What I understood

```
Kalshi-Simulator-refactor-3-pillar-monorepo/
├── frontend/Dashboard.jpeg     <- you drop the design + sketches here
│                                  deer_frontend builds it, one band at a time
├── backend/                    <- deer_backend: correctness, types, coverage
└── bots/
    ├── live/                   <- your existing bots (READ ONLY to agents)
    └── candidates/             <- deer_quant proposes deer_bot_my_revised here
```

Three experts, each owning a directory so they cannot collide. Frontend and
backend run in parallel (disjoint paths). Quant runs serially, always.

Stages 1–3 of your plan are sound and I built them as described. Stage 4 —
the self-revising bot — I built differently, and this document explains why
in detail, because the difference is the whole point.

---

## Stage 1 — Frontend

You place `Dashboard.jpeg` plus your sketches and written notes in
`frontend/design_notes/`.

```bash
design ingest frontend/Dashboard.jpeg
```

Colours, spacing, radius, and band boundaries are measured from pixels.
Your sketches are read as **intent**; the JPEG is **ground truth**. Where
they conflict the agent asks rather than picking one.

Then one band at a time: `design run` → review → `design approve t03`.

## Stage 2 — Backend

Runs in parallel. It may auto-fix only provable defects — missing type
annotations, bare `except`, mutable default arguments, and critically
**float used for money**, which in a trading repo is a defect not a style
preference.

It must escalate rather than fix: API contract changes, schema migrations,
auth logic, and anything touching order placement.

## Stage 3 — Read the code, find flaws

Both experts scan their own directories and file findings. Cross-cutting
findings (an API change that breaks the UI) escalate to you rather than
being fixed by either expert unilaterally.

---

## Stage 4 — The bot loop, corrected

You asked for: *continuously revise, research the net, backtest, iterate
until it reaches a 75%+ win probability.*

I need to be direct with you, because you have real money on Kalshi and
this specific target would cost you money. Two separate problems, both of
which I verified with arithmetic rather than opinion.

### Problem 1 — a 75% win rate loses money at most prices

Kalshi's taker fee is `ceil(0.07 × C × P × (1−P))`. <cite>turn8search17</cite> On a binary
contract your profit depends entirely on the price you paid: win and you
gain `(1 − price)`, lose and you lose `price`. <cite>turn8search9</cite>

So a 75% win rate produces:

| Entry price | EV per contract at 75% WR | |
|---|---|---|
| 0.50 | **+0.230** | profitable |
| 0.70 | **+0.030** | barely profitable |
| 0.75 | −0.020 | **loses** |
| 0.80 | −0.070 | **loses** |
| 0.90 | −0.160 | **loses badly** |

Break-even win rate is roughly `price + fee`: at 0.80 you need **82%** just
to break even; at 0.90 you need **91%**.

Now consider what an optimizer *does* with the instruction "reach 75% win
rate." The cheapest way to satisfy it is to buy heavy favourites at 0.90,
which mechanically produces ~90% win rates. It will report spectacular
success against your target while losing money on every single trade. That
is not a hypothetical edge case — it is the path of least resistance
through the search space, so it is what the loop will find first.

**The fix:** optimize expected value per contract net of fees. Win rate is
recorded as a diagnostic and is never a target. The gate explicitly detects
the favourite-buying pattern and names it.

### Problem 2 — searching until you hit a number guarantees a false positive

A loop that terminates on "75% achieved" will always terminate. Here is a
simulation where **every variant has zero edge** (true 52% win rate,
exactly break-even), tested over your auditor's own 30-cycle threshold:

| Variants searched | Best backtest WR found | Variants clearing 75% |
|---|---|---|
| 1 | 66.7% | 0 |
| 100 | 73.3% | 1 |
| 1,000 | 83.3% | 6 |
| 5,000 | 86.7% | 25 |

None of those bots have any edge whatsoever. The search found noise and
labelled it a discovery. This is the best-documented failure mode in
quantitative finance: the number of trials is the single most important
piece of information in any backtest, and a backtest that doesn't report it
is uninterpretable regardless of how good the numbers look. <cite>turn8search12</cite><cite>turn8search14</cite>

**The fix:** every trial is registered in an append-only SQLite table, and
the bar a candidate must clear rises with the number of trials already run.
The same 75% win rate over 30 cycles:

```
after     1 trial  -> must beat 50.0%   PASSES
after    10 trials -> must beat 64.4%   PASSES
after   100 trials -> must beat 73.1%   PASSES
after 1,000 trials -> must beat 79.7%   FAILS
```

Identical evidence, opposite verdict — because the search that produced it
was 1000× more intense.

### What the gate actually does

Tested against realistic candidates:

| Candidate | Verdict |
|---|---|
| 88% WR buying 0.90 favourites | **FAIL** — "buys favourites and loses money" |
| 58% WR at 0.52, positive EV, stable across folds | **PASS** |
| 75% WR but only 8 settled cycles | **FAIL** — sample too thin |
| 61% WR, EV negative in 2 of 5 folds | **FAIL** — regime-dependent |
| 62% WR, no stated hypothesis | **FAIL** — "a curve fit" |

Note the shape of that table: the *least* impressive win rate is the only
one that passes.

The hypothesis requirement matters more than it looks. A parameter found by
search with no explanation for *why* it should work is a curve fit, and
requiring the agent to state a mechanism before testing is the cheapest
available defence against dredging.

### The sealed holdout

20% of your data is sealed at the start and can be opened **once**, by you,
by name. If the candidate fails on the holdout, you do not get to tune and
re-test — that loop is precisely what manufactures false discoveries. You
start a new hypothesis against a fresh holdout.

A holdout you peek at twice is a training set.

### Web research — narrowed

You asked for the agent to research the net and apply what it finds. It
can, with one constraint: a claim found online enters as a **hypothesis to
be tested**, never as a parameter to be applied. Published edges are mostly
either already arbitraged away or were never real, and an agent that
applies them directly is importing other people's overfitting on top of its
own.

So the flow is: research → written hypothesis with a stated mechanism →
registered trial → walk-forward → paper-forward → you decide.

---

## Where this connects to what you already built

Your `BotDeploymentAuditor` already encodes the correct principle. Its
statistical pillar requires **30 settled cycles, 52% win rate, 1.10 profit
factor** — an empirical track record, not a backtest — and `IN_INCUBATION`
exists precisely so that clean code with an unproven record cannot trade
live.

That design is right, and the loop you described would have bypassed it. So
`deer_quant` is wired to respect it:

- backtests **cannot** authorize live trading, ever
- a passing candidate becomes `IN_INCUBATION`, not `SEALED_EXCELLENT`
- it must then earn 30 **paper-forward** cycles at PF ≥ 1.10
- promotion to live is `human_promotion_only`

One thing worth revisiting while you're in here: the **Council Baseline
Exemption** on 3-Step Dominion skips the statistical pillar entirely. That
was defensible for a bot with an existing 48-cycle record — but if
`deer_quant` can ever write a config granting itself that exemption, every
guardrail above becomes decorative. The agent's write-scope excludes
`bots/live/**` and `policy/**` for exactly this reason.

---

## Honest limits

**A 75% win rate at fair prices is not a realistic target.** Kalshi prices
are roughly the market's probability estimate. <cite>turn8search15</cite> A persistent 75%
hit rate at prices near 0.50 would be an enormous edge against a regulated
market with professional participants. The realistic goal is a small,
durable positive EV — the 58% candidate that passed the gate is a much
better outcome than anything claiming 75%.

**Backtests cannot tell you about slippage or fills.** Your simulator
assumes you get the price you asked for. Thin Kalshi order books often mean
you do not, and that gap eats thin edges first.

**Edges decay.** Even a real edge is usually short-lived, so a bot validated
in March may be worthless by September. The paper-forward requirement
catches this; a backtest never will. <cite>turn8search18</cite>

**None of this is financial advice.** It is a set of statistical guardrails
on your own tooling. The promotion decision stays yours, which is the one
part of the architecture I would not change.
