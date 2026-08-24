"""
Geospatial method comparison: H3 hex-bucketing vs. exact BallTree nearest-neighbor
search, for identifying candidate order pairs that are close enough (by store
pickup location) and time-compatible to be bundled onto one shopper's route.

BallTree (haversine) = exact ground truth: which order pairs are truly within
the distance threshold.
H3 = approximate, hex-bucket based: same-hex or adjacent-hex pairs.

We benchmark H3 against the BallTree ground truth on: recall, precision, and
wall-clock compute time, at increasing dataset scale.
"""

import time
import numpy as np
import pandas as pd
import h3
from sklearn.neighbors import BallTree
from itertools import combinations

orders = pd.read_csv("/home/claude/shipt_project/orders.csv", parse_dates=["order_creation_ts", "promised_by_ts"])

DIST_THRESHOLD_KM = 1.0
H3_RESOLUTION = 8  # avg hex edge ~461m; same+neighbor ring covers roughly a 1-1.5km radius
EARTH_RADIUS_KM = 6371.0


def time_windows_overlap(start1, end1, start2, end2):
    return (start1 <= end2) & (start2 <= end1)


def ballt_ree_ground_truth(df, dist_km=DIST_THRESHOLD_KM):
    """Exact candidate pairs via BallTree haversine radius search."""
    coords_rad = np.radians(df[["store_lat", "store_lon"]].values)
    tree = BallTree(coords_rad, metric="haversine")
    radius_rad = dist_km / EARTH_RADIUS_KM
    idx_lists = tree.query_radius(coords_rad, r=radius_rad)

    pairs = set()
    order_ids = df["order_id"].values
    starts = df["order_creation_ts"].values
    ends = df["promised_by_ts"].values

    for i, neighbors in enumerate(idx_lists):
        for j in neighbors:
            if j <= i:
                continue
            if time_windows_overlap(starts[i], ends[i], starts[j], ends[j]):
                pairs.add((order_ids[i], order_ids[j]))
    return pairs


def h3_candidate_pairs(df, resolution=H3_RESOLUTION):
    """Approximate candidate pairs via H3 same-hex / adjacent-hex bucketing.
    Uses plain dict lookups (not pandas .loc) to keep the hot loop fast --
    the whole point of H3 is O(1) bucket lookups, so the implementation
    needs to actually honor that."""
    order_ids = df["order_id"].to_numpy()
    lats = df["store_lat"].to_numpy()
    lons = df["store_lon"].to_numpy()
    starts = df["order_creation_ts"].to_numpy()
    ends = df["promised_by_ts"].to_numpy()

    # plain-dict lookup table: order_id -> (start, end)
    window_lookup = {oid: (s, e) for oid, s, e in zip(order_ids, starts, ends)}

    hex_idx = [h3.latlng_to_cell(lat, lon, resolution) for lat, lon in zip(lats, lons)]

    hex_to_orders = {}
    for oid, hx in zip(order_ids, hex_idx):
        hex_to_orders.setdefault(hx, []).append(oid)

    unique_hexes = set(hex_idx)
    # precompute each hex's 1-ring neighborhood once
    neighbor_map = {hx: h3.grid_disk(hx, 1) for hx in unique_hexes}

    pairs = set()
    for hx in unique_hexes:
        candidate_orders = set()
        for nh in neighbor_map[hx]:
            candidate_orders.update(hex_to_orders.get(nh, []))
        candidate_orders = sorted(candidate_orders)

        for oid1, oid2 in combinations(candidate_orders, 2):
            pair_key = (oid1, oid2) if oid1 < oid2 else (oid2, oid1)
            if pair_key in pairs:
                continue
            s1, e1 = window_lookup[oid1]
            s2, e2 = window_lookup[oid2]
            if time_windows_overlap(s1, e1, s2, e2):
                pairs.add(pair_key)
    return pairs


# ---------------------------------------------------------------------------
# Run benchmark per metro (bundling only makes sense within a metro)
# ---------------------------------------------------------------------------
results = []
all_h3_pairs = set()
all_bt_pairs = set()

for metro, grp in orders.groupby("metro"):
    grp = grp.reset_index(drop=True)

    t0 = time.perf_counter()
    bt_pairs = ballt_ree_ground_truth(grp)
    bt_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    h3_pairs = h3_candidate_pairs(grp)
    h3_time = time.perf_counter() - t0

    true_positives = h3_pairs & bt_pairs
    recall = len(true_positives) / len(bt_pairs) if bt_pairs else 1.0
    precision = len(true_positives) / len(h3_pairs) if h3_pairs else 1.0

    results.append({
        "metro": metro,
        "n_orders": len(grp),
        "balltree_pairs_found": len(bt_pairs),
        "balltree_time_sec": round(bt_time, 4),
        "h3_pairs_found": len(h3_pairs),
        "h3_time_sec": round(h3_time, 4),
        "h3_recall_vs_balltree": round(recall, 3),
        "h3_precision_vs_balltree": round(precision, 3),
        "speedup_factor": round(bt_time / h3_time, 2) if h3_time > 0 else None,
    })

    all_h3_pairs |= {(metro, p) for p in h3_pairs}
    all_bt_pairs |= {(metro, p) for p in bt_pairs}

results_df = pd.DataFrame(results)

# ---------------------------------------------------------------------------
# SF-specific test: does a finer H3 resolution fix the precision collapse
# in a geographically dense metro?
# ---------------------------------------------------------------------------
sf = orders[orders["metro"] == "San Francisco"].reset_index(drop=True)
bt_pairs_sf = ballt_ree_ground_truth(sf)

resolution_test = []
for res in [8, 9, 10]:
    t0 = time.perf_counter()
    h3_pairs_res = h3_candidate_pairs(sf, resolution=res)
    elapsed = time.perf_counter() - t0
    tp = h3_pairs_res & bt_pairs_sf
    recall = len(tp) / len(bt_pairs_sf) if bt_pairs_sf else 1.0
    precision = len(tp) / len(h3_pairs_res) if h3_pairs_res else 1.0
    resolution_test.append({
        "resolution": res,
        "pairs_found": len(h3_pairs_res),
        "time_sec": round(elapsed, 4),
        "recall": round(recall, 3),
        "precision": round(precision, 3),
    })

resolution_df = pd.DataFrame(resolution_test)
resolution_df.to_csv("/home/claude/shipt_project/sf_resolution_test.csv", index=False)

results_df.to_csv("/home/claude/shipt_project/geo_method_benchmark.csv", index=False)

print(results_df.to_string(index=False))
print()
print("SF resolution sensitivity test:")
print(resolution_df.to_string(index=False))
print()
print("TOTAL across all metros:")
print("BallTree total pairs:", len(all_bt_pairs))
print("H3 total pairs:", len(all_h3_pairs))
print("Overall recall:", round(len(all_h3_pairs & all_bt_pairs) / len(all_bt_pairs), 3))
