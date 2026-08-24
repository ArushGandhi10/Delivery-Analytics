"""
Self-contained D3.js hexagon map -- no external tile server, no API key.
Renders real H3 hexagon boundaries, colored by bundling activity, with
animated "corridor" lines showing which stores actually got bundled together.

Why not pydeck: pydeck's basemap depends on a live tile provider (Mapbox/Carto).
If that fails to load -- no internet, no token, a firewall -- the map silently
renders blank. For a live interview demo, a self-contained visualization that
can't fail on external dependency is the safer engineering choice.
"""

import json
import math
import os
import h3

HAITI = "#25123A"
MEADOW = "#23CC6B"
YELLOWGREEN = "#BAE581"
OFFWHITE = "#FAF9F6"
MUTED = "#8B8894"

_D3_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "d3.min.js")
with open(_D3_PATH, "r", encoding="utf-8") as _f:
    _D3_SOURCE = _f.read()


def _project(lat, lon, lat0, lon0, scale_x, scale_y, pad, width, height):
    x = pad + (lon - lon0) * scale_x
    y = height - pad - (lat - lat0) * scale_y
    return x, y


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

    # --- aggregate bundle activity per hex (how often a hex participates in an accepted bundle) ---
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

    max_orders = max(hex_counts.values()) if hex_counts else 1
    max_bundles = max(hex_bundle_counts.values()) if hex_bundle_counts else 1
    # normalize against the 75th percentile rather than the raw max, so density
    # isn't dominated by a single outlier hex leaving everything else pale
    sorted_order_vals = sorted(hex_counts.values())
    p75_orders = sorted_order_vals[int(len(sorted_order_vals) * 0.75)] if sorted_order_vals else 1
    p75_orders = max(p75_orders, 1)

    # --- bounding box across all hex boundary vertices ---
    all_lats, all_lons = [], []
    hex_boundaries = {}
    for hx in hex_counts:
        boundary = h3.cell_to_boundary(hx)
        hex_boundaries[hx] = boundary
        for lat, lon in boundary:
            all_lats.append(lat)
            all_lons.append(lon)

    lat_min, lat_max = min(all_lats), max(all_lats)
    lon_min, lon_max = min(all_lons), max(all_lons)
    lat_pad = (lat_max - lat_min) * 0.12 or 0.01
    lon_pad = (lon_max - lon_min) * 0.12 or 0.01
    lat_min -= lat_pad; lat_max += lat_pad
    lon_min -= lon_pad; lon_max += lon_pad

    # Fit canvas to the metro's actual aspect ratio instead of a fixed box,
    # so small dense metros don't waste half the card as blank space.
    pad = 18
    mean_lat_rad = math.radians((lat_min + lat_max) / 2)
    lon_span = (lon_max - lon_min) * math.cos(mean_lat_rad)
    lat_span = (lat_max - lat_min)
    aspect = (lon_span / lat_span) if lat_span > 0 else 1.0
    aspect = max(0.6, min(aspect, 2.2))  # keep it sane for very thin/wide metros

    if aspect >= (max_width - 2 * pad) / (max_height - 2 * pad):
        width = max_width
        height = int(width / aspect) + 2 * pad
        height = min(height, max_height)
    else:
        height = max_height
        width = int(height * aspect) + 2 * pad
        width = min(width, max_width)

    avail_w, avail_h = width - 2 * pad, height - 2 * pad
    scale = min(avail_w / (lon_span or 1e-6), avail_h / (lat_span or 1e-6))
    scale_x = scale * math.cos(mean_lat_rad)
    scale_y = scale

    def proj(lat, lon):
        return _project(lat, lon, lat_min, lon_min, scale_x, scale_y, pad, width, height)

    # --- build hex polygon data ---
    hexes_js = []
    for hx, boundary in hex_boundaries.items():
        pts = [proj(lat, lon) for lat, lon in boundary]
        center_lat, center_lon = h3.cell_to_latlng(hx)
        cx, cy = proj(center_lat, center_lon)
        hexes_js.append({
            "id": hx,
            "points": pts,
            "cx": cx, "cy": cy,
            "orders": hex_counts.get(hx, 0),
            "bundles": hex_bundle_counts.get(hx, 0),
            "order_ratio": round(min(hex_counts.get(hx, 0) / p75_orders, 1.0), 3),
            "bundle_ratio": round(hex_bundle_counts.get(hx, 0) / max_bundles, 3) if max_bundles else 0,
        })

    # --- top corridors, projected as center-to-center lines ---
    sorted_corridors = sorted(corridor_counts.items(), key=lambda x: -x[1])[:top_corridors]
    max_corridor = sorted_corridors[0][1] if sorted_corridors else 1
    corridors_js = []
    for (h1, h2), cnt in sorted_corridors:
        lat1, lon1 = h3.cell_to_latlng(h1)
        lat2, lon2 = h3.cell_to_latlng(h2)
        x1, y1 = proj(lat1, lon1)
        x2, y2 = proj(lat2, lon2)
        corridors_js.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                             "weight": round(cnt / max_corridor, 3), "count": cnt})

    # --- store markers ---
    stores_js = []
    if stores_df is not None:
        for _, s in stores_df.iterrows():
            x, y = proj(s["store_lat"], s["store_lon"])
            if pad - 20 <= x <= width - pad + 20 and pad - 20 <= y <= height - pad + 20:
                stores_js.append({"x": x, "y": y, "retailer": s["retailer"], "id": s["store_id"]})

    data = {"hexes": hexes_js, "corridors": corridors_js, "stores": stores_js,
           "width": width, "height": height}
    data_json = json.dumps(data)

    html = f"""
<div style="background:#fff;border-radius:16px;padding:18px 20px 12px;
     border:1px solid rgba(37,18,58,0.07); box-shadow:0 2px 14px rgba(37,18,58,0.05);">
  <div style="font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:1.02rem;
       color:{HAITI};margin-bottom:2px;">{title}</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;color:{MUTED};
       letter-spacing:0.06em;margin-bottom:8px;">
       H3 RES {resolution} · HEX FILL = BUNDLE ACTIVITY · LINES = TOP BUNDLING CORRIDORS
  </div>
  <div id="map-{id(orders_df)}" style="position:relative;"></div>
</div>
<script>
{_D3_SOURCE}
</script>
<script>
(function() {{
  const data = {data_json};
  const HAITI = "{HAITI}", MEADOW = "{MEADOW}", YG = "{YELLOWGREEN}", MUTED = "{MUTED}";
  const container = document.getElementById("map-{id(orders_df)}");

  const svg = d3.select(container).append("svg")
    .attr("width", data.width).attr("height", data.height)
    .style("overflow", "visible");

  const tooltip = d3.select(container).append("div")
    .style("position", "absolute").style("pointer-events", "none")
    .style("background", HAITI).style("color", "#fff")
    .style("font-family", "Inter, sans-serif").style("font-size", "12px")
    .style("padding", "7px 11px").style("border-radius", "8px")
    .style("box-shadow", "0 4px 16px rgba(37,18,58,0.25)")
    .style("opacity", 0).style("z-index", 10).style("line-height", "1.5");

  const colorScale = d3.interpolateRgb("#DFF5E8", MEADOW);
  const intensity = d3.scaleSqrt().domain([0, 1]).range([0.6, 1]);

  // hexagons, staggered fade + scale-in
  const hexG = svg.append("g");
  hexG.selectAll("polygon")
    .data(data.hexes)
    .join("polygon")
    .attr("points", d => d.points.map(p => p.join(",")).join(" "))
    .attr("fill", d => colorScale(Math.max(d.order_ratio, d.bundle_ratio)))
    .attr("stroke", HAITI).attr("stroke-width", 1.1).attr("stroke-opacity", 0.55)
    .attr("opacity", 0)
    .style("cursor", "pointer")
    .on("mouseenter", function(event, d) {{
      d3.select(this).attr("stroke-width", 2.2).attr("stroke-opacity", 0.75);
      tooltip.style("opacity", 1)
        .html(`<b>${{d.orders}}</b> orders originate here<br/><b>${{d.bundles}}</b> bundle-endpoint events`);
    }})
    .on("mousemove", function(event) {{
      const [mx, my] = d3.pointer(event, container);
      tooltip.style("left", (mx + 14) + "px").style("top", (my - 10) + "px");
    }})
    .on("mouseleave", function() {{
      d3.select(this).attr("stroke-width", 1).attr("stroke-opacity", 0.4);
      tooltip.style("opacity", 0);
    }})
    .transition().duration(500).delay((d, i) => i * 5)
    .attr("opacity", d => intensity(Math.max(d.order_ratio, d.bundle_ratio)));

  // bundling corridors -- animated dash flow
  const corridorG = svg.append("g");
  const corridors = corridorG.selectAll("line")
    .data(data.corridors)
    .join("line")
    .attr("x1", d => d.x1).attr("y1", d => d.y1)
    .attr("x2", d => d.x2).attr("y2", d => d.y2)
    .attr("stroke", YG)
    .attr("stroke-width", d => 1 + d.weight * 3.2)
    .attr("stroke-linecap", "round")
    .attr("opacity", 0)
    .attr("stroke-dasharray", "1 7")
    .style("cursor", "pointer")
    .on("mouseenter", function(event, d) {{
      d3.select(this).attr("stroke", MEADOW).attr("stroke-width", 2 + d.weight * 4);
      tooltip.style("opacity", 1).html(`<b>${{d.count}}</b> bundles matched on this corridor`);
    }})
    .on("mousemove", function(event) {{
      const [mx, my] = d3.pointer(event, container);
      tooltip.style("left", (mx + 14) + "px").style("top", (my - 10) + "px");
    }})
    .on("mouseleave", function(event, d) {{
      d3.select(this).attr("stroke", YG).attr("stroke-width", 1 + d.weight * 3.2);
      tooltip.style("opacity", 0);
    }});

  corridors.transition().duration(700).delay(400).attr("opacity", 0.8);

  function animateDash() {{
    corridors.attr("stroke-dashoffset", 0)
      .transition().duration(2800).ease(d3.easeLinear)
      .attr("stroke-dashoffset", -64)
      .on("end", animateDash);
  }}
  animateDash();

  // store markers
  svg.append("g").selectAll("circle")
    .data(data.stores)
    .join("circle")
    .attr("cx", d => d.x).attr("cy", d => d.y).attr("r", 0)
    .attr("fill", "#fff").attr("stroke", HAITI).attr("stroke-width", 1.6)
    .style("cursor", "pointer")
    .on("mouseenter", function(event, d) {{
      d3.select(this).attr("r", 6).attr("fill", YG);
      tooltip.style("opacity", 1).html(`<b>${{d.retailer}}</b><br/>Store ${{d.id}}`);
    }})
    .on("mousemove", function(event) {{
      const [mx, my] = d3.pointer(event, container);
      tooltip.style("left", (mx + 14) + "px").style("top", (my - 10) + "px");
    }})
    .on("mouseleave", function() {{
      d3.select(this).attr("r", 3.4).attr("fill", "#fff");
      tooltip.style("opacity", 0);
    }})
    .transition().duration(400).delay(900)
    .attr("r", 3.4);
}})();
</script>
"""
    return html
