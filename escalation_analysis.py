"""
Escalation economics.

Shipt's promo pay escalates on orders that sit unaccepted -- roughly $1/hour
as the delivery window approaches. That changes the bundling calculus in a way
the static acceptance model misses:

  - Two SOLO orders escalate INDEPENDENTLY -> $2/hour combined burn
  - One BUNDLE is a single offer      -> $1/hour burn

So a bundle burns escalation at HALF the rate of the two solo orders it
replaces. Even though a bundle is less attractive (it pays less up front) and
will therefore sit longer, the solo baseline is ALSO escalating -- twice as
fast. The bundle can absorb a lot of waiting before it stops being cheaper.

This computes the break-even: how long can a bundle sit unaccepted before it
costs more than letting the two orders clear solo?
"""

import numpy as np
import pandas as pd

ESCALATION_PER_HOUR = 1.00      # promo pay added per hour unaccepted, per offer
BUNDLE_DISCOUNT = 0.82

offers = pd.read_csv("/home/claude/shipt_project/offers.csv")

df = offers.copy()
df["solo_pay_total"] = df["pay_1"] + df["pay_2"]
df["bundle_initial"] = df["solo_pay_total"] * BUNDLE_DISCOUNT
df["upfront_discount"] = df["solo_pay_total"] - df["bundle_initial"]

# Break-even: bundle_initial + 1*T_b  ==  solo_total + 2*T_s
# Solving for T_b given T_s:  T_b = upfront_discount + 2*T_s
# i.e. even at T_s = 0 (solos clear instantly), the bundle gets
# `upfront_discount` hours of free runway.
rows = []
for t_solo in [0.0, 0.25, 0.5, 1.0, 1.5, 2.0]:
    breakeven_hours = df["upfront_discount"] + 2 * t_solo
    rows.append({
        "solo_clear_hours": t_solo,
        "bundle_breakeven_hours_mean": round(breakeven_hours.mean(), 2),
        "bundle_breakeven_hours_p25": round(breakeven_hours.quantile(0.25), 2),
        "bundle_breakeven_hours_p75": round(breakeven_hours.quantile(0.75), 2),
    })
breakeven_df = pd.DataFrame(rows)
breakeven_df.to_csv("/home/claude/shipt_project/escalation_breakeven.csv", index=False)

# Cost curves over waiting time, for the average bundle
avg_solo = df["solo_pay_total"].mean()
avg_bundle_init = df["bundle_initial"].mean()
curve = []
for t in np.arange(0, 6.25, 0.25):
    curve.append({
        "hours_waiting": round(t, 2),
        "solo_cost": round(avg_solo + 2 * ESCALATION_PER_HOUR * t, 2),
        "bundle_cost": round(avg_bundle_init + 1 * ESCALATION_PER_HOUR * t, 2),
    })
curve_df = pd.DataFrame(curve)
curve_df["bundle_cheaper"] = curve_df["bundle_cost"] < curve_df["solo_cost"]
curve_df.to_csv("/home/claude/shipt_project/escalation_curve.csv", index=False)

crossover = curve_df[~curve_df["bundle_cheaper"]]
crossover_hr = crossover["hours_waiting"].min() if len(crossover) else None

summary = {
    "avg_solo_pay_total": round(avg_solo, 2),
    "avg_bundle_initial": round(avg_bundle_init, 2),
    "avg_upfront_discount": round(df["upfront_discount"].mean(), 2),
    "escalation_per_hour_solo": 2 * ESCALATION_PER_HOUR,
    "escalation_per_hour_bundle": ESCALATION_PER_HOUR,
    "breakeven_hours_if_solos_instant": round(df["upfront_discount"].mean(), 2),
    "crossover_hours_avg_bundle": crossover_hr if crossover_hr is not None else ">6",
}
pd.DataFrame([summary]).to_csv("/home/claude/shipt_project/escalation_summary.csv", index=False)

print("ESCALATION SUMMARY")
for k, v in summary.items():
    print(f"  {k}: {v}")
print()
print("BREAK-EVEN (hours a bundle can sit before costing more than solos)")
print(breakeven_df.to_string(index=False))
