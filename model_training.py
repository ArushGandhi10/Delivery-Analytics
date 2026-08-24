"""
Predictive layer: can we predict whether a candidate bundle will be VIABLE
(time-feasible + saves >10% distance) from order features alone -- without
running the full route optimization for every pair?

Why this matters operationally: at Shipt scale, you can't brute-force route-
optimize every candidate pair in real time. A fast classifier lets you triage
which pairs are worth the expensive optimization step.

Models compared:
  1. Logistic Regression (interpretable baseline)
  2. Random Forest
  3. XGBoost
  4. Small PyTorch neural net (to test whether deep learning adds anything
     on tabular data at this scale -- expected: it does not)
"""

import time
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
import xgboost as xgb

bundles = pd.read_csv("/home/claude/shipt_project/bundles.csv")

# ---------------------------------------------------------------------------
# Feature engineering -- deliberately EXCLUDING the route-optimization outputs
# (bundle_dist_km, dist_saved_km, pct_dist_saved, bundle_total_min) because
# those are exactly what we're trying to avoid computing. Using them would be
# target leakage.
# ---------------------------------------------------------------------------
df = bundles.copy()

df["basket_total"] = df["basket_size_1"] + df["basket_size_2"]
df["basket_diff"] = (df["basket_size_1"] - df["basket_size_2"]).abs()
df["pay_total"] = df["pay_1"] + df["pay_2"]
df["same_store_flag"] = df["same_store"].astype(int)
df["window_slack_min"] = df["available_min"]

# Geometric ratios -- cheap to compute, genuinely predictive of route efficiency.
# Intuition: if the two dropoffs are far apart relative to the individual delivery
# legs, the bundled route has to detour a lot and saves little.
df["leg_sum_km"] = df["leg1_km"] + df["leg2_km"]
df["cust_spread_ratio"] = df["cust_to_cust_km"] / (df["leg_sum_km"] + 0.01)
df["store_spread_ratio"] = df["store_to_store_km"] / (df["leg_sum_km"] + 0.01)
df["leg_imbalance"] = (df["leg1_km"] - df["leg2_km"]).abs() / (df["leg_sum_km"] + 0.01)

# categorical encodings
df["both_shop"] = (df["bundle_type"] == "both_shop").astype(int)
df["both_delivery"] = (df["bundle_type"] == "both_delivery").astype(int)
df["mixed_type"] = (df["bundle_type"] == "mixed").astype(int)

for dt in ["on_demand", "same_day", "next_day"]:
    df[f"dt1_{dt}"] = (df["delivery_type_1"] == dt).astype(int)
    df[f"dt2_{dt}"] = (df["delivery_type_2"] == dt).astype(int)

df["has_on_demand"] = ((df["delivery_type_1"] == "on_demand") | (df["delivery_type_2"] == "on_demand")).astype(int)

metro_dummies = pd.get_dummies(df["metro"], prefix="metro").astype(int)
df = pd.concat([df, metro_dummies], axis=1)

FEATURES = [
    "basket_total", "basket_diff", "pay_total", "same_store_flag",
    "window_slack_min", "both_shop", "both_delivery", "mixed_type",
    "has_on_demand", "creation_gap_min",
    # geometric features (pre-optimization, no leakage)
    "store_to_store_km", "cust_to_cust_km", "leg1_km", "leg2_km",
    "leg_sum_km", "cust_spread_ratio", "store_spread_ratio", "leg_imbalance",
    "dt1_on_demand", "dt1_same_day", "dt1_next_day",
    "dt2_on_demand", "dt2_same_day", "dt2_next_day",
] + list(metro_dummies.columns)

X = df[FEATURES].values.astype(float)
y = df["viable"].astype(int).values

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

results = []


def evaluate(name, y_true, y_prob, train_time):
    y_pred = (y_prob >= 0.5).astype(int)
    results.append({
        "model": name,
        "auc": round(roc_auc_score(y_true, y_prob), 4),
        "precision": round(precision_score(y_true, y_pred), 4),
        "recall": round(recall_score(y_true, y_pred), 4),
        "f1": round(f1_score(y_true, y_pred), 4),
        "train_time_sec": round(train_time, 3),
    })


# --- 1. Logistic Regression ---
t0 = time.perf_counter()
lr = LogisticRegression(max_iter=1000)
lr.fit(X_train_s, y_train)
t_lr = time.perf_counter() - t0
evaluate("Logistic Regression", y_test, lr.predict_proba(X_test_s)[:, 1], t_lr)

# --- 2. Random Forest ---
t0 = time.perf_counter()
rf = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
t_rf = time.perf_counter() - t0
evaluate("Random Forest", y_test, rf.predict_proba(X_test)[:, 1], t_rf)

# --- 3. XGBoost ---
t0 = time.perf_counter()
xgb_clf = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.08,
    subsample=0.9, colsample_bytree=0.9,
    eval_metric="logloss", random_state=42, n_jobs=-1)
xgb_clf.fit(X_train, y_train)
t_xgb = time.perf_counter() - t0
evaluate("XGBoost", y_test, xgb_clf.predict_proba(X_test)[:, 1], t_xgb)

# --- 4. Small PyTorch neural net ---
try:
    import torch
    import torch.nn as nn

    torch.manual_seed(42)
    Xtr = torch.tensor(X_train_s, dtype=torch.float32)
    ytr = torch.tensor(y_train, dtype=torch.float32).unsqueeze(1)
    Xte = torch.tensor(X_test_s, dtype=torch.float32)

    net = nn.Sequential(
        nn.Linear(X_train_s.shape[1], 64), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(64, 32), nn.ReLU(),
        nn.Linear(32, 1), nn.Sigmoid(),
    )
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()

    t0 = time.perf_counter()
    net.train()
    for epoch in range(60):
        perm = torch.randperm(Xtr.size(0))
        for k in range(0, Xtr.size(0), 512):
            idx = perm[k:k + 512]
            opt.zero_grad()
            loss = loss_fn(net(Xtr[idx]), ytr[idx])
            loss.backward()
            opt.step()
    t_nn = time.perf_counter() - t0

    net.eval()
    with torch.no_grad():
        nn_prob = net(Xte).squeeze().numpy()
    evaluate("Neural Net (PyTorch)", y_test, nn_prob, t_nn)
    torch_available = True
except ImportError:
    torch_available = False
    print("PyTorch not available -- skipping NN comparison")

results_df = pd.DataFrame(results).sort_values("auc", ascending=False)
results_df.to_csv("/home/claude/shipt_project/model_comparison.csv", index=False)

# Feature importance from the best tree model
importance = pd.DataFrame({
    "feature": FEATURES,
    "importance": xgb_clf.feature_importances_,
}).sort_values("importance", ascending=False)
importance.to_csv("/home/claude/shipt_project/feature_importance.csv", index=False)

# Save scored predictions for the app
df_test_idx = train_test_split(df.index, test_size=0.25, random_state=42, stratify=y)[1]
scored = df.loc[df_test_idx].copy()
scored["predicted_viability"] = xgb_clf.predict_proba(X_test)[:, 1]
scored.to_csv("/home/claude/shipt_project/scored_bundles.csv", index=False)

print("MODEL COMPARISON")
print(results_df.to_string(index=False))
print()
print("TOP 10 FEATURES (XGBoost)")
print(importance.head(10).to_string(index=False))
print()
print("Base rate (viable):", round(y.mean(), 4))
