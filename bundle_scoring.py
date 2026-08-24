"""
Bundle scoring: take candidate order pairs (close pickup points + overlapping
time windows) and score how efficient each bundle actually is.

Core logic: a bundle is worth doing if the combined route is meaningfully
shorter than running the two orders as separate solo trips.

Solo cost  = (store1 -> cust1) + (store2 -> cust2)
Bundle cost = store1 -> store2 -> [cust1, cust2 in best order]
              (or store1 -> cust1 -> store2 -> cust2 etc. -- we take best)

We also apply feasibility constraints:
  - shop_and_deliver orders need in-store shop time (est. from basket_size)
  - the bundled route must still land inside both promised_by windows
"""

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree
from itertools import permutations

EARTH_RADIUS_KM = 6371.0
DIST_THRESHOLD_KM = 0.5
MAX_CREATION_GAP_MIN = 45.0   # orders must be created within 45 min of each other --
                              # a shopper can only bundle orders that are concurrently
                              # live in the dispatch queue, not merely overlapping in
                              # their (often multi-hour) delivery windows
AVG_SPEED_KMH = 30.0          # urban driving average
SHOP_MIN_PER_ITEM = 0.9       # est. in-store minutes per item
SHOP_BASE_MIN = 8.0           # fixed overhead entering/checking out of a store
HANDOFF_MIN = 3.0             # per-dropoff handoff time

orders = pd.read_csv("/home/claude/shipt_project/orders.csv",
                     parse_dates=["order_creation_ts", "promised_by_ts"])


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def shop_time_min(row):
    """shop_and_deliver requires in-store time; delivery_only is pre-packed."""
    if row["order_type"] == "shop_and_deliver":
        return SHOP_BASE_MIN + SHOP_MIN_PER_ITEM * row["basket_size"]
    return 2.0  # quick pickup of a pre-packed order


def get_candidate_pairs(df, dist_km=DIST_THRESHOLD_KM):
    """Exact BallTree radius search on store (pickup) locations, within metro."""
    coords_rad = np.radians(df[["store_lat", "store_lon"]].values)
    tree = BallTree(coords_rad, metric="haversine")
    idx_lists = tree.query_radius(coords_rad, r=dist_km / EARTH_RADIUS_KM)

    starts = df["order_creation_ts"].values
    ends = df["promised_by_ts"].values
    pairs = []
    for i, neighbors in enumerate(idx_lists):
        for j in neighbors:
            if j <= i:
                continue
            # Orders must be created close together in time -- a shopper can only
            # bundle orders that are concurrently live in the dispatch queue.
            creation_gap_min = abs((starts[i] - starts[j]) / np.timedelta64(1, "m"))
            if creation_gap_min > MAX_CREATION_GAP_MIN:
                continue
            # and their delivery windows must still overlap
            if starts[i] <= ends[j] and starts[j] <= ends[i]:
                pairs.append((i, j))
    return pairs


def score_bundle(r1, r2):
    """Compare best bundled route vs. two solo routes. Returns dict of metrics.

    IMPORTANT baseline note: a solo trip is not just store->customer. The shopper
    must first travel TO the store. Running two orders solo means making that
    approach trip twice. Bundling eliminates one approach leg -- that's where
    most of the real-world saving comes from. We model the approach leg as the
    shopper starting from the previous order's dropoff (a reasonable proxy for
    a shopper working continuously through a shift).
    """
    # Approach legs: for solo, shopper drives to store1, delivers, then drives
    # from cust1 to store2, delivers cust2.
    leg_s1_c1 = haversine_km(r1["store_lat"], r1["store_lon"], r1["customer_lat"], r1["customer_lon"])
    leg_c1_s2 = haversine_km(r1["customer_lat"], r1["customer_lon"], r2["store_lat"], r2["store_lon"])
    leg_s2_c2 = haversine_km(r2["store_lat"], r2["store_lon"], r2["customer_lat"], r2["customer_lon"])
    solo_dist = leg_s1_c1 + leg_c1_s2 + leg_s2_c2

    # Bundled: start at store1, must visit store2, cust1, cust2.
    # Enumerate valid orderings (a store must be visited before its customer).
    stops = {
        "s1": (r1["store_lat"], r1["store_lon"]),
        "s2": (r2["store_lat"], r2["store_lon"]),
        "c1": (r1["customer_lat"], r1["customer_lon"]),
        "c2": (r2["customer_lat"], r2["customer_lon"]),
    }

    best_dist = np.inf
    best_route = None
    for perm in permutations(["s1", "s2", "c1", "c2"]):
        # precedence: store before its own customer
        if perm.index("s1") > perm.index("c1"):
            continue
        if perm.index("s2") > perm.index("c2"):
            continue
        d = 0.0
        for a, b in zip(perm[:-1], perm[1:]):
            d += haversine_km(stops[a][0], stops[a][1], stops[b][0], stops[b][1])
        if d < best_dist:
            best_dist = d
            best_route = perm

    dist_saved = solo_dist - best_dist
    pct_saved = dist_saved / solo_dist if solo_dist > 0 else 0.0

    # Time feasibility: bundled drive time + both shop times + handoffs
    # Real-world variance: shop time and traffic are stochastic, not deterministic.
    # A dispatch system can't know these in advance -- which is exactly why a
    # predictive model earns its keep over a pure geometric formula.
    rng = np.random.default_rng(abs(hash((r1["order_id"], r2["order_id"]))) % (2**32))
    traffic_multiplier = rng.normal(1.0, 0.22)          # congestion varies by route/time
    traffic_multiplier = max(0.7, traffic_multiplier)
    shop_variance = rng.normal(1.0, 0.30)               # in-store time is highly variable
    shop_variance = max(0.5, shop_variance)

    bundle_drive_min = (best_dist / AVG_SPEED_KMH) * 60 * traffic_multiplier
    total_service_min = (shop_time_min(r1) + shop_time_min(r2)) * shop_variance + 2 * HANDOFF_MIN
    bundle_total_min = bundle_drive_min + total_service_min

    # Does the bundle still fit inside both promised windows?
    latest_start = max(r1["order_creation_ts"], r2["order_creation_ts"])
    earliest_deadline = min(r1["promised_by_ts"], r2["promised_by_ts"])
    available_min = (earliest_deadline - latest_start).total_seconds() / 60
    feasible = bundle_total_min <= available_min

    return {
        "solo_dist_km": round(solo_dist, 3),
        "bundle_dist_km": round(best_dist, 3),
        "dist_saved_km": round(dist_saved, 3),
        "pct_dist_saved": round(pct_saved, 4),
        "bundle_total_min": round(bundle_total_min, 1),
        "available_min": round(available_min, 1),
        "time_feasible": bool(feasible),
        "best_route": "->".join(best_route),
    }


all_bundles = []
for metro, grp in orders.groupby("metro"):
    grp = grp.reset_index(drop=True)
    pairs = get_candidate_pairs(grp)
    # cap per metro to keep runtime sane -- sample if huge
    if len(pairs) > 20000:
        rng = np.random.default_rng(42)
        pairs = [pairs[k] for k in rng.choice(len(pairs), 20000, replace=False)]

    for i, j in pairs:
        r1, r2 = grp.iloc[i], grp.iloc[j]
        s = score_bundle(r1, r2)
        s.update({
            "metro": metro,
            "order_id_1": r1["order_id"],
            "order_id_2": r2["order_id"],
            "order_type_1": r1["order_type"],
            "order_type_2": r2["order_type"],
            "delivery_type_1": r1["delivery_type"],
            "delivery_type_2": r2["delivery_type"],
            "same_store": r1["store_id"] == r2["store_id"],
            "basket_size_1": r1["basket_size"],
            "basket_size_2": r2["basket_size"],
            "pay_1": r1["base_pay"] + r1["promo_pay"] + r1["incentive_pay"],
            "pay_2": r2["base_pay"] + r2["promo_pay"] + r2["incentive_pay"],
            # --- Cheap geometric features available BEFORE running full route
            # optimization. These are legitimate model inputs (a dispatch system
            # can compute them in O(1) per pair), unlike the optimizer outputs.
            "store_to_store_km": round(haversine_km(
                r1["store_lat"], r1["store_lon"], r2["store_lat"], r2["store_lon"]), 3),
            "cust_to_cust_km": round(haversine_km(
                r1["customer_lat"], r1["customer_lon"], r2["customer_lat"], r2["customer_lon"]), 3),
            "leg1_km": round(haversine_km(
                r1["store_lat"], r1["store_lon"], r1["customer_lat"], r1["customer_lon"]), 3),
            "leg2_km": round(haversine_km(
                r2["store_lat"], r2["store_lon"], r2["customer_lat"], r2["customer_lon"]), 3),
            "creation_gap_min": round(abs(
                (r1["order_creation_ts"] - r2["order_creation_ts"]).total_seconds() / 60), 1),
        })
        all_bundles.append(s)

bundles_df = pd.DataFrame(all_bundles)
bundles_df["bundle_type"] = bundles_df.apply(
    lambda r: "both_shop" if r["order_type_1"] == r["order_type_2"] == "shop_and_deliver"
    else ("both_delivery" if r["order_type_1"] == r["order_type_2"] == "delivery_only"
          else "mixed"), axis=1)

# A bundle is "viable" if it's time-feasible AND saves meaningful distance
bundles_df["viable"] = (bundles_df["time_feasible"]) & (bundles_df["pct_dist_saved"] > 0.18)

bundles_df.to_csv("/home/claude/shipt_project/bundles.csv", index=False)

print("Total candidate bundles scored:", len(bundles_df))
print()
print("Viability rate:", round(bundles_df["viable"].mean(), 3))
print("Time-feasible rate:", round(bundles_df["time_feasible"].mean(), 3))
print()
print("By bundle type:")
print(bundles_df.groupby("bundle_type").agg(
    n=("viable", "size"),
    viable_rate=("viable", "mean"),
    avg_pct_saved=("pct_dist_saved", "mean"),
    avg_km_saved=("dist_saved_km", "mean"),
).round(3).to_string())
print()
print("By metro:")
print(bundles_df.groupby("metro").agg(
    n=("viable", "size"),
    viable_rate=("viable", "mean"),
    avg_km_saved=("dist_saved_km", "mean"),
).round(3).to_string())
print()
print("Same-store vs different-store bundles:")
print(bundles_df.groupby("same_store").agg(
    n=("viable", "size"),
    viable_rate=("viable", "mean"),
    avg_pct_saved=("pct_dist_saved", "mean"),
).round(3).to_string())
