"""
Policy impact simulation: what happens at fleet level if Shipt enables
multi-work bundling vs. dispatching every order solo?

Method: greedy maximum matching on viable bundle candidates, ranked by
distance saved. Each order can appear in at most ONE bundle (a shopper can't
double-commit an order), which is the key constraint that makes this a
matching problem rather than a simple sum over pairs.

We report:
  - % of orders that get bundled
  - total distance saved (km)
  - driver-hours saved
  - shopper pay implications (bundled orders pay less per order, per Shipt's
    effort-based model, but shoppers complete more orders per hour)

IMPORTANT CAVEAT (stated in the app too): this is a SIMULATION on synthetic
data with a greedy matcher, not a causal estimate from a real experiment.
It answers "what is the theoretical ceiling", not "what would an A/B test show".
"""

import numpy as np
import pandas as pd

AVG_SPEED_KMH = 30.0
IRS_COST_PER_KM = 0.42   # approx vehicle operating cost per km (fuel+wear)

bundles = pd.read_csv("/home/claude/shipt_project/bundles.csv")
orders = pd.read_csv("/home/claude/shipt_project/orders.csv")
offers = pd.read_csv("/home/claude/shipt_project/offers.csv")

# Merge acceptance outcomes onto bundles -- a bundle only happens if a shopper
# actually accepts the offer. This is the key realism step: geometric feasibility
# is necessary but NOT sufficient.
accept_lookup = offers.set_index(["order_id_1", "order_id_2"])["accepted"].to_dict()
bundles["accepted"] = bundles.apply(
    lambda r: accept_lookup.get((r["order_id_1"], r["order_id_2"]), 0), axis=1)

# persist the merged version so downstream consumers (the app) have acceptance
bundles.to_csv("/home/claude/shipt_project/bundles.csv", index=False)

results_by_metro = []
matched_pairs_all = []

for metro, grp in bundles.groupby("metro"):
    metro_orders = orders[orders["metro"] == metro]
    total_orders = len(metro_orders)

    # A bundle only forms if it is viable AND the shopper accepted the offer
    viable = grp[(grp["viable"]) & (grp["accepted"] == 1)].sort_values("dist_saved_km", ascending=False)

    # greedy matching: take highest-saving bundles first, skip if either
    # order is already committed to another bundle
    used = set()
    matched = []
    for _, row in viable.iterrows():
        o1, o2 = row["order_id_1"], row["order_id_2"]
        if o1 in used or o2 in used:
            continue
        used.add(o1)
        used.add(o2)
        matched.append(row)

    matched_df = pd.DataFrame(matched)
    n_bundles = len(matched_df)
    orders_bundled = n_bundles * 2

    total_km_saved = matched_df["dist_saved_km"].sum() if n_bundles else 0.0
    hours_saved = total_km_saved / AVG_SPEED_KMH
    vehicle_cost_saved = total_km_saved * IRS_COST_PER_KM

    results_by_metro.append({
        "metro": metro,
        "total_orders": total_orders,
        "bundles_formed": n_bundles,
        "orders_bundled": orders_bundled,
        "pct_orders_bundled": round(orders_bundled / total_orders, 4),
        "total_km_saved": round(total_km_saved, 1),
        "driver_hours_saved": round(hours_saved, 1),
        "vehicle_cost_saved_usd": round(vehicle_cost_saved, 2),
        "avg_km_saved_per_bundle": round(total_km_saved / n_bundles, 2) if n_bundles else 0,
    })

    if n_bundles:
        matched_df["metro"] = metro
        matched_pairs_all.append(matched_df)

impact_df = pd.DataFrame(results_by_metro)
impact_df.to_csv("/home/claude/shipt_project/policy_impact.csv", index=False)

matched_all = pd.concat(matched_pairs_all, ignore_index=True)
matched_all.to_csv("/home/claude/shipt_project/matched_bundles.csv", index=False)

# ---------------------------------------------------------------------------
# Fleet-wide totals + extrapolation framing
# ---------------------------------------------------------------------------
totals = {
    "total_orders": impact_df["total_orders"].sum(),
    "bundles_formed": impact_df["bundles_formed"].sum(),
    "orders_bundled": impact_df["orders_bundled"].sum(),
    "pct_orders_bundled": round(impact_df["orders_bundled"].sum() / impact_df["total_orders"].sum(), 4),
    "total_km_saved": round(impact_df["total_km_saved"].sum(), 1),
    "driver_hours_saved": round(impact_df["driver_hours_saved"].sum(), 1),
    "vehicle_cost_saved_usd": round(impact_df["vehicle_cost_saved_usd"].sum(), 2),
}

pd.DataFrame([totals]).to_csv("/home/claude/shipt_project/policy_impact_totals.csv", index=False)

print("POLICY IMPACT BY METRO")
print(impact_df.to_string(index=False))
print()
print("FLEET TOTALS (single simulated day, 6,000 orders)")
for k, v in totals.items():
    print(f"  {k}: {v}")
print()

# sensitivity: what if we only bundle the model's top-scoring candidates?
scored = pd.read_csv("/home/claude/shipt_project/scored_bundles.csv")
print("MODEL-TRIAGED SENSITIVITY (using classifier scores to pre-filter)")
for threshold in [0.5, 0.7, 0.9]:
    high_conf = scored[scored["predicted_acceptance"] >= threshold]
    actually_viable = high_conf["accepted"].sum()
    precision = actually_viable / len(high_conf) if len(high_conf) else 0
    print(f"  threshold {threshold}: {len(high_conf):>6} pairs flagged, "
          f"{precision:.1%} actually accepted, "
          f"{len(high_conf)/len(scored):.1%} of all candidates need full optimization")
