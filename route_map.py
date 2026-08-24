"""
Route comparison map: one real bundle, drawn on a real street basemap.

Shows the two solo routes vs. the single bundled route, so the bundling
mechanic is visible on the ground rather than existing only as a percentage.

Uses Leaflet + CARTO raster tiles loaded client-side. If tiles fail to load
(offline, firewall), the route polylines and markers still render on a plain
background -- graceful degradation rather than a blank canvas.
"""

import json

HAITI = "#25123A"
MEADOW = "#23CC6B"
YELLOWGREEN = "#BAE581"
CORAL = "#E8593C"
MUTED = "#8B8894"


def render_route_map(bundle_row, uid="routemap", height=520):
    """bundle_row: dict with store_lat_1/lon_1, customer_lat_1/lon_1,
    store_lat_2/lon_2, customer_lat_2/lon_2, best_route, distances."""

    s1 = [bundle_row["store_lat_1"], bundle_row["store_lon_1"]]
    c1 = [bundle_row["customer_lat_1"], bundle_row["customer_lon_1"]]
    s2 = [bundle_row["store_lat_2"], bundle_row["store_lon_2"]]
    c2 = [bundle_row["customer_lat_2"], bundle_row["customer_lon_2"]]

    stops = {"s1": s1, "c1": c1, "s2": s2, "c2": c2}
    bundled_order = bundle_row["best_route"].split("->")
    bundled_path = [stops[k] for k in bundled_order]

    # Solo baseline: s1->c1, then reposition c1->s2, then s2->c2
    solo_leg_a = [s1, c1]
    solo_reposition = [c1, s2]
    solo_leg_b = [s2, c2]

    payload = json.dumps({
        "s1": s1, "c1": c1, "s2": s2, "c2": c2,
        "bundled": bundled_path,
        "bundledOrder": bundled_order,
        "soloA": solo_leg_a,
        "soloRepo": solo_reposition,
        "soloB": solo_leg_b,
        "soloDist": round(float(bundle_row["solo_dist_km"]), 2),
        "bundleDist": round(float(bundle_row["bundle_dist_km"]), 2),
        "saved": round(float(bundle_row["dist_saved_km"]), 2),
        "pct": round(float(bundle_row["pct_dist_saved"]) * 100, 1),
        "retailer1": bundle_row.get("retailer_1", "Store A"),
        "retailer2": bundle_row.get("retailer_2", "Store B"),
    })

    return f"""
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600&family=Inter:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap');
#rm-{uid} {{ height:{height}px; border-radius:14px; background:#EDEBE6; }}
.rm-shell {{ position:relative; font-family:'Inter',sans-serif; }}
.rm-toggle {{ display:flex; gap:6px; margin-bottom:10px; }}
.rm-btn {{ flex:0 0 auto; padding:8px 16px; border-radius:999px; border:1px solid rgba(37,18,58,.15);
  background:#fff; color:{HAITI}; font-size:13px; font-weight:500; cursor:pointer;
  font-family:'Inter',sans-serif; transition:all .18s; }}
.rm-btn.on {{ background:{HAITI}; color:#fff; border-color:{HAITI}; }}
.rm-stats {{ position:absolute; top:52px; right:14px; z-index:500;
  background:rgba(37,18,58,.93); border-radius:12px; padding:12px 16px; color:#fff;
  backdrop-filter:blur(8px); box-shadow:0 4px 20px rgba(37,18,58,.3); }}
.rm-stats .r {{ display:flex; justify-content:space-between; gap:18px; font-size:12px; margin:3px 0; }}
.rm-stats .k {{ color:#BAE581; font-family:'IBM Plex Mono',monospace; font-size:10px;
  letter-spacing:.08em; text-transform:uppercase; }}
.rm-stats .v {{ font-family:'IBM Plex Mono',monospace; font-weight:500; }}
.rm-legend {{ display:flex; gap:16px; margin-top:10px; font-size:11.5px; color:{MUTED}; flex-wrap:wrap; }}
.rm-legend span {{ display:flex; align-items:center; gap:6px; }}
.rm-sw {{ width:16px; height:3px; border-radius:2px; }}
.leaflet-container {{ font-family:'Inter',sans-serif; }}
</style>
<div class="rm-shell">
  <div class="rm-toggle">
    <button class="rm-btn on" id="b-solo-{uid}">Two solo routes</button>
    <button class="rm-btn" id="b-bundle-{uid}">One bundled route</button>
    <button class="rm-btn" id="b-both-{uid}">Compare</button>
  </div>
  <div id="rm-{uid}"></div>
  <div class="rm-stats" id="stats-{uid}"></div>
  <div class="rm-legend">
    <span><i class="rm-sw" style="background:{CORAL}"></i>Solo route</span>
    <span><i class="rm-sw" style="background:{CORAL};opacity:.45"></i>Repositioning leg (eliminated by bundling)</span>
    <span><i class="rm-sw" style="background:{MEADOW}"></i>Bundled route</span>
    <span><i class="rm-sw" style="background:{HAITI};height:9px;width:9px;border-radius:50%"></i>Store</span>
    <span><i class="rm-sw" style="background:#fff;border:2px solid {HAITI};height:9px;width:9px;border-radius:50%"></i>Customer</span>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
(function() {{
  const D = {payload};
  // Leaflet's <script src> may not have finished executing when this inline
  // block runs inside a sandboxed iframe -- poll until L exists, then init.
  const stats = document.getElementById('stats-{uid}');
  function setStats(mode) {{
    let h = '';
    if (mode === 'solo' || mode === 'both')
      h += `<div class="r"><span class="k">Solo total</span><span class="v">${{D.soloDist}} km</span></div>`;
    if (mode === 'bundle' || mode === 'both')
      h += `<div class="r"><span class="k">Bundled</span><span class="v">${{D.bundleDist}} km</span></div>`;
    if (mode === 'both')
      h += `<div class="r" style="border-top:1px solid rgba(186,229,129,.3);margin-top:6px;padding-top:6px">
            <span class="k">Saved</span><span class="v" style="color:#BAE581">${{D.saved}} km &middot; ${{D.pct}}%</span></div>`;
    stats.innerHTML = h;
  }}

  function boot(tries) {{
    tries = tries || 0;
    if (typeof L === "undefined") {{
      if (tries > 40) {{ return fallback(); }}
      return setTimeout(function() {{ boot(tries + 1); }}, 60);
    }}
    init();
  }}

  // If Leaflet can't load (offline / blocked CDN), draw the routes as plain
  // SVG so the comparison is still visible -- degraded, but never blank.
  function fallback() {{
    const host = document.getElementById('rm-{uid}');
    const W = host.clientWidth || 900, H = {height};
    const pts = [D.s1, D.s2, D.c1, D.c2];
    const lats = pts.map(p => p[0]), lons = pts.map(p => p[1]);
    const pad = 60;
    const latMin = Math.min(...lats), latMax = Math.max(...lats);
    const lonMin = Math.min(...lons), lonMax = Math.max(...lons);
    const sx = (W - 2*pad) / ((lonMax - lonMin) || 1e-6);
    const sy = (H - 2*pad) / ((latMax - latMin) || 1e-6);
    const s = Math.min(sx, sy);
    const px = p => [pad + (p[1] - lonMin) * s, H - pad - (p[0] - latMin) * s];
    function poly(arr, color, dash, w) {{
      const d = arr.map(px).map(p => p.join(',')).join(' ');
      return `<polyline points="${{d}}" fill="none" stroke="${{color}}" stroke-width="${{w||4}}"
        ${{dash ? 'stroke-dasharray="8 8" opacity=".45"' : 'opacity=".9"'}}
        stroke-linecap="round" stroke-linejoin="round"/>`;
    }}
    function dot(p, isStore, label) {{
      const [x,y] = px(p);
      return `<circle cx="${{x}}" cy="${{y}}" r="${{isStore?8:6}}"
        fill="${{isStore?'{HAITI}':'#fff'}}" stroke="{HAITI}" stroke-width="2.5"/>
        <text x="${{x}}" y="${{y-14}}" text-anchor="middle" font-size="11"
        font-family="Inter,sans-serif" fill="{HAITI}">${{label}}</text>`;
    }}
    host.innerHTML = `<svg width="100%" height="${{H}}" viewBox="0 0 ${{W}} ${{H}}">
      <rect width="${{W}}" height="${{H}}" fill="#EDEBE6" rx="14"/>
      <g id="fb-solo">
        ${{poly(D.soloA, '{CORAL}')}}${{poly(D.soloB, '{CORAL}')}}${{poly(D.soloRepo, '{CORAL}', true, 3)}}
      </g>
      <g id="fb-bundle" style="display:none">${{poly(D.bundled, '{MEADOW}', false, 5)}}</g>
      ${{dot(D.s1, true, 'Store 1')}}${{dot(D.s2, true, 'Store 2')}}
      ${{dot(D.c1, false, 'Customer 1')}}${{dot(D.c2, false, 'Customer 2')}}
      <text x="${{W/2}}" y="${{H-14}}" text-anchor="middle" font-size="11"
        font-family="Inter,sans-serif" fill="{MUTED}">Street basemap unavailable &mdash; showing route geometry only</text>
    </svg>`;
    const fs = document.getElementById('fb-solo'), fb = document.getElementById('fb-bundle');
    const btns = {{
      solo: document.getElementById('b-solo-{uid}'),
      bundle: document.getElementById('b-bundle-{uid}'),
      both: document.getElementById('b-both-{uid}')
    }};
    function fshow(mode) {{
      Object.values(btns).forEach(b => b.classList.remove('on'));
      btns[mode].classList.add('on');
      fs.style.display = (mode === 'bundle') ? 'none' : '';
      fb.style.display = (mode === 'solo') ? 'none' : '';
      setStats(mode);
    }}
    btns.solo.onclick = () => fshow('solo');
    btns.bundle.onclick = () => fshow('bundle');
    btns.both.onclick = () => fshow('both');
    fshow('solo');
  }}

  function init() {{
  const map = L.map('rm-{uid}', {{ zoomControl:true, attributionControl:true, scrollWheelZoom:false }});
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution:'&copy; OpenStreetMap &copy; CARTO', subdomains:'abcd', maxZoom:19
  }}).addTo(map);

  const soloLayer = L.layerGroup(), bundleLayer = L.layerGroup();

  function arrowLine(pts, color, opts) {{
    return L.polyline(pts, Object.assign({{color:color, weight:4, opacity:.85,
      lineCap:'round', lineJoin:'round'}}, opts||{{}}));
  }}

  arrowLine(D.soloA, '{CORAL}').addTo(soloLayer);
  arrowLine(D.soloB, '{CORAL}').addTo(soloLayer);
  arrowLine(D.soloRepo, '{CORAL}', {{dashArray:'8 8', opacity:.45, weight:3}}).addTo(soloLayer);
  arrowLine(D.bundled, '{MEADOW}', {{weight:5}}).addTo(bundleLayer);

  function marker(pt, isStore, label) {{
    return L.circleMarker(pt, {{
      radius: isStore ? 8 : 6,
      fillColor: isStore ? '{HAITI}' : '#ffffff',
      color: '{HAITI}', weight: 2.5, fillOpacity: 1
    }}).bindTooltip(label, {{direction:'top', offset:[0,-8]}});
  }}
  const markers = L.layerGroup([
    marker(D.s1, true, 'Store 1 &middot; ' + D.retailer1),
    marker(D.s2, true, 'Store 2 &middot; ' + D.retailer2),
    marker(D.c1, false, 'Customer 1'),
    marker(D.c2, false, 'Customer 2')
  ]).addTo(map);

  const bounds = L.latLngBounds([D.s1, D.s2, D.c1, D.c2]).pad(0.22);
  map.fitBounds(bounds);

  const btns = {{
    solo: document.getElementById('b-solo-{uid}'),
    bundle: document.getElementById('b-bundle-{uid}'),
    both: document.getElementById('b-both-{uid}')
  }};
  function show(mode) {{
    Object.values(btns).forEach(b => b.classList.remove('on'));
    btns[mode].classList.add('on');
    map.removeLayer(soloLayer); map.removeLayer(bundleLayer);
    if (mode === 'solo' || mode === 'both') soloLayer.addTo(map);
    if (mode === 'bundle' || mode === 'both') bundleLayer.addTo(map);
    setStats(mode);
  }}
  btns.solo.onclick = () => show('solo');
  btns.bundle.onclick = () => show('bundle');
  btns.both.onclick = () => show('both');
  show('solo');
  }}
  boot();
}})();
</script>
"""
