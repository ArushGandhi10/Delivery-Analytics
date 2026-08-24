"""
Shopper acceptance modeling.

THE REAL PROBLEM: a geometrically-efficient bundle is worthless if no shopper
accepts the offer. Shipt shoppers are independent contractors who cherry-pick
offers -- and per Shipt's effort-based pay model, bundled orders carry REDUCED
per-order add-ons vs. two solo orders. So bundling saves the fleet money
precisely by paying shoppers less in aggregate, which is exactly what makes
acceptance uncertain.

This is genuinely stochastic (individual shopper preferences are unobservable),
so a predictive model adds real value over a formula.

We simulate acceptance with a latent utility model, then train classifiers to
recover it from observable features -- and use the model to find the pay level
at which bundle acceptance becomes economical.
"""

import time
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, brier_score_loss
import xgboost as xgb

rng = np.random.default_rng(7)
bundles = pd.read_csv("/home/claude/shipt_project/bundles.csv")

# only bundles that are operationally feasible get offered to a shopper
df = bundles[bundles["time_feasible"]].reset_index(drop=True).copy()

# ---------------------------------------------------------------------------
# Bundle offer pay, per Shipt's effort-based model with the bundling discount
# ---------------------------------------------------------------------------
BUNDLE_DISCOUNT = 0.82   # bundled offer pays ~82% of the two solo offers combined
df["solo_pay_total"] = df["pay_1"] + df["pay_2"]
df["bundle_offer_pay"] = (df["solo_pay_total"] * BUNDLE_DISCOUNT).round(2)

# Economics from the shopper's point of view
df["est_minutes"] = df["bundle_total_min"]
df["pay_per_hour"] = (df["bundle_offer_pay"] / (df["est_minutes"] / 60)).round(2)
df["pay_per_km"] = (df["bundle_offer_pay"] / (df["bundle_dist_km"] + 0.1)).round(2)
df["total_items"] = df["basket_size_1"] + df["basket_size_2"]
df["items_per_dollar"] = (df["total_items"] / df["bundle_offer_pay"]).round(3)

# shopper attributes attached to the offer (whoever it's routed to)
shoppers = pd.read_csv("/home/claude/shipt_project/shoppers.csv")
shopper_map = shoppers.set_index("shopper_id")
df["assigned_shopper"] = rng.choice(shoppers["shopper_id"].values, size=len(df))
df["shopper_rating"] = df["assigned_shopper"].map(shopper_map["shopper_rating"])
df["preferred_shopper"] = df["assigned_shopper"].map(shopper_map["preferred_shopper"])

# ---------------------------------------------------------------------------
# LATENT ACCEPTANCE MODEL (the "ground truth" behavior we're trying to learn)
# Drivers of acceptance, grounded in how gig shoppers actually evaluate offers:
#   + effective hourly rate is the dominant factor
#   + shorter total time commitment is preferred
#   - heavy item counts are a deterrent (physical effort)
#   - long drives with low pay-per-km are unattractive
#   + experienced/high-rated shoppers are pickier (higher reservation wage)
#   + genuine unobserved individual preference noise
# ---------------------------------------------------------------------------
z = (
    -3.10
    + 0.140 * df["pay_per_hour"]
    - 0.011 * df["est_minutes"]
    - 0.030 * df["total_items"]
    + 0.220 * df["pay_per_km"]
    - 0.850 * (df["shopper_rating"] - 4.7)        # pickier veterans
    + 0.320 * df["preferred_shopper"]
    - 0.280 * (df["bundle_type"] == "both_shop").astype(int)   # two in-store shops = effort
    + 0.150 * df["same_store"].astype(int)                      # one store = easy
    + rng.normal(0, 1.15, len(df))                              # unobservable preference
)
p_accept = 1 / (1 + np.exp(-z))
df["accepted"] = (rng.random(len(df)) < p_accept).astype(int)

print("Simulated acceptance rate:", round(df["accepted"].mean(), 3))
print()

# ---------------------------------------------------------------------------
# Model training -- note: shopper_rating / preferred_shopper ARE observable to
# the dispatch system, but the individual preference noise is NOT, which caps
# achievable AUC at a realistic level.
# ---------------------------------------------------------------------------
df["both_shop_flag"] = (df["bundle_type"] == "both_shop").astype(int)
df["both_delivery_flag"] = (df["bundle_type"] == "both_delivery").astype(int)
df["same_store_flag"] = df["same_store"].astype(int)
df["has_on_demand"] = ((df["delivery_type_1"] == "on_demand") | (df["delivery_type_2"] == "on_demand")).astype(int)
metro_d = pd.get_dummies(df["metro"], prefix="metro").astype(int)
df = pd.concat([df, metro_d], axis=1)

FEATURES = [
    "bundle_offer_pay", "pay_per_hour", "pay_per_km", "est_minutes",
    "total_items", "items_per_dollar", "bundle_dist_km",
    "shopper_rating", "preferred_shopper",
    "both_shop_flag", "both_delivery_flag", "same_store_flag", "has_on_demand",
] + list(metro_d.columns)

X = df[FEATURES].values.astype(float)
y = df["accepted"].values

X_tr, X_te, y_tr, y_te, idx_tr, idx_te = train_test_split(
    X, y, df.index, test_size=0.25, random_state=42, stratify=y)

scaler = StandardScaler()
X_tr_s, X_te_s = scaler.fit_transform(X_tr), scaler.transform(X_te)

results = []

def evaluate(name, y_true, y_prob, t):
    y_pred = (y_prob >= 0.5).astype(int)
    results.append({
        "model": name,
        "auc": round(roc_auc_score(y_true, y_prob), 4),
        "precision": round(precision_score(y_true, y_pred), 4),
        "recall": round(recall_score(y_true, y_pred), 4),
        "f1": round(f1_score(y_true, y_pred), 4),
        "brier": round(brier_score_loss(y_true, y_prob), 4),
        "train_time_sec": round(t, 3),
    })

t0 = time.perf_counter(); lr = LogisticRegression(max_iter=1000).fit(X_tr_s, y_tr)
evaluate("Logistic Regression", y_te, lr.predict_proba(X_te_s)[:, 1], time.perf_counter() - t0)

t0 = time.perf_counter()
rf = RandomForestClassifier(n_estimators=250, max_depth=10, min_samples_leaf=20,
                            random_state=42, n_jobs=-1).fit(X_tr, y_tr)
evaluate("Random Forest", y_te, rf.predict_proba(X_te)[:, 1], time.perf_counter() - t0)

t0 = time.perf_counter()
xgb_clf = xgb.XGBClassifier(n_estimators=400, max_depth=5, learning_rate=0.05,
                            subsample=0.9, colsample_bytree=0.9, min_child_weight=5,
                            eval_metric="logloss", random_state=42, n_jobs=-1).fit(X_tr, y_tr)
evaluate("XGBoost", y_te, xgb_clf.predict_proba(X_te)[:, 1], time.perf_counter() - t0)

import torch, torch.nn as nn
torch.manual_seed(42)
Xtr_t = torch.tensor(X_tr_s, dtype=torch.float32)
ytr_t = torch.tensor(y_tr, dtype=torch.float32).unsqueeze(1)
Xte_t = torch.tensor(X_te_s, dtype=torch.float32)
net = nn.Sequential(nn.Linear(X_tr_s.shape[1], 64), nn.ReLU(), nn.Dropout(0.25),
                    nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid())
opt = torch.optim.Adam(net.parameters(), lr=1e-3); loss_fn = nn.BCELoss()
t0 = time.perf_counter()
net.train()
for _ in range(80):
    perm = torch.randperm(Xtr_t.size(0))
    for k in range(0, Xtr_t.size(0), 512):
        b = perm[k:k+512]; opt.zero_grad()
        loss_fn(net(Xtr_t[b]), ytr_t[b]).backward(); opt.step()
t_nn = time.perf_counter() - t0
net.eval()
with torch.no_grad():
    nn_prob = net(Xte_t).squeeze().numpy()
evaluate("Neural Net (PyTorch)", y_te, nn_prob, t_nn)

res_df = pd.DataFrame(results).sort_values("auc", ascending=False)
res_df.to_csv("/home/claude/shipt_project/model_comparison.csv", index=False)

imp = pd.DataFrame({"feature": FEATURES, "importance": xgb_clf.feature_importances_}) \
        .sort_values("importance", ascending=False)
imp.to_csv("/home/claude/shipt_project/feature_importance.csv", index=False)

scored = df.loc[idx_te].copy()
scored["predicted_acceptance"] = xgb_clf.predict_proba(X_te)[:, 1]
scored.to_csv("/home/claude/shipt_project/scored_bundles.csv", index=False)
df.to_csv("/home/claude/shipt_project/offers.csv", index=False)

print("MODEL COMPARISON (target: shopper accepts the bundle offer)")
print(res_df.to_string(index=False))
print()
print("TOP FEATURES")
print(imp.head(10).to_string(index=False))
print()

# ---------------------------------------------------------------------------
# PAY SENSITIVITY: what bundle discount maximizes net fleet benefit?
# Trade-off: a steeper discount saves Shipt money per bundle, but fewer
# shoppers accept, so fewer bundles actually happen.
# ---------------------------------------------------------------------------
print("PAY SENSITIVITY -- bundle discount vs. acceptance vs. net saving")
sens = []
for disc in [0.70, 0.75, 0.80, 0.82, 0.85, 0.90, 0.95, 1.00]:
    offer = df["solo_pay_total"] * disc
    pph = offer / (df["est_minutes"] / 60)
    ppk = offer / (df["bundle_dist_km"] + 0.1)
    z2 = (-3.10 + 0.140 * pph - 0.011 * df["est_minutes"] - 0.030 * df["total_items"]
          + 0.220 * ppk - 0.850 * (df["shopper_rating"] - 4.7)
          + 0.320 * df["preferred_shopper"]
          - 0.280 * df["both_shop_flag"] + 0.150 * df["same_store_flag"])
    acc_rate = (1 / (1 + np.exp(-z2))).mean()
    pay_saved_per_bundle = (df["solo_pay_total"] - offer).mean()
    dist_value_per_bundle = df["dist_saved_km"].mean() * 0.42   # vehicle cost per km
    expected_net = acc_rate * (pay_saved_per_bundle + dist_value_per_bundle)
    sens.append({
        "bundle_discount": disc,
        "acceptance_rate": round(acc_rate, 3),
        "pay_saved_per_bundle": round(pay_saved_per_bundle, 2),
        "expected_net_value_per_offer": round(expected_net, 2),
    })
sens_df = pd.DataFrame(sens)
sens_df.to_csv("/home/claude/shipt_project/pay_sensitivity.csv", index=False)
print(sens_df.to_string(index=False))
