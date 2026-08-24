"""
Synthetic Shipt-style order + shopper dataset for the geospatial bundling project.
Fields modeled after real Shipt schema (order-level + shopper-level), as recalled
by the candidate from their time on the People Analytics / Enterprise Data team.

Metros confirmed as real Shipt coverage areas: Birmingham AL (HQ), San Francisco,
Los Angeles, Austin.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

# ---------------------------------------------------------------------------
# Metro centers (approx downtown lat/long) + rough spread radius in degrees
# ---------------------------------------------------------------------------
METROS = {
    "Birmingham": {"lat": 33.5186, "lon": -86.8104, "spread": 0.09},
    "San Francisco": {"lat": 37.7749, "lon": -122.4194, "spread": 0.06},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437, "spread": 0.15},
    "Austin": {"lat": 30.2672, "lon": -97.7431, "spread": 0.10},
}

RETAILERS = ["Target", "CVS", "Publix", "Kroger", "Petco", "Meijer", "Lowe's", "Walgreens"]

# Each metro gets a fixed set of "stores" (retailer locations) that orders are placed from.
# This matters for bundling logic -- multiple shop_and_deliver orders from the SAME store
# are the easiest bundling case.
# Store counts reflect rough real-world density: LA is huge and sprawling, Birmingham
# is a smaller metro. Real Shipt metros have dozens of partner store locations.
STORES_PER_METRO = {
    "Birmingham": 22,
    "San Francisco": 30,
    "Los Angeles": 45,
    "Austin": 28,
}
stores = []
store_id = 0
for metro, info in METROS.items():
    for _ in range(STORES_PER_METRO[metro]):
        store_id += 1
        stores.append({
            "store_id": f"S{store_id}",
            "metro": metro,
            "retailer": np.random.choice(RETAILERS),
            "store_lat": info["lat"] + np.random.uniform(-info["spread"], info["spread"]),
            "store_lon": info["lon"] + np.random.uniform(-info["spread"], info["spread"]),
        })
stores_df = pd.DataFrame(stores)

# ---------------------------------------------------------------------------
# Shoppers
# ---------------------------------------------------------------------------
N_SHOPPERS_PER_METRO = 25
shoppers = []
shopper_id = 0
for metro in METROS:
    for _ in range(N_SHOPPERS_PER_METRO):
        shopper_id += 1
        shoppers.append({
            "shopper_id": f"SH{shopper_id}",
            "metro": metro,
            "shopper_rating": round(np.clip(np.random.normal(4.7, 0.25), 3.5, 5.0), 2),
            "preferred_shopper": np.random.choice([0, 1], p=[0.75, 0.25]),
        })
shoppers_df = pd.DataFrame(shoppers)

# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
N_ORDERS = 6000
DELIVERY_TYPE_WINDOWS_MIN = {
    "on_demand": 120,      # within 2 hours
    "same_day": 240,       # customer-chosen slot, more relaxed than on_demand
    "next_day": 1440,      # next day
}
DELIVERY_TYPE_PROB = {"on_demand": 0.45, "same_day": 0.40, "next_day": 0.15}

# order_type: shop_and_deliver (Marketplace-style, shopper shops in-store)
# vs delivery_only (Platform/Dedicated-style, order pre-packed, shopper just delivers)
ORDER_TYPE_PROB = {"shop_and_deliver": 0.70, "delivery_only": 0.30}

BASE_DATE = datetime(2026, 8, 10, 8, 0, 0)  # simulate a single business day, 8am start

orders = []
for i in range(1, N_ORDERS + 1):
    metro = np.random.choice(list(METROS.keys()))
    metro_info = METROS[metro]
    metro_stores = stores_df[stores_df["metro"] == metro]
    store = metro_stores.sample(1).iloc[0]

    order_type = np.random.choice(list(ORDER_TYPE_PROB.keys()), p=list(ORDER_TYPE_PROB.values()))
    delivery_type = np.random.choice(list(DELIVERY_TYPE_WINDOWS_MIN.keys()), p=list(DELIVERY_TYPE_PROB.values()))
    window_min = DELIVERY_TYPE_WINDOWS_MIN[delivery_type]

    # order created at a random minute across a 10-hour window (8am - 6pm)
    creation_offset_min = np.random.uniform(0, 600)
    order_creation_ts = BASE_DATE + timedelta(minutes=creation_offset_min)
    promised_by_ts = order_creation_ts + timedelta(minutes=window_min)

    # customer location: scattered around the metro, biased near the store for realism
    customer_lat = store["store_lat"] + np.random.normal(0, metro_info["spread"] * 0.5)
    customer_lon = store["store_lon"] + np.random.normal(0, metro_info["spread"] * 0.5)

    basket_size = max(1, int(np.random.gamma(shape=3, scale=4)))
    total_cost = round(basket_size * np.random.uniform(4, 15), 2)
    revenue = round(total_cost * np.random.uniform(0.08, 0.15), 2)   # Shipt's cut, illustrative
    markup = round(total_cost * np.random.uniform(0.03, 0.07), 2)

    # base pay reflecting real Shipt effort-based model: distance + item count + complexity
    base_pay = round(3.5 + basket_size * 0.25 + np.random.uniform(0, 3), 2)
    promo_pay = round(np.random.choice([0, 0, 0, 1, 2, 3, 5], p=[0.5, 0.15, 0.1, 0.1, 0.08, 0.05, 0.02]), 2)
    incentive_pay = round(np.random.choice([0, 0, 1, 2], p=[0.7, 0.15, 0.1, 0.05]), 2)

    shopper = shoppers_df[shoppers_df["metro"] == metro].sample(1).iloc[0]

    # on-time flag: more likely late if on_demand + large basket (more realistic risk pattern)
    late_risk = 0.08 + (0.10 if delivery_type == "on_demand" else 0) + (0.01 * max(0, basket_size - 10))
    on_time_flag = np.random.choice([1, 0], p=[1 - min(late_risk, 0.6), min(late_risk, 0.6)])

    orders.append({
        "order_id": f"O{i}",
        "order_creation_ts": order_creation_ts,
        "promised_by_ts": promised_by_ts,
        "metro": metro,
        "retailer": store["retailer"],
        "store_id": store["store_id"],
        "store_lat": store["store_lat"],
        "store_lon": store["store_lon"],
        "customer_id": f"C{np.random.randint(1, N_ORDERS // 2)}",
        "customer_lat": customer_lat,
        "customer_lon": customer_lon,
        "order_type": order_type,
        "delivery_type": delivery_type,
        "on_time_flag": on_time_flag,
        "basket_size": basket_size,
        "total_cost": total_cost,
        "revenue": revenue,
        "markup": markup,
        "shopper_id": shopper["shopper_id"],
        "shopper_rating": shopper["shopper_rating"],
        "preferred_shopper": shopper["preferred_shopper"],
        "base_pay": base_pay,
        "promo_pay": promo_pay,
        "incentive_pay": incentive_pay,
    })

orders_df = pd.DataFrame(orders)
orders_df["total_shopper_pay"] = orders_df["base_pay"] + orders_df["promo_pay"] + orders_df["incentive_pay"]

orders_df.to_csv("/home/claude/shipt_project/orders.csv", index=False)
stores_df.to_csv("/home/claude/shipt_project/stores.csv", index=False)
shoppers_df.to_csv("/home/claude/shipt_project/shoppers.csv", index=False)

print("Orders:", orders_df.shape)
print(orders_df["metro"].value_counts())
print(orders_df["order_type"].value_counts(normalize=True))
print(orders_df["delivery_type"].value_counts(normalize=True))
print("On-time rate:", orders_df["on_time_flag"].mean().round(3))
print(orders_df.head(3).T)
