# Multi-Work Bundling — Complete Technical Walkthrough

Everything in the app, why it's there, how it's computed, and where it's weak.

---

## 1. The core question the project asks

**"If Shipt combined orders onto one shopper's route, how much would it actually save — and what stops it from happening?"**

The finding: geometry is not the constraint. Shopper acceptance is. That reframing is the point of the whole project.

---

## 2. The data (synthetic — `generate_data.py`)

6,000 orders across one simulated 10-hour operating day (8am–6pm), in four real Shipt metros.

| Metro | Stores | Why that count |
|---|---|---|
| Birmingham | 22 | Smaller metro, Shipt HQ |
| Austin | 28 | Mid-size |
| San Francisco | 30 | Dense, geographically compact |
| Los Angeles | 45 | Large and sprawling |

**Per-order fields:** `order_id`, `order_creation_ts`, `promised_by_ts`, `metro`, `retailer`, `store_id`, `store_lat/lon`, `customer_id`, `customer_lat/lon`, `order_type`, `delivery_type`, `basket_size`, `total_cost`, `revenue`, `markup`, `shopper_id`, `shopper_rating`, `preferred_shopper`, `base_pay`, `promo_pay`, `incentive_pay`, `on_time_flag`.

**Two type dimensions that matter:**

- `order_type`: `shop_and_deliver` (70%) — shopper physically shops in-store; `delivery_only` (30%) — order pre-packed, shopper just collects and drops.
- `delivery_type`: `on_demand` (45%, 120-min window), `same_day` (40%, 240 min), `next_day` (15%, 1440 min).

**Pay model.** The three-component split (`base_pay` + `promo_pay` + `incentive_pay`) follows the Shipt schema structure. **The coefficients are invented**: `base_pay = 3.50 + 0.25 × basket_size + U(0,3)`, with `promo_pay` zero 75% of the time and `incentive_pay` zero 85% of the time. This produces a mean total of **$8.62** per order (range $3.82–$20.38) — plausible magnitudes, but not derived from any published Shipt figures.

Two caveats to state plainly if asked:
- These numbers are assumptions chosen to make the acceptance economics behave sensibly, not sourced constants.
- Base pay here scales with basket size, whereas in the real schema base is fixed and effort is reflected in the promo/incentive components. A closer model would move that term.

**The one externally grounded pay fact:** Shipt's effort-based algorithm applies **reduced add-ons to bundled orders** — a bundle pays less than the two solo offers it replaces. That is what the `BUNDLE_DISCOUNT = 0.82` represents, and it's the assumption the entire acceptance tension rests on.

> **If challenged:** "This is synthetic. Magnitudes are illustrative. What transfers is the pipeline and the method comparison, not the specific dollar figures."

---

## 3. Finding candidate pairs (`bundle_scoring.py`)

Two orders are a **candidate** only if all three hold:

1. **Same metro** — no cross-city bundling.
2. **Pickup points within 500m** (`DIST_THRESHOLD_KM = 0.5`), by haversine distance on store coordinates, found via `sklearn` BallTree radius search.
3. **Created within 45 minutes of each other** (`MAX_CREATION_GAP_MIN = 45`) **and** delivery windows overlap.

**Why the 45-minute rule exists:** without it, an order with a 24-hour `next_day` window "overlaps" with nearly everything, so every order had ~27 candidate partners and 93% of orders bundled — implausible. A shopper can only bundle orders that are *concurrently live in the dispatch queue*, not merely overlapping across multi-hour windows.

**Result: 24,776 candidate pairs.**

> **If challenged on the thresholds:** These are judgment calls, not derived constants. 500m and 45 min are defensible as "close enough that a shopper wouldn't consider it a detour" and "both live in the queue at once." I'd tune both against real dispatch data.

---

## 4. Scoring a bundle — the distance calculation

For each candidate pair, compare the **best bundled route** against **two solo routes**.

### Solo baseline (three legs, not two)

```
store1 → customer1   +   customer1 → store2   +   store2 → customer2
```

**The middle leg is the critical one.** A shopper doing two solo orders must *drive from the first customer to the second store*. An earlier version of this model omitted that leg, which made the solo baseline artificially cheap and produced *negative* average savings. Bundling's real value comes largely from eliminating that repositioning trip.

### Bundled route

Enumerate all orderings of the four stops (`store1`, `store2`, `customer1`, `customer2`), keep only those where each store precedes its own customer (you can't deliver before you collect), take the shortest.

### The savings

```
dist_saved  = solo_dist − bundle_dist
pct_saved   = dist_saved / solo_dist
```

**Actual numbers for bundles that formed:** avg solo route **17.58 km** → avg bundled route **9.35 km** → **8.23 km saved per bundle (≈47%)**.

> **Note:** 8.23 km is the average among *matched* bundles. Across all candidates the average saving is lower (~27%) — greedy matching deliberately picks the best ones first.

---

## 5. Time feasibility — can a shopper physically complete it?

```
bundle_total_min = drive_time + service_time

drive_time    = (bundle_dist_km / 30 kph) × 60 × traffic_multiplier
service_time  = (shop_time_1 + shop_time_2) × shop_variance + 2 × 3 min handoff

shop_time  = 8 + 0.9 × basket_size   (shop_and_deliver)
           = 2                       (delivery_only, pre-packed)

traffic_multiplier ~ N(1.0, 0.22), floored at 0.7
shop_variance      ~ N(1.0, 0.30), floored at 0.5
```

**Why the randomness:** in-store time and traffic are genuinely variable and *unknowable in advance*. A deterministic model would make feasibility a pure formula — nothing for a predictive model to learn.

```
available_min = min(both promised_by) − max(both order_creation)
time_feasible = bundle_total_min ≤ available_min
```

**96.3% of candidates are time-feasible.** Time is rarely the binding constraint once pairs are already proximate.

---

## 6. "Geometric viability" — precise definition

```
viable = time_feasible  AND  pct_dist_saved > 0.18
```

Both conditions. The 18% floor exists because a bundle saving 3% isn't worth the operational complexity, the added failure risk, or a worse customer experience — it must clear a real efficiency bar.

**15,733 of 24,776 candidates (63.5%) are viable.**

Component breakdown: 23,869 pass time feasibility; 16,135 clear the 18% distance bar; 15,733 clear both.

> **If challenged on 18%:** Arbitrary but conservative. Lower it and more bundles qualify at thinner margins. It's a business threshold, not a statistical one, and should be set with ops.

---

## 7. Shopper acceptance — why this is the heart of the project

### Why model it at all

Shipt shoppers are **independent contractors who choose their offers.** And per Shipt's actual effort-based pay algorithm, **bundled orders carry reduced add-ons** — a bundle pays less than the two solo offers it replaces. That's not incidental; it's *how* bundling saves money.

So there's a structural tension: **bundling saves Shipt money precisely by paying shoppers less in aggregate — which is exactly what makes them decline it.** An analysis that optimizes routing while ignoring acceptance will overstate its own impact dramatically.

**Business relevance in one line:** a bundling initiative's ROI is not `geometric_savings`. It is `geometric_savings × acceptance_rate`. Getting acceptance wrong by 2× makes the business case wrong by 2×.

### How acceptance is modeled

Offer pay: `bundle_offer_pay = (solo_pay_1 + solo_pay_2) × 0.82`

Latent utility (log-odds), then `accepted ~ Bernoulli(sigmoid(z))`:

```
z = −3.10
    + 0.140 × pay_per_hour          ← dominant driver
    + 0.220 × pay_per_km
    − 0.011 × est_minutes           ← long commitments deter
    − 0.030 × total_items           ← physical effort deters
    − 0.850 × (shopper_rating − 4.7) ← veterans are pickier
    + 0.320 × preferred_shopper
    − 0.280 × both_shop             ← two in-store shops = hard
    + 0.150 × same_store            ← one store = easy
    + N(0, 1.15)                    ← unobservable individual preference
```

**Overall acceptance: 23.7%.**

The `N(0, 1.15)` noise term represents preferences a dispatch system can never observe — a shopper's mood, their other commitments, whether they dislike that store. It's what caps achievable AUC at a realistic level.

> **The honest framing:** "I simulated acceptance with a utility model grounded in how gig workers actually evaluate offers, then trained classifiers to recover it. On real data I'd fit this to observed accept/decline logs. The structure is what I'm demonstrating — the coefficients are assumptions."

### Model comparison

| Model | AUC | Train time |
|---|---|---|
| **Logistic Regression** | **0.770** | 0.03s |
| Neural Net (PyTorch) | ~0.769 | ~3s |
| Random Forest | ~0.766 | ~5s |
| XGBoost | ~0.763 | ~0.9s |

**Top features:** `pay_per_hour` (25%), `est_minutes` (14%), then `pay_per_km`, `total_items`.

**Two defensible conclusions:**
1. **Ship logistic regression.** It matches the tree models, trains ~100× faster, and its coefficients are directly explainable to ops — which matters when you're telling someone *why* an offer was routed.
2. **The neural net was tested and rejected on evidence.** Within 0.006 AUC at ~100× the cost. Expected on tabular data at this scale — deep learning earns its keep on sequences, embeddings, unstructured input, not 20 engineered columns.

> **Why AUC ~0.77 and not higher:** because ~0.77 is what genuine behavioral uncertainty looks like. An earlier version of this pipeline predicted geometric viability instead and scored **0.9995** — which was a red flag, not a win: the features arithmetically determined the target. Switching to acceptance made it a real prediction problem.

---

## 8. Matching — why 52% and not more

Each order can join **at most one** bundle. So capturing opportunity is a **matching problem**, not a sum over pairs. Bundles are taken greedily, highest `dist_saved` first; if either order is already committed, the pair is skipped.

**Result: 1,557 bundles = 3,114 orders = 51.9% of 6,000.**

### Exact attribution of the other 48.1%

| Reason not bundled | Orders | Share |
|---|---|---|
| No candidate partner at all (nothing within 500m / 45min) | 14 | 0.2% |
| Had a candidate, none geometrically viable | 125 | 2.1% |
| **Had a viable bundle, shopper declined all of them** | **1,939** | **32.3%** |
| Had an accepted bundle, but partner was taken first (greedy matching) | 808 | 13.5% |
| **Bundled** | **3,114** | **51.9%** |

**This table is the single most important defense in the project.** It shows the loss is overwhelmingly behavioral (32.3%) and combinatorial (13.5%) — not geometric (2.3% combined). That *is* the thesis, quantified.

> **If asked "why not use optimal matching instead of greedy?":** Correct challenge. Greedy is a lower bound. Optimal maximum-weight matching (Blossom algorithm) would capture more of that 13.5%. Greedy was chosen for runtime; the gap is a known limitation, not an oversight.

---

## 9. The headline metrics

| Metric | Value | Derivation |
|---|---|---|
| Orders bundled | 51.9% | 3,114 / 6,000 |
| Bundles formed | 1,557 | greedy matching output |
| Distance saved | 12,816 km | Σ `dist_saved_km` over matched bundles |
| **Driver-hours saved** | **427** | **12,816 km ÷ 30 kph** |
| Vehicle cost avoided | $5,383 | 12,816 km × $0.42/km |

**The 427 hours specifically:** it is *driving* hours only, at a flat 30 kph urban average. It does **not** include saved in-store time or handoff time. It's a deliberately conservative figure.

> **Weakest link, be ready for it:** 30 kph is a single flat assumption across four metros, and LA traffic is not Birmingham traffic. If pushed: "Flat 30 kph is a simplification. Metro-specific or time-of-day speed profiles would materially change the hours figure — the km saved is the more robust number."

> **On $0.42/km:** an approximate vehicle operating cost (fuel + wear). Note this accrues to the *shopper* (who owns the vehicle), not directly to Shipt — worth acknowledging rather than claiming it as company savings.

---

## 10. The Overview funnel

| Stage | Count | % of start |
|---|---|---|
| Candidate pairs (proximity + timing) | 24,776 | 100% |
| Geometrically viable | 15,733 | 64% |
| Shopper accepted | 4,176 | 17% |
| Bundles formed (after matching) | 1,557 | 6% |

Note the last two stages count *different things* — 4,176 is accepted **pairs**, 1,557 is **bundles surviving the one-per-order constraint**. Worth stating explicitly rather than letting it be inferred.

---

## 11. The geospatial method comparison

Benchmark: exact BallTree (haversine) vs. approximate H3 hex-bucketing, at 1km threshold, H3 resolution 8.

| Metro | H3 recall | H3 precision |
|---|---|---|
| Austin | 0.804 | 0.804 |
| Birmingham | 0.792 | 0.792 |
| Los Angeles | 0.786 | 0.786 |
| **San Francisco** | 0.784 | **0.349** |

**The SF finding — your strongest insight.** SF's stores span only ~0.012° of latitude (roughly 5× tighter than Austin). At resolution 8, most SF stores fall inside one or two hexagons, so the same-hex-plus-neighbors net catches nearly every pair — precision collapses to 0.349.

**Resolution sensitivity test on SF:**

| Resolution | Recall | Precision | Time |
|---|---|---|---|
| 8 | 0.784 | 0.349 | 2.17s |
| 9 | 0.486 | 0.789 | 0.49s |
| 10 | ~0.49 | ~0.79 | faster |

Resolution 9 more than doubles precision and runs 5× faster, at real cost to recall.

**Conclusion:** fixed resolution is the wrong default nationally. Resolution should adapt to local store density.

**Why BallTree feeds the actual analysis:** at 6,000 orders, exact search is cheap and correct. H3's advantage appears once pair counts grow superlinearly. Using exact results downstream means the bundling numbers aren't contaminated by approximation error.

---

## 12. Pay sensitivity

Sweep the bundle discount from 100% down to 70% of two solo offers, recompute acceptance from the utility model, and compute:

```
expected_net = acceptance_rate × (pay_saved_per_bundle + km_saved × $0.42)
```

**Finding:** acceptance falls from ~30.5% at full pay to ~16.6% at a 30% discount. Expected value is roughly **flat between 70% and 82%**, then declines.

**The read:** the discount is not the highest-value lever. Acceptance responds far more to *which pairs are offered to which shopper* than to shaving points off the offer. That points investment toward better matching and targeting, not toward squeezing pay.

> This is arguably the most business-relevant output in the whole app, because it's a recommendation about where to spend effort, not just a measurement.

---

## 13. Triage — the operational efficiency argument

Full route optimization can't run on every candidate pair in real time. Score cheaply first, optimize only the top slice.

At a **0.9** predicted-acceptance threshold: only ~1.8% of candidates need full optimization, and ~88.7% of those are accepted.

That's a concrete compute-savings argument for a production dispatch system.

---

## 14. Known limitations — say these before you're asked

1. **Synthetic data.** Every distribution is an assumption. The pipeline transfers; the magnitudes don't.
2. **Simulation, not causal inference.** This is a greedy-matching upper bound on one simulated day. It answers "what's the ceiling," not "what would an experiment measure." A real readout needs a **switchback or geo-holdout design** — because bundling changes the supply of available shoppers, treatment contaminates control in a naive A/B split.
3. **Straight-line distance, not road-network routing.** Haversine underestimates real driving distance, probably non-uniformly (worse in grid cities than sprawl).
4. **Pairs only, not larger batches.** Real multi-work may bundle 3+ orders. Extending to triples is combinatorially harder and would change the numbers.
5. **Shopper location pings unused.** The schema includes 30-second GPS traces; the model matches orders to *each other*, not to where a shopper actually is. That's the most obvious production gap.
6. **Greedy matching is a lower bound.** Optimal max-weight matching would capture more of the 13.5% lost to partner contention.
7. **Acceptance coefficients are assumed, not fitted.** On real data these come from observed accept/decline logs.
8. **Flat 30 kph across all metros and hours.** Directly affects the 427-hour figure.

---

## 15. The three sentences to lead with

> "I wanted to test whether the hard part of bundling is finding compatible orders or getting shoppers to take them. It's the second — 32% of orders had a geometrically viable bundle that every shopper declined, versus 2% that had no viable bundle at all.
>
> That matters because bundling saves money *by paying less per order*, which is exactly what makes shoppers decline it. So the ROI isn't the routing savings, it's routing savings times acceptance.
>
> It's synthetic data, so treat the magnitudes as illustrative — the method and the shape of the finding are what I'd stand behind."
