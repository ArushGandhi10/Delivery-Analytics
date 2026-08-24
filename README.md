# Multi-Work Bundling Intelligence

A geospatial + predictive prototype exploring how order bundling could work in a
last-mile delivery marketplace.

---

## Running it

```bash
pip install streamlit pydeck plotly h3 xgboost scikit-learn torch pandas numpy
streamlit run app.py
```

The CSVs are already generated, so the app runs immediately. To rebuild from
scratch, run the pipeline in order:

```bash
python generate_data.py       # synthetic orders, shoppers, stores
python geo_benchmark.py       # H3 vs BallTree spatial method comparison
python bundle_scoring.py      # route scoring for candidate pairs
python acceptance_model.py    # shopper acceptance simulation + models
python policy_simulation.py   # fleet-level matching and impact
```

---

## The pipeline in one paragraph

Orders are paired when their pickup points are within 500m and they enter the
dispatch queue within 45 minutes of each other. Each candidate pair is scored by
comparing the best bundled route (respecting store-before-customer precedence)
against running both orders solo, where the solo baseline correctly charges for
the shopper's second approach trip to a store. Pairs that save >18% distance and
fit inside both promised windows are *viable*. Viable pairs are then offered to a
shopper, whose accept/decline decision is modelled separately — because bundled
offers pay ~82% of two solo offers, acceptance is the real bottleneck. Finally,
bundles are matched greedily under a one-bundle-per-order constraint.

---

## Headline numbers (single simulated day, 6,000 orders)

| Metric | Value |
|---|---|
| Orders bundled | 51.9% |
| Bundles formed | 1,557 |
| Distance saved | 12,816 km |
| Driver-hours saved | 427 |
| Vehicle cost avoided | ~$5,383 |

---

## Findings worth talking through

**1. The binding constraint is behavioural, not geometric.**
Most candidate pairs are geometrically bundleable. The funnel collapses at
shopper acceptance. Any bundling initiative that optimises routing without
modelling acceptance will overstate its own impact substantially.

**2. Density and value pull in opposite directions.**
San Francisco bundles 64% of orders but saves only ~5.6 km each. Los Angeles
bundles 30% but saves ~12 km each. A single national bundling target would
misread both markets — the right target is metro-specific.

**3. H3 resolution should adapt to local density.**
At resolution 8, H3 precision collapsed to 0.35 in San Francisco (dense stores
fall inside one or two hexagons, so nearly every pair looks adjacent). Moving to
resolution 9 restored precision to 0.79 and ran 5× faster, at real cost to
recall. Fixed-resolution indexing is the wrong default nationally.

**4. A neural net was tested and rejected on evidence.**
PyTorch landed within 0.006 AUC of logistic regression while training ~100×
slower. Expected result on tabular features at this scale. Logistic regression is
the recommendation: same accuracy, interpretable coefficients, trivial to serve.

**5. Scoring before optimising saves most of the compute.**
At a 0.9 acceptance-score threshold, only ~1.8% of candidate pairs need full
route optimisation, and 88.7% of those are accepted. Route optimisation cannot
run on every pair in real time; a cheap classifier makes the triage viable.

**6. The pay discount is not the highest-value lever.**
Expected value per offer is flat between roughly 70% and 82% of solo pay, then
declines. Acceptance responds far more to *which pairs go to which shopper* than
to shaving points off the offer.

---

## Stated limitations

- **Synthetic data.** Orders, shopper behaviour, and acceptance are simulated
  from plausible distributions. Magnitudes are illustrative; the pipeline and the
  method comparisons are the transferable part.
- **Simulation, not causal inference.** Fleet impact is a greedy-matching upper
  bound on one simulated day. A real readout needs a switchback or geo-holdout
  design, because bundling changes shopper supply and contaminates naive
  treatment/control splits.
- **Simplifications.** Straight-line distance stands in for road-network routing;
  bundles are pairs rather than larger batches; shopper location pings are not
  used, so offers are not matched to a shopper's actual position.

---

## Stack

`h3` · `scikit-learn` (BallTree, LogisticRegression, RandomForest) · `xgboost` ·
`pytorch` · `pandas` / `numpy` · `streamlit` · `pydeck` · `plotly`
