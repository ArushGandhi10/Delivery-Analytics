"""
H3 hex density + bundling corridor map, drawn on a real Leaflet street basemap.

Colors each real H3 hexagon by order density, overlays the top bundling
corridors as animated lines, and marks stores -- all on actual streets rather
than an abstract projection.

Leaflet's JS and CSS are inlined directly from local files (via npm) rather
than loaded from a CDN at render time -- this removes the library itself as
a point of failure. The only remaining external dependency is the raster
tile *images* from CARTO, which is unavoidable for a real basemap; if those
fail to load, the hexagons/corridors/markers still render correctly on a
blank background, since they don't depend on the tile images themselves.
"""

import json
import math
import os
import h3

HAITI = "#25123A"
MEADOW = "#23CC6B"
YELLOWGREEN = "#BAE581"
MUTED = "#8B8894"

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "leaflet.js"), "r", encoding="utf-8") as _f:
    _LEAFLET_JS = _f.read()
with open(os.path.join(_DIR, "leaflet.css"), "r", encoding="utf-8") as _f:
    _LEAFLET_CSS = _f.read()

_FILL_LOW = (223, 245, 232)   # #DFF5E8
_FILL_HIGH = (35, 204, 107)   # #23CC6B (Meadow)


def _hex_color(t):
    """Interpolate between the pale and full Meadow fill for a 0-1 ratio."""
    t = max(0.0, min(1.0, t))
    r = round(_FILL_LOW[0] + (_FILL_HIGH[0] - _FILL_LOW[0]) * t)
    g = round(_FILL_LOW[1] + (_FILL_HIGH[1] - _FILL_LOW[1]) * t)
    b = round(_FILL_LOW[2] + (_FILL_HIGH[2] - _FILL_LOW[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def render_hex_map(orders_df, stores_df, matched_df, title="", resolution=8,
                   max_width=560, max_height=420, top_corridors=14):
    """
    orders_df   : orders for ONE metro (needs store_lat, store_lon, order_id)
    stores_df   : stores for that metro (store_id, store_lat, store_lon, retailer)
    matched_df  : matched bundle rows for that metro, already joined with
                  store_lat_1/lon_1/store_lat_2/lon_2 columns
    """
    if len(orders_df) == 0:
        return "<div style='padding:40px;color:#8B8894;font-family:Inter,sans-serif;'>No data for this selection.</div>"

    # --- aggregate orders per hex ---
    hex_counts = {}
    for _, r in orders_df.iterrows():
        hx = h3.latlng_to_cell(r["store_lat"], r["store_lon"], resolution)
        hex_counts[hx] = hex_counts.get(hx, 0) + 1

    # --- aggregate bundle activity per hex + corridor frequency between hexes ---
    hex_bundle_counts = {}
    corridor_counts = {}
    if matched_df is not None and len(matched_df) > 0:
        for _, r in matched_df.iterrows():
            h1 = h3.latlng_to_cell(r["store_lat_1"], r["store_lon_1"], resolution)
            h2 = h3.latlng_to_cell(r["store_lat_2"], r["store_lon_2"], resolution)
            hex_bundle_counts[h1] = hex_bundle_counts.get(h1, 0) + 1
            hex_bundle_counts[h2] = hex_bundle_counts.get(h2, 0) + 1
            if h1 != h2:
                key = tuple(sorted([h1, h2]))
                corridor_counts[key] = corridor_counts.get(key, 0) + 1

    max_bundles = max(hex_bundle_counts.values()) if hex_bundle_counts else 1
    # Normalize order density against the 75th percentile, not the raw max,
    # so one outlier hex doesn't wash out every other hex's color.
    sorted_vals = sorted(hex_counts.values())
    p75 = sorted_vals[int(len(sorted_vals) * 0.75)] if sorted_vals else 1
    p75 = max(p75, 1)

    # --- build hex polygons using REAL lat/lng boundaries (no projection needed --
    # Leaflet handles the map projection itself) ---
    hexes_js = []
    all_lats, all_lons = [], []
    for hx, count in hex_counts.items():
        boundary = h3.cell_to_boundary(hx)  # list of (lat, lng) tuples
        for lat, lng in boundary:
            all_lats.append(lat)
            all_lons.append(lng)
        density_ratio = min(count / p75, 1.0)
        bundle_ratio = hex_bundle_counts.get(hx, 0) / max_bundles if max_bundles else 0
        color_t = max(density_ratio, bundle_ratio)
        hexes_js.append({
            "boundary": [[lat, lng] for lat, lng in boundary],
            "orders": count,
            "bundles": hex_bundle_counts.get(hx, 0),
            "color": _hex_color(color_t),
            "fillOpacity": round(0.35 + 0.45 * math.sqrt(color_t), 3),
        })

    # --- top corridors, as real center-to-center great-circle-ish lines ---
    sorted_corridors = sorted(corridor_counts.items(), key=lambda x: -x[1])[:top_corridors]
    max_corridor = sorted_corridors[0][1] if sorted_corridors else 1
    corridors_js = []
    for (h1, h2), cnt in sorted_corridors:
        lat1, lon1 = h3.cell_to_latlng(h1)
        lat2, lon2 = h3.cell_to_latlng(h2)
        corridors_js.append({
            "points": [[lat1, lon1], [lat2, lon2]],
            "weight": round(cnt / max_corridor, 3),
            "count": cnt,
        })

    # --- store markers ---
    stores_js = []
    if stores_df is not None:
        for _, s in stores_df.iterrows():
            stores_js.append({
                "lat": float(s["store_lat"]), "lng": float(s["store_lon"]),
                "retailer": s["retailer"], "id": s["store_id"],
            })
            all_lats.append(float(s["store_lat"]))
            all_lons.append(float(s["store_lon"]))

    bounds = [[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]]
    uid = abs(hash((title, resolution, len(hexes_js)))) % (10**8)

    payload = json.dumps({"hexes": hexes_js, "corridors": corridors_js,
                          "stores": stores_js, "bounds": bounds})

    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600&family=Inter:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap');
#card-{uid} {{ background:#fff; border-radius:16px; padding:18px 20px 12px;
  border:1px solid rgba(37,18,58,0.07); box-shadow:0 2px 14px rgba(37,18,58,0.05); }}
#title-{uid} {{ font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:1.02rem;
  color:{HAITI}; margin-bottom:2px; }}
#sub-{uid} {{ font-family:'IBM Plex Mono',monospace; font-size:0.68rem; color:{MUTED};
  letter-spacing:0.06em; margin-bottom:8px; }}
#map-{uid} {{ height:{max_height}px; border-radius:12px; background:#EDEBE6; }}
.corridor-{uid} {{ stroke-dasharray:1 8; animation: dash-{uid} 2.6s linear infinite; }}
@keyframes dash-{uid} {{ to {{ stroke-dashoffset:-72; }} }}
{_LEAFLET_CSS}
</style>
<div id="card-{uid}">
  <div id="title-{uid}">{title}</div>
  <div id="sub-{uid}">H3 RES {resolution} &middot; HEX FILL = ORDER DENSITY &middot; LINES = TOP BUNDLING CORRIDORS</div>
  <div id="map-{uid}"></div>
</div>
<script>
{_LEAFLET_JS}
</script>
<script>
(function() {{
  const D = {payload};
  const HAITI = "{HAITI}", YG = "{YELLOWGREEN}";

  function init() {{
    // Multiple maps on one page settle their iframe layout at different
    // rates -- a fixed delay works for some and not others. Poll until the
    // container genuinely has a non-zero size before Leaflet ever touches it,
    // since Leaflet caches container size at map-creation time and a later
    // invalidateSize() does not repair vector layers already projected
    // against a stale zero size.
    function whenSized(tries) {{
      tries = tries || 0;
      const el = document.getElementById("map-{uid}");
      if ((!el || el.offsetWidth === 0) && tries < 100) {{
        return setTimeout(function() {{ whenSized(tries + 1); }}, 50);
      }}
      start();
    }}

    function start() {{
      const initCenter = [(D.bounds[0][0] + D.bounds[1][0]) / 2, (D.bounds[0][1] + D.bounds[1][1]) / 2];
      const map = L.map("map-{uid}", {{ scrollWheelZoom: false, center: initCenter, zoom: 11 }});
    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
      attribution: '&copy; OpenStreetMap &copy; CARTO', subdomains: 'abcd', maxZoom: 19
    }}).addTo(map);

    D.hexes.forEach(function(h) {{
      const poly = L.polygon(h.boundary, {{
        color: HAITI, weight: 1, opacity: 0.45,
        fillColor: h.color, fillOpacity: h.fillOpacity
      }}).addTo(map);
      poly.bindTooltip(
        '<b>' + h.orders + '</b> orders originate here<br/><b>' + h.bundles + '</b> bundle-endpoint events',
        {{ sticky: true }}
      );
      poly.on('mouseover', function() {{ this.setStyle({{ weight: 2.4, opacity: 0.85 }}); }});
      poly.on('mouseout', function() {{ this.setStyle({{ weight: 1, opacity: 0.45 }}); }});
    }});

    D.corridors.forEach(function(c) {{
      const line = L.polyline(c.points, {{
        color: YG, weight: 1.5 + c.weight * 4, opacity: 0.85,
        className: "corridor-{uid}"
      }}).addTo(map);
      line.bindTooltip('<b>' + c.count + '</b> bundles matched on this corridor');
      line.on('mouseover', function() {{ this.setStyle({{ color: "#23CC6B", weight: 2.5 + c.weight * 5 }}); }});
      line.on('mouseout', function() {{ this.setStyle({{ color: YG, weight: 1.5 + c.weight * 4 }}); }});
    }});

    D.stores.forEach(function(s) {{
      L.circleMarker([s.lat, s.lng], {{
        radius: 5, fillColor: "#fff", color: HAITI, weight: 2, fillOpacity: 1
      }}).addTo(map).bindTooltip('<b>' + s.retailer + '</b><br/>Store ' + s.id);
    }});

    map.fitBounds(D.bounds, {{ padding: [16, 16] }});
    }}

    whenSized();
  }}

  init();
}})();
</script>
"""
