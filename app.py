"""
Multi-Work Bundling Intelligence
Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np

from d3_charts import funnel_chart, bar_chart, scatter_chart, line_chart, grouped_bar
from map_component import render_hex_map
from route_map import render_route_map
from experiment_sim import run_experiment

st.set_page_config(page_title="Multi-Work Bundling Intelligence",
                   page_icon="◆", layout="wide",
                   initial_sidebar_state="collapsed")

HAITI = "#25123A"
MEADOW = "#23CC6B"
YELLOWGREEN = "#BAE581"
OFFWHITE = "#FAF9F6"
CHARCOAL = "#2B2B33"
MUTED = "#8B8894"
CORAL = "#E8593C"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
.stApp {{ background: {OFFWHITE}; }}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 1rem; max-width: 1400px; }}
h1,h2,h3 {{ font-family:'Space Grotesk',sans-serif !important; color:{HAITI} !important; }}
p,li,div,span {{ font-family:'Inter',sans-serif; color:{CHARCOAL}; }}
.hero {{ background:linear-gradient(135deg,{HAITI} 0%,#3A1D57 100%);
  border-radius:20px; padding:34px 40px; margin-bottom:24px; position:relative; overflow:hidden; }}
.hero::after {{ content:''; position:absolute; right:-60px; top:-60px; width:260px; height:260px;
  background:{MEADOW}; opacity:.13;
  clip-path:polygon(25% 0%,75% 0%,100% 50%,75% 100%,25% 100%,0% 50%); }}
.hero h1 {{ color:#fff !important; font-size:2.2rem; margin:0 0 10px; letter-spacing:-.02em; }}
.hero .sub {{ color:{YELLOWGREEN}; font-size:1rem; font-weight:500; max-width:730px; line-height:1.55; }}
.hero .eyebrow {{ color:{MEADOW}; font-family:'IBM Plex Mono',monospace; font-size:.72rem;
  letter-spacing:.16em; text-transform:uppercase; margin-bottom:12px; }}
.metric-card {{ background:#fff; border-radius:16px; padding:20px 22px;
  border:1px solid rgba(37,18,58,.07); box-shadow:0 2px 14px rgba(37,18,58,.05); height:100%; }}
.metric-card .label {{ font-family:'IBM Plex Mono',monospace; font-size:.68rem; color:{MUTED};
  letter-spacing:.11em; text-transform:uppercase; margin-bottom:8px; }}
.metric-card .value {{ font-family:'Space Grotesk',sans-serif; font-size:2rem; font-weight:700;
  color:{HAITI}; line-height:1.05; letter-spacing:-.02em; }}
.metric-card .note {{ font-size:.78rem; color:{MUTED}; margin-top:7px; line-height:1.4; }}
.metric-card.accent {{ border-left:4px solid {MEADOW}; }}
.section-head {{ font-family:'Space Grotesk',sans-serif; font-size:1.28rem; font-weight:600;
  color:{HAITI}; margin:26px 0 6px; display:flex; align-items:center; gap:10px; }}
.section-head::before {{ content:''; width:13px; height:15px; background:{MEADOW};
  clip-path:polygon(25% 0%,75% 0%,100% 50%,75% 100%,25% 100%,0% 50%); flex-shrink:0; }}
.section-sub {{ color:{MUTED}; font-size:.9rem; margin-bottom:14px; max-width:900px; line-height:1.55; }}
.callout {{ background:rgba(35,204,107,.08); border-left:3px solid {MEADOW};
  border-radius:0 10px 10px 0; padding:15px 19px; margin:15px 0; font-size:.88rem; line-height:1.6; }}
.caveat {{ background:rgba(37,18,58,.04); border-left:3px solid {MUTED};
  border-radius:0 10px 10px 0; padding:14px 18px; margin:15px 0; font-size:.83rem;
  color:{MUTED}; line-height:1.55; }}
.warn {{ background:rgba(232,89,60,.07); border-left:3px solid {CORAL};
  border-radius:0 10px 10px 0; padding:14px 18px; margin:15px 0; font-size:.85rem; line-height:1.6; }}
.stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid rgba(37,18,58,.1); }}
.stTabs [data-baseweb="tab"] {{ font-family:'Inter',sans-serif; font-weight:500; font-size:.92rem;
  color:{MUTED}; padding:11px 18px; background:transparent; }}
.stTabs [aria-selected="true"] {{ color:{HAITI} !important; border-bottom:2.5px solid {MEADOW}; }}
[data-testid="stDataFrame"] {{ border-radius:12px; overflow:hidden; }}
[data-baseweb="slider"] [role="slider"] {{ background-color:{HAITI} !important;
  border-color:{HAITI} !important; }}
[data-baseweb="slider"] div[data-testid="stTickBar"] {{ display:none; }}
[data-baseweb="slider"] > div > div > div:first-child {{ background:{MEADOW} !important; }}
.stSlider [data-baseweb="slider"] div[style*="rgb(255, 75, 75)"] {{ background:{MEADOW} !important; }}
.stButton button {{ border-radius:999px; border:1px solid {HAITI}; color:{HAITI};
  background:#fff; font-weight:500; padding:6px 20px; }}
.stButton button:hover {{ background:{HAITI}; color:#fff; border-color:{HAITI}; }}
</style>
""", unsafe_allow_html=True)

BASE = "."


@st.cache_data
def load():
    d = {
        "orders": pd.read_csv(f"{BASE}/orders.csv", parse_dates=["order_creation_ts", "promised_by_ts"]),
        "stores": pd.read_csv(f"{BASE}/stores.csv"),
        "bundles": pd.read_csv(f"{BASE}/bundles.csv"),
        "offers": pd.read_csv(f"{BASE}/offers.csv"),
        "impact": pd.read_csv(f"{BASE}/policy_impact.csv"),
        "models": pd.read_csv(f"{BASE}/model_comparison.csv"),
        "features": pd.read_csv(f"{BASE}/feature_importance.csv"),
        "geo_bench": pd.read_csv(f"{BASE}/geo_method_benchmark.csv"),
        "sf_res": pd.read_csv(f"{BASE}/sf_resolution_test.csv"),
        "paysens": pd.read_csv(f"{BASE}/pay_sensitivity.csv"),
        "scored": pd.read_csv(f"{BASE}/scored_bundles.csv"),
        "matched": pd.read_csv(f"{BASE}/matched_bundles.csv"),
        "esc_curve": pd.read_csv(f"{BASE}/escalation_curve.csv"),
        "esc_break": pd.read_csv(f"{BASE}/escalation_breakeven.csv"),
        "esc_sum": pd.read_csv(f"{BASE}/escalation_summary.csv"),
    }
    loc = d["orders"].set_index("order_id")[
        ["store_lat", "store_lon", "customer_lat", "customer_lon", "retailer"]]
    m = d["matched"].join(loc.add_suffix("_1"), on="order_id_1")
    m = m.join(loc.add_suffix("_2"), on="order_id_2")
    d["matched_geo"] = m
    return d


D = load()

st.markdown(f"""
<div class="hero">
  <div class="eyebrow">Geospatial Intelligence &nbsp;·&nbsp; Prototype</div>
  <h1>Multi-Work Bundling Intelligence</h1>
  <div class="sub">Using spatial and temporal proximity to identify which orders can be
  combined onto a single shopper route &mdash; and predicting whether a shopper
  will actually accept the bundle.</div>
</div>
""", unsafe_allow_html=True)

metros = ["All metros"] + sorted(D["orders"]["metro"].unique().tolist())
metro = st.selectbox("Metro", metros, index=0, label_visibility="collapsed")


def f(df):
    return df if metro == "All metros" else df[df["metro"] == metro]


def card(label, value, note="", accent=False):
    cls = "metric-card accent" if accent else "metric-card"
    return f"""<div class="{cls}"><div class="label">{label}</div>
    <div class="value">{value}</div><div class="note">{note}</div></div>"""


t1, t2, t3, t4, t5 = st.tabs([
    "Overview", "Geospatial Method", "Acceptance Model", "Experiment", "Fleet Impact"])

# ============================== OVERVIEW ==============================
with t1:
    o, b, imp = f(D["orders"]), f(D["bundles"]), f(D["impact"])
    tot = len(o)
    bundled = imp["orders_bundled"].sum()
    km = imp["total_km_saved"].sum()
    hrs = imp["driver_hours_saved"].sum()

    c = st.columns(4)
    c[0].markdown(card("Orders analyzed", f"{tot:,}", "Single simulated operating day"),
                  unsafe_allow_html=True)
    c[1].markdown(card("Orders bundled", f"{bundled/tot:.0%}",
                       f"{bundled:,} orders into {imp['bundles_formed'].sum():,} bundles",
                       accent=True), unsafe_allow_html=True)
    c[2].markdown(card("Distance saved", f"{km:,.0f} km", "vs. dispatching every order solo"),
                  unsafe_allow_html=True)
    c[3].markdown(card("Driver-hours saved", f"{hrs:,.0f}",
                       f"&asymp; ${imp['vehicle_cost_saved_usd'].sum():,.0f} vehicle cost"),
                  unsafe_allow_html=True)

    st.markdown('<div class="section-head">Where the opportunity is lost</div>', unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">Three stages narrow the funnel. Geometry finds what is
    <em>possible</em>; the shopper decides what is <em>acceptable</em>; matching determines what the
    fleet can <em>capture</em>.</div>""", unsafe_allow_html=True)

    cand = len(b)
    viable = int(b["viable"].sum())
    acc = int(((b["viable"]) & (b["accepted"] == 1)).sum())
    formed = int(imp["bundles_formed"].sum())

    stages = [
        {"label": "Candidate pairs", "sublabel": "spatial + temporal proximity",
         "value": cand, "drop_label": f"\u2193  \u2212{cand-viable:,} fail geometry or timing"},
        {"label": "Geometrically viable", "sublabel": "saves >18%, fits window",
         "value": viable, "drop_label": f"\u2193  \u2212{viable-acc:,} shopper declines"},
        {"label": "Shopper accepted", "sublabel": "offer economics clear",
         "value": acc, "drop_label": f"\u2193  \u2212{acc-formed:,} lost to 1-per-order matching"},
        {"label": "Bundles formed", "sublabel": "final matched pairs",
         "value": formed, "drop_label": ""},
    ]
    st.components.v1.html(funnel_chart(stages, uid="fn"), height=400, scrolling=False)

    st.markdown(f"""<div class="callout">
    <strong>The binding constraint is behavioural, not geometric.</strong>
    Only {(cand-viable)/cand:.0%} of candidate pairs fail on geometry or timing. The funnel
    collapses at shopper acceptance &mdash; because a bundled offer pays less than the two solo
    offers it replaces, so the shopper has to find the trade worthwhile.
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-head">Density and value pull in opposite directions</div>',
                unsafe_allow_html=True)
    mi = D["impact"]
    pts = [{"label": r["metro"], "x": float(r["pct_orders_bundled"]),
            "y": float(r["avg_km_saved_per_bundle"]), "size": float(r["total_km_saved"]),
            "tip": f"{r['pct_orders_bundled']:.0%} bundled &middot; {r['avg_km_saved_per_bundle']:.1f} km/bundle"}
           for _, r in mi.iterrows()]
    st.components.v1.html(scatter_chart(pts, uid="sc",
                                        xlabel="Share of orders bundled",
                                        ylabel="Avg km saved per bundle"),
                          height=410, scrolling=False)

    st.markdown("""<div class="callout">
    San Francisco bundles the highest share of orders but saves the least per bundle &mdash; trips
    are short to begin with. Los Angeles is the mirror image: sprawl makes each bundle worth
    roughly twice as much, but far fewer pairs clear the proximity bar. A single national
    bundling target would misread both markets.
    </div>""", unsafe_allow_html=True)

# ========================= GEOSPATIAL METHOD =========================
with t2:
    st.markdown('<div class="section-head">What a bundle actually looks like</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">One real matched bundle from the dataset, on a street
    map. Toggle between running the two orders separately and combining them onto a single route.
    The dashed leg is the repositioning trip a shopper makes between two solo orders &mdash;
    eliminating it is where most of the saving comes from.</div>""", unsafe_allow_html=True)

    mg = D["matched_geo"]
    mg_f = mg if metro == "All metros" else mg[mg["metro"] == metro]
    examples = mg_f.sort_values("dist_saved_km", ascending=False).head(6).reset_index(drop=True)

    if len(examples):
        opts = [f"{r['metro']}  \u00b7  saves {r['dist_saved_km']:.1f} km ({r['pct_dist_saved']:.0%})"
                for _, r in examples.iterrows()]
        pick = st.selectbox("Example bundle", opts, index=0)
        row = examples.iloc[opts.index(pick)]
        st.components.v1.html(render_route_map(row.to_dict(), uid="rt"), height=690, scrolling=False)
    else:
        st.info("No matched bundles for this metro.")

    st.markdown('<div class="section-head">Choosing a spatial matching method</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">Finding nearby order pairs is the computational core.
    Two approaches were benchmarked: exact nearest-neighbour search (BallTree, haversine) and
    approximate hex-bucketing with Uber's H3 index.</div>""", unsafe_allow_html=True)

    gb = D["geo_bench"]
    c = st.columns(3)
    c[0].markdown(card("H3 recall", f"{gb['h3_recall_vs_balltree'].mean():.1%}",
                       "Share of true nearby pairs recovered"), unsafe_allow_html=True)
    c[1].markdown(card("Exact pairs found", f"{gb['balltree_pairs_found'].sum():,}",
                       "BallTree ground truth"), unsafe_allow_html=True)
    c[2].markdown(card("Method chosen", "BallTree",
                       "Exact at this scale; H3 for production volume", accent=True),
                  unsafe_allow_html=True)

    st.dataframe(gb.rename(columns={
        "metro": "Metro", "n_orders": "Orders", "balltree_pairs_found": "BallTree pairs",
        "balltree_time_sec": "BallTree (s)", "h3_pairs_found": "H3 pairs", "h3_time_sec": "H3 (s)",
        "h3_recall_vs_balltree": "H3 recall", "h3_precision_vs_balltree": "H3 precision",
        "speedup_factor": "Speedup"}), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-head">The resolution trade-off</div>', unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">H3 precision collapsed in San Francisco at resolution 8
    &mdash; the metro is dense enough that most stores fall inside one or two hexagons, so nearly
    every pair looks like a neighbour. Resolution 9 fixes precision and runs faster, at real cost
    to recall.</div>""", unsafe_allow_html=True)

    sr = D["sf_res"]
    groups = [{"label": f"res {int(r['resolution'])}",
               "values": [float(r["recall"]), float(r["precision"])]} for _, r in sr.iterrows()]
    st.components.v1.html(grouped_bar(groups, ["Recall", "Precision"], [HAITI, MEADOW],
                                      uid="res", width=980, ylabel="Score", y_pct=True),
                          height=370, scrolling=False)

    st.markdown("""<div class="callout">
    <strong>Fixed resolution is the wrong default.</strong> One national H3 resolution
    under-performs in both directions &mdash; too coarse for dense metros like San Francisco,
    needlessly fine for sprawling ones like Austin. Resolution should adapt to local store density.
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-head">Order density &amp; bundling corridors</div>',
                unsafe_allow_html=True)
    orders_all, stores_all, mj = D["orders"], D["stores"], D["matched_geo"]
    if metro == "All metros":
        cols = st.columns(2)
        for i, m in enumerate(sorted(orders_all["metro"].unique())):
            html = render_hex_map(orders_all[orders_all["metro"] == m],
                                  stores_all[stores_all["metro"] == m],
                                  mj[mj["metro"] == m], title=m,
                                  max_width=560, max_height=400, top_corridors=10)
            with cols[i % 2]:
                st.components.v1.html(html, height=470, scrolling=False)
    else:
        html = render_hex_map(orders_all[orders_all["metro"] == metro],
                              stores_all[stores_all["metro"] == metro],
                              mj[mj["metro"] == metro], title=metro,
                              max_width=980, max_height=560, top_corridors=18)
        st.components.v1.html(html, height=630, scrolling=False)

# ========================= ACCEPTANCE MODEL =========================
with t3:
    st.markdown('<div class="section-head">Predicting shopper acceptance</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">A geometrically perfect bundle is worthless if no
    shopper takes it. Shoppers are independent contractors who choose their offers, and a bundled
    offer pays less than the two solo offers it replaces &mdash; so acceptance, not geometry, is
    the real constraint on multi-work.</div>""", unsafe_allow_html=True)

    m = D["models"]
    best = m.iloc[0]
    c = st.columns(3)
    c[0].markdown(card("Best AUC", f"{best['auc']:.3f}", str(best["model"])), unsafe_allow_html=True)
    c[1].markdown(card("Spread across models", f"{m['auc'].max()-m['auc'].min():.3f}",
                       "Logistic through gradient boosting"), unsafe_allow_html=True)
    c[2].markdown(card("Recommended", "Logistic regression",
                       "Matches tree models, ~100&times; faster, explainable coefficients",
                       accent=True), unsafe_allow_html=True)

    st.dataframe(m.rename(columns={
        "model": "Model", "auc": "AUC", "precision": "Precision", "recall": "Recall",
        "f1": "F1", "brier": "Brier", "train_time_sec": "Train (s)"}),
        use_container_width=True, hide_index=True)

    st.markdown("""<div class="callout">
    <strong>A neural network was tested and rejected on evidence.</strong> PyTorch landed within
    0.006 AUC of logistic regression while training roughly 100&times; slower. On tabular features
    at this scale that is the expected result &mdash; deep learning earns its cost on sequences,
    embeddings and unstructured input, not twenty engineered columns.
    </div>""", unsafe_allow_html=True)

    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="section-head">What drives acceptance</div>', unsafe_allow_html=True)
        fi = D["features"].head(9)
        items = [{"label": r["feature"], "value": round(float(r["importance"]), 4)}
                 for _, r in fi.iloc[::-1].iterrows()]
        st.components.v1.html(bar_chart(items, uid="fi", width=600, height=330,
                                        xlabel="Importance"), height=360, scrolling=False)
    with right:
        st.markdown('<div class="section-head">Acceptance by offer economics</div>',
                    unsafe_allow_html=True)
        off = f(D["offers"])
        off = off[off["pay_per_hour"].between(0, 80)].copy()
        off["b"] = pd.cut(off["pay_per_hour"], bins=[0, 15, 20, 25, 30, 40, 80])
        rate = off.groupby("b", observed=True)["accepted"].mean().reset_index()
        items = [{"label": f"${str(r['b'])[1:-1].replace(', ', '-')}/hr",
                  "value": round(float(r["accepted"]), 4),
                  "display": f"{r['accepted']:.0%}"} for _, r in rate.iterrows()]
        st.components.v1.html(bar_chart(items, uid="ae", width=600, height=330,
                                        color=HAITI, xlabel="Acceptance rate"),
                              height=360, scrolling=False)

    st.markdown('<div class="section-head">Triage: which pairs deserve full optimisation</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">Route optimisation cannot run on every candidate pair
    in real time. Scoring first and optimising only the top slice keeps most of the value for a
    fraction of the compute.</div>""", unsafe_allow_html=True)
    sc = D["scored"]
    rows = []
    for t in [0.3, 0.5, 0.7, 0.9]:
        hc = sc[sc["predicted_acceptance"] >= t]
        if len(hc):
            rows.append({"Score threshold": t, "Pairs flagged": len(hc),
                         "Share of candidates": f"{len(hc)/len(sc):.1%}",
                         "Actually accepted": f"{hc['accepted'].mean():.1%}"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ============================ EXPERIMENT ============================
with t4:
    st.markdown('<div class="section-head">Designing an experiment on bundle pay</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">The models show which features <em>predict</em>
    acceptance. Acting on a lever &mdash; raising pay to lift acceptance &mdash; is a causal claim,
    and prediction alone cannot support it. This is how that experiment would be designed and
    read.</div>""", unsafe_allow_html=True)

    st.markdown("""<div class="warn">
    <strong>This is a design and readout demonstration, not a causal finding.</strong>
    Outcomes are simulated from the same utility model that generated the training data, so the
    effect it recovers is the effect that was coded in &mdash; it proves nothing about real
    shoppers. What it does demonstrate is randomised assignment, sample sizing, confidence
    intervals, and the difference between an observed gap and a statistically distinguishable one.
    On real data the identical machinery reads a real test.
    </div>""", unsafe_allow_html=True)

    ec1, ec2, ec3 = st.columns(3)
    ctrl_d = ec1.slider("Control discount", 0.70, 1.00, 0.82, 0.01,
                        help="Bundle pays this share of the two solo offers combined")
    trt_d = ec2.slider("Treatment discount", 0.70, 1.00, 0.90, 0.01)
    n_size = ec3.select_slider("Sample size", [100, 250, 500, 1000, 2500, 5000, 10000], 1000)

    if "exp_seed" not in st.session_state:
        st.session_state["exp_seed"] = 42
    if st.button("Re-randomise"):
        st.session_state["exp_seed"] = int(np.random.default_rng().integers(0, 10 ** 6))
    seed = st.session_state["exp_seed"]

    res = run_experiment(D["offers"], ctrl_d, trt_d, n_size, seed=seed)

    r1 = st.columns(4)
    r1[0].markdown(card("Control", f"{res['control_rate']:.1%}",
                        f"n = {res['n_control']:,} &middot; {ctrl_d:.0%} of solo pay"),
                   unsafe_allow_html=True)
    r1[1].markdown(card("Treatment", f"{res['treatment_rate']:.1%}",
                        f"n = {res['n_treatment']:,} &middot; {trt_d:.0%} of solo pay"),
                   unsafe_allow_html=True)
    r1[2].markdown(card("Observed lift", f"{res['lift']*100:+.1f} pp",
                        f"95% CI [{res['ci_low']*100:+.1f}, {res['ci_high']*100:+.1f}] pp",
                        accent=True), unsafe_allow_html=True)
    verdict = "Significant" if res["significant"] else "Not significant"
    r1[3].markdown(card("Verdict", verdict, f"p = {res['p_value']:.4f}"), unsafe_allow_html=True)

    if res["significant"]:
        st.markdown(f"""<div class="callout">
        The confidence interval excludes zero, so the difference is unlikely to be noise at this
        sample size. Cost of the change: about
        <strong>${abs(res['extra_pay_per_bundle']):.2f} extra pay per bundle</strong>.
        Whether that is worth {res['lift']*100:+.1f} points of acceptance is a margin question,
        not a statistical one.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="warn">
        The 95% confidence interval spans zero, so this test cannot distinguish the effect from
        noise. Note this does <em>not</em> mean there is no effect &mdash; only that this sample is
        too small to resolve it. Increase the sample size and watch the interval tighten.
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-head">Why sample size decides what you can see</div>',
                unsafe_allow_html=True)
    sizes = [100, 250, 500, 1000, 2500, 5000, 10000]
    pts_lift, pts_lo, pts_hi = [], [], []
    for s in sizes:
        r = run_experiment(D["offers"], ctrl_d, trt_d, s, seed=seed)
        pts_lift.append({"x": s, "y": r["lift"] * 100, "tip": f"lift {r['lift']*100:+.1f} pp"})
        pts_lo.append({"x": s, "y": r["ci_low"] * 100, "tip": f"CI low {r['ci_low']*100:+.1f} pp"})
        pts_hi.append({"x": s, "y": r["ci_high"] * 100, "tip": f"CI high {r['ci_high']*100:+.1f} pp"})
    series = [
        {"name": "Upper 95% bound", "color": YELLOWGREEN, "points": pts_hi},
        {"name": "Observed lift", "color": MEADOW, "points": pts_lift},
        {"name": "Lower 95% bound", "color": HAITI, "points": pts_lo},
    ]
    st.components.v1.html(line_chart(series, uid="pw", width=980, height=340,
                                     xlabel="Sample size", ylabel="Lift (percentage points)"),
                          height=380, scrolling=False)

    st.markdown("""<div class="callout">
    At small samples the bounds are wide enough to contain zero, so the test is uninformative no
    matter what the point estimate says &mdash; and the point estimate itself swings around. As the
    sample grows the interval narrows toward the true effect. This is why an underpowered test is
    worse than no test: it produces a number that looks like an answer.
    </div>""", unsafe_allow_html=True)

    st.markdown("""<div class="caveat">
    <strong>What a real version of this needs.</strong> Randomising individual offers leaks:
    bundling changes how many shoppers remain available, so treatment contaminates control through
    the shared supply pool. A real readout needs a <strong>switchback</strong> design (alternating
    the policy on and off across time windows in a market) or a <strong>geo-holdout</strong> (whole
    metros assigned to each arm), so interference happens between periods or markets rather than
    within them.
    </div>""", unsafe_allow_html=True)

# =========================== FLEET IMPACT ===========================
with t5:
    st.markdown('<div class="section-head">If bundling were enabled fleet-wide</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">Each order can join at most one bundle, so capturing
    the opportunity is a matching problem, not a sum over pairs. Bundles are matched greedily,
    highest distance saving first, among pairs both viable and accepted.</div>""",
                unsafe_allow_html=True)

    imp = f(D["impact"])
    c = st.columns(4)
    c[0].markdown(card("Bundles formed", f"{imp['bundles_formed'].sum():,}"), unsafe_allow_html=True)
    c[1].markdown(card("Distance saved", f"{imp['total_km_saved'].sum():,.0f} km", accent=True),
                  unsafe_allow_html=True)
    c[2].markdown(card("Driver-hours saved", f"{imp['driver_hours_saved'].sum():,.0f}",
                       "At a flat 30 kph urban average"), unsafe_allow_html=True)
    c[3].markdown(card("Vehicle cost avoided", f"${imp['vehicle_cost_saved_usd'].sum():,.0f}",
                       "At $0.42/km operating cost"), unsafe_allow_html=True)

    mi = D["impact"]
    items = [{"label": r["metro"], "value": float(r["total_km_saved"]),
              "display": f"{r['total_km_saved']:,.0f} km \u00b7 {r['pct_orders_bundled']:.0%} bundled"}
             for _, r in mi.sort_values("total_km_saved").iterrows()]
    st.components.v1.html(bar_chart(items, uid="fi2", width=980, height=280,
                                    xlabel="Kilometres saved"), height=310, scrolling=False)

    st.markdown('<div class="section-head">Escalating pay changes the comparison</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="section-sub">Promo pay rises on orders that sit unaccepted. Two solo
    orders escalate independently &mdash; roughly twice the burn rate of the single bundled offer
    that would replace them. The solo baseline is a moving target, not a fixed one.</div>""",
                unsafe_allow_html=True)

    ec = D["esc_curve"]
    es = D["esc_sum"].iloc[0]
    series = [
        {"name": "Two solo offers ($2/hr burn)", "color": CORAL,
         "points": [{"x": float(r["hours_waiting"]), "y": float(r["solo_cost"]),
                     "tip": f"${r['solo_cost']:.2f}"} for _, r in ec.iterrows()]},
        {"name": "One bundled offer ($1/hr burn)", "color": MEADOW,
         "points": [{"x": float(r["hours_waiting"]), "y": float(r["bundle_cost"]),
                     "tip": f"${r['bundle_cost']:.2f}"} for _, r in ec.iterrows()]},
    ]
    st.components.v1.html(line_chart(series, uid="esc", width=980, height=340,
                                     xlabel="Hours the offer sits unaccepted",
                                     ylabel="Total pay cost ($)"),
                          height=380, scrolling=False)

    st.markdown(f"""<div class="callout">
    <strong>A bundle gets {es['breakeven_hours_if_solos_instant']:.1f} hours of free runway.</strong>
    The upfront discount averages ${es['avg_upfront_discount']:.2f}, and the bundle burns escalation
    at half the rate of the two solo offers it replaces. Even if both solo orders cleared
    <em>instantly</em>, the bundle could sit unaccepted for
    {es['breakeven_hours_if_solos_instant']:.1f} hours before costing more. If the solos each take
    an hour to clear, that runway extends past five hours. Bundling is more robust to low acceptance
    than the {D['bundles']['accepted'].mean():.0%} raw acceptance rate suggests &mdash; because the
    baseline it is measured against is escalating faster.
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-head">Setting the bundle pay discount</div>',
                unsafe_allow_html=True)
    ps = D["paysens"]
    series = [
        {"name": "Acceptance rate (%)", "color": HAITI,
         "points": [{"x": float(r["bundle_discount"]), "y": float(r["acceptance_rate"]) * 100,
                     "tip": f"{r['acceptance_rate']:.1%}"} for _, r in ps.iterrows()]},
        {"name": "Expected net value per offer ($)", "color": MEADOW,
         "points": [{"x": float(r["bundle_discount"]),
                     "y": float(r["expected_net_value_per_offer"]),
                     "tip": f"${r['expected_net_value_per_offer']:.2f}"} for _, r in ps.iterrows()]},
    ]
    st.components.v1.html(line_chart(series, uid="psen", width=980, height=340,
                                     xlabel="Bundle pay as share of two solo offers",
                                     ylabel="Rate (%) / value ($)", x_pct=True),
                          height=380, scrolling=False)

    st.markdown("""<div class="callout">
    Expected value is roughly flat between 70% and 82%, then falls away. Below that band the extra
    margin per bundle no longer compensates for the bundles that stop forming. The practical read:
    the discount is not the lever worth tuning hardest &mdash; acceptance responds far more to which
    pairs are offered to which shopper.
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-head">What this prototype does not do</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="caveat">
    <strong>Synthetic data.</strong> Orders, shopper behaviour and acceptance are simulated from
    plausible distributions, not production. Magnitudes are illustrative; the pipeline and the
    method comparisons are the transferable part.<br><br>
    <strong>Simulation, not causal inference.</strong> Fleet impact is a greedy-matching upper bound
    on one simulated day. It answers what the ceiling is, not what an experiment would measure.<br><br>
    <strong>Simplifications.</strong> Straight-line distance stands in for road-network routing; a
    uniform circuity correction cancels out of every percentage here, but differential circuity on
    multi-stop routes would not. Bundles are pairs rather than larger batches. Shopper location pings
    are unused, so offers are not matched to where a shopper actually is. Greedy matching is a lower
    bound &mdash; optimal max-weight matching would capture more.<br><br>
    <strong>Assumed parameters.</strong> The 500 m radius, 45-minute dispatch window, 18% savings
    floor, 0.82 pay discount and $1/hour escalation are judgment calls, not fitted constants. Each
    would be calibrated against real dispatch data.
    </div>""", unsafe_allow_html=True)
