"""
D3-based chart components, Shipt-branded. Self-contained: D3 is inlined from a
local file so nothing depends on a CDN being reachable at demo time.
"""

import json
import os

HAITI = "#25123A"
MID_PURPLE = "#4A2D6B"
MEADOW = "#23CC6B"
YELLOWGREEN = "#BAE581"
CHARCOAL = "#2B2B33"
MUTED = "#8B8894"
GRID = "rgba(37,18,58,0.08)"

_D3_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "d3.min.js")
with open(_D3_PATH, "r", encoding="utf-8") as _f:
    D3_SOURCE = _f.read()

FONTS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap');
.d3wrap { font-family: 'Inter', sans-serif; }
.d3wrap .num { font-family: 'IBM Plex Mono', monospace; }
.d3wrap .ttl { font-family: 'Space Grotesk', sans-serif; font-weight: 600; }
.d3tip { position:absolute; pointer-events:none; background:#25123A; color:#fff;
  font-family:'Inter',sans-serif; font-size:12px; padding:7px 11px; border-radius:8px;
  box-shadow:0 4px 16px rgba(37,18,58,.25); opacity:0; z-index:20; line-height:1.5; }
</style>
"""


def _shell(inner_html, script_body, uid, height, maxw=None):
    mw = f"max-width:{maxw}px;" if maxw else ""
    return f"""{FONTS}
<div class="d3wrap" id="w-{uid}" style="position:relative;{mw}margin:0 auto;">{inner_html}</div>
<script>{D3_SOURCE}</script>
<script>
(function() {{
  const root = document.getElementById("w-{uid}");
  const tip = d3.select(root).append("div").attr("class","d3tip");
  function showTip(html, ev) {{
    const [mx,my] = d3.pointer(ev, root);
    tip.style("opacity",1).html(html).style("left",(mx+14)+"px").style("top",(my-12)+"px");
  }}
  function hideTip() {{ tip.style("opacity",0); }}
  {script_body}
}})();
</script>"""


def funnel_chart(stages, uid="funnel", width=660):
    """stages: [{label, sublabel, value, drop_label}] -- drop_label shown BELOW that stage."""
    data = json.dumps(stages)
    colors = json.dumps([HAITI, MID_PURPLE, MEADOW, YELLOWGREEN])
    script = f"""
  const stages = {data}, colors = {colors};
  const W = {width}, labelW = 172, barW = W - labelW - 16, rowH = 58, dropH = 26;
  const H = stages.length * rowH + (stages.length - 1) * dropH + 10;
  const svg = d3.select(root).append("svg").attr("width","100%")
    .attr("viewBox", `0 0 ${{W}} ${{H}}`).style("overflow","visible");
  const maxV = stages[0].value;
  let y = 0;
  stages.forEach((s, i) => {{
    const w = Math.max(barW * (s.value / maxV), 54);
    const x = labelW + 16 + (barW - w) / 2;
    svg.append("text").attr("x", labelW).attr("y", y + rowH/2 - 4)
      .attr("text-anchor","end").attr("font-size",13).attr("font-weight",500)
      .attr("fill","{CHARCOAL}").text(s.label);
    svg.append("text").attr("x", labelW).attr("y", y + rowH/2 + 13)
      .attr("text-anchor","end").attr("font-size",11).attr("fill","{MUTED}").text(s.sublabel);
    const g = svg.append("g").style("cursor","pointer")
      .on("mousemove", ev => showTip(`<b>${{s.value.toLocaleString()}}</b> ${{s.label.toLowerCase()}}<br/>${{(100*s.value/maxV).toFixed(1)}}% of candidates`, ev))
      .on("mouseleave", hideTip);
    const rect = g.append("rect").attr("x", labelW + 16 + barW/2).attr("y", y)
      .attr("width", 0).attr("height", rowH - 6).attr("rx", 5).attr("fill", colors[i]);
    rect.transition().duration(650).delay(i*120)
      .attr("x", x).attr("width", w);
    const light = i < 2;
    g.append("text").attr("x", labelW + 16 + barW/2).attr("y", y + rowH/2 - 4)
      .attr("text-anchor","middle").attr("font-size", w > 90 ? 16 : 12).attr("font-weight",500)
      .attr("font-family","'IBM Plex Mono',monospace")
      .attr("fill", light ? "#fff" : "{HAITI}").attr("opacity",0)
      .text(s.value.toLocaleString())
      .transition().duration(400).delay(i*120+400).attr("opacity",1);
    if (w > 90) {{
      g.append("text").attr("x", labelW + 16 + barW/2).attr("y", y + rowH/2 + 14)
        .attr("text-anchor","middle").attr("font-size",11)
        .attr("fill", light ? "{YELLOWGREEN}" : "{HAITI}").attr("opacity",0)
        .text((100*s.value/maxV).toFixed(0) + "%")
        .transition().duration(400).delay(i*120+400).attr("opacity",1);
    }}
    y += rowH;
    if (s.drop_label) {{
      svg.append("text").attr("x", labelW + 16 + barW/2).attr("y", y + dropH/2)
        .attr("text-anchor","middle").attr("font-size",11).attr("fill","{MUTED}")
        .attr("opacity",0).text(s.drop_label)
        .transition().duration(400).delay(i*120+600).attr("opacity",1);
      y += dropH;
    }}
  }});
"""
    return _shell("", script, uid, 0, maxw=width)


def bar_chart(items, uid="bar", width=620, height=300, value_fmt="{:,.0f}",
              horizontal=True, color=MEADOW, xlabel=""):
    """items: [{label, value}]"""
    data = json.dumps(items)
    script = f"""
  const items = {data};
  const W = {width}, H = {height}, m = {{t:14,r:70,b:34,l:150}};
  const iw = W-m.l-m.r, ih = H-m.t-m.b;
  const svg = d3.select(root).append("svg").attr("width","100%")
    .attr("viewBox",`0 0 ${{W}} ${{H}}`).style("overflow","visible");
  const g = svg.append("g").attr("transform",`translate(${{m.l}},${{m.t}})`);
  const x = d3.scaleLinear().domain([0, d3.max(items,d=>d.value)*1.08]).range([0,iw]);
  const y = d3.scaleBand().domain(items.map(d=>d.label)).range([0,ih]).padding(0.3);
  g.selectAll("line.grid").data(x.ticks(5)).join("line").attr("class","grid")
    .attr("x1",d=>x(d)).attr("x2",d=>x(d)).attr("y1",0).attr("y2",ih)
    .attr("stroke","{GRID}").attr("stroke-width",1);
  g.selectAll("text.lbl").data(items).join("text").attr("class","lbl")
    .attr("x",-10).attr("y",d=>y(d.label)+y.bandwidth()/2+4).attr("text-anchor","end")
    .attr("font-size",12).attr("fill","{CHARCOAL}").text(d=>d.label);
  g.selectAll("rect").data(items).join("rect")
    .attr("x",0).attr("y",d=>y(d.label)).attr("height",y.bandwidth())
    .attr("rx",4).attr("fill","{color}").attr("width",0)
    .style("cursor","pointer")
    .on("mousemove",(ev,d)=>showTip(`<b>${{d.label}}</b><br/>${{d.value.toLocaleString(undefined,{{maximumFractionDigits:2}})}}`,ev))
    .on("mouseleave",hideTip)
    .transition().duration(700).delay((d,i)=>i*45).attr("width",d=>x(d.value));
  g.selectAll("text.val").data(items).join("text").attr("class","val")
    .attr("x",d=>x(d.value)+8).attr("y",d=>y(d.label)+y.bandwidth()/2+4)
    .attr("font-size",12).attr("font-family","'IBM Plex Mono',monospace")
    .attr("fill","{MUTED}").attr("opacity",0)
    .text(d=>d.display || d.value.toLocaleString(undefined,{{maximumFractionDigits:2}}))
    .transition().duration(400).delay(600).attr("opacity",1);
  g.append("g").attr("transform",`translate(0,${{ih}})`)
    .call(d3.axisBottom(x).ticks(5).tickSize(0).tickPadding(8))
    .call(s=>s.select(".domain").remove())
    .selectAll("text").attr("font-size",11).attr("fill","{MUTED}");
  if ("{xlabel}") svg.append("text").attr("x",m.l+iw/2).attr("y",H-2)
    .attr("text-anchor","middle").attr("font-size",11).attr("fill","{MUTED}").text("{xlabel}");
"""
    return _shell("", script, uid, height, maxw=width)


def scatter_chart(points, uid="scatter", width=620, height=380,
                  xlabel="", ylabel="", x_pct=True):
    """points: [{label, x, y, size}]"""
    data = json.dumps(points)
    script = f"""
  const pts = {data};
  const W={width}, H={height}, m={{t:20,r:40,b:48,l:62}};
  const iw=W-m.l-m.r, ih=H-m.t-m.b;
  const svg=d3.select(root).append("svg").attr("width","100%")
    .attr("viewBox",`0 0 ${{W}} ${{H}}`).style("overflow","visible");
  const g=svg.append("g").attr("transform",`translate(${{m.l}},${{m.t}})`);
  const xe=d3.extent(pts,d=>d.x), ye=d3.extent(pts,d=>d.y);
  const xp=(xe[1]-xe[0])*0.22||0.1, yp=(ye[1]-ye[0])*0.22||1;
  const x=d3.scaleLinear().domain([xe[0]-xp,xe[1]+xp]).range([0,iw]);
  const y=d3.scaleLinear().domain([ye[0]-yp,ye[1]+yp]).range([ih,0]);
  const r=d3.scaleSqrt().domain(d3.extent(pts,d=>d.size)).range([14,34]);
  g.selectAll("line.gy").data(y.ticks(5)).join("line").attr("class","gy")
    .attr("x1",0).attr("x2",iw).attr("y1",d=>y(d)).attr("y2",d=>y(d))
    .attr("stroke","{GRID}");
  g.selectAll("line.gx").data(x.ticks(5)).join("line").attr("class","gx")
    .attr("y1",0).attr("y2",ih).attr("x1",d=>x(d)).attr("x2",d=>x(d))
    .attr("stroke","{GRID}");
  const node=g.selectAll("g.pt").data(pts).join("g").attr("class","pt")
    .attr("transform",d=>`translate(${{x(d.x)}},${{y(d.y)}})`).style("cursor","pointer")
    .on("mousemove",(ev,d)=>showTip(`<b>${{d.label}}</b><br/>${{d.tip||""}}`,ev))
    .on("mouseleave",hideTip);
  node.append("circle").attr("r",0).attr("fill","{MEADOW}").attr("fill-opacity",.72)
    .attr("stroke","{HAITI}").attr("stroke-width",1.4)
    .transition().duration(700).delay((d,i)=>i*90).attr("r",d=>r(d.size));
  node.append("text").attr("text-anchor","middle").attr("y",d=>-r(d.size)-9)
    .attr("font-size",12).attr("font-weight",500).attr("fill","{CHARCOAL}")
    .attr("opacity",0).text(d=>d.label)
    .transition().duration(400).delay(700).attr("opacity",1);
  g.append("g").attr("transform",`translate(0,${{ih}})`)
    .call(d3.axisBottom(x).ticks(5).tickSize(0).tickPadding(8)
      .tickFormat(d=>{str(x_pct).lower()} ? (d*100).toFixed(0)+"%" : d))
    .call(s=>s.select(".domain").attr("stroke","{GRID}"))
    .selectAll("text").attr("font-size",11).attr("fill","{MUTED}");
  g.append("g").call(d3.axisLeft(y).ticks(5).tickSize(0).tickPadding(8))
    .call(s=>s.select(".domain").remove())
    .selectAll("text").attr("font-size",11).attr("fill","{MUTED}");
  svg.append("text").attr("x",m.l+iw/2).attr("y",H-6).attr("text-anchor","middle")
    .attr("font-size",11).attr("fill","{MUTED}").text("{xlabel}");
  svg.append("text").attr("transform","rotate(-90)").attr("x",-(m.t+ih/2)).attr("y",14)
    .attr("text-anchor","middle").attr("font-size",11).attr("fill","{MUTED}").text("{ylabel}");
"""
    return _shell("", script, uid, height, maxw=width)


def line_chart(series, uid="line", width=620, height=340, xlabel="", ylabel="",
               x_pct=False, y_pct=False, annotate=None):
    """series: [{name, color, points:[{x,y}]}]"""
    data = json.dumps(series)
    ann = json.dumps(annotate or [])
    script = f"""
  const series={data}, annots={ann};
  const W={width}, H={height}, m={{t:24,r:24,b:48,l:60}};
  const iw=W-m.l-m.r, ih=H-m.t-m.b;
  const svg=d3.select(root).append("svg").attr("width","100%")
    .attr("viewBox",`0 0 ${{W}} ${{H}}`).style("overflow","visible");
  const g=svg.append("g").attr("transform",`translate(${{m.l}},${{m.t}})`);
  const all=series.flatMap(s=>s.points);
  const x=d3.scaleLinear().domain(d3.extent(all,d=>d.x)).range([0,iw]);
  const ymax=d3.max(all,d=>d.y), ymin=d3.min(all,d=>d.y);
  const y=d3.scaleLinear().domain([Math.min(0,ymin*0.9), ymax*1.1]).range([ih,0]);
  g.selectAll("line.gy").data(y.ticks(5)).join("line").attr("class","gy")
    .attr("x1",0).attr("x2",iw).attr("y1",d=>y(d)).attr("y2",d=>y(d)).attr("stroke","{GRID}");
  annots.forEach(a=>{{
    g.append("line").attr("x1",x(a.x)).attr("x2",x(a.x)).attr("y1",0).attr("y2",ih)
      .attr("stroke","{MUTED}").attr("stroke-dasharray","4 4").attr("stroke-width",1);
    g.append("text").attr("x",x(a.x)+6).attr("y",12).attr("font-size",11)
      .attr("fill","{MUTED}").text(a.label);
  }});
  const line=d3.line().x(d=>x(d.x)).y(d=>y(d.y)).curve(d3.curveMonotoneX);
  series.forEach((s,si)=>{{
    const p=g.append("path").datum(s.points).attr("fill","none")
      .attr("stroke",s.color).attr("stroke-width",2.4).attr("stroke-linecap","round")
      .attr("d",line);
    const L=p.node().getTotalLength();
    p.attr("stroke-dasharray",`${{L}} ${{L}}`).attr("stroke-dashoffset",L)
      .transition().duration(900).delay(si*150).ease(d3.easeCubicOut).attr("stroke-dashoffset",0);
    g.selectAll(`circle.s${{si}}`).data(s.points).join("circle").attr("class",`s${{si}}`)
      .attr("cx",d=>x(d.x)).attr("cy",d=>y(d.y)).attr("r",3.2).attr("fill",s.color)
      .attr("opacity",0).style("cursor","pointer")
      .on("mousemove",(ev,d)=>showTip(`<b>${{s.name}}</b><br/>${{d.tip||d.y}}`,ev))
      .on("mouseleave",hideTip)
      .transition().duration(400).delay(900+si*150).attr("opacity",1);
  }});
  g.append("g").attr("transform",`translate(0,${{ih}})`)
    .call(d3.axisBottom(x).ticks(6).tickSize(0).tickPadding(8)
      .tickFormat(d=>{str(x_pct).lower()}?(d*100).toFixed(0)+"%":d))
    .call(s=>s.select(".domain").attr("stroke","{GRID}"))
    .selectAll("text").attr("font-size",11).attr("fill","{MUTED}");
  g.append("g").call(d3.axisLeft(y).ticks(5).tickSize(0).tickPadding(8)
      .tickFormat(d=>{str(y_pct).lower()}?(d*100).toFixed(0)+"%":d))
    .call(s=>s.select(".domain").remove())
    .selectAll("text").attr("font-size",11).attr("fill","{MUTED}");
  svg.append("text").attr("x",m.l+iw/2).attr("y",H-6).attr("text-anchor","middle")
    .attr("font-size",11).attr("fill","{MUTED}").text("{xlabel}");
  svg.append("text").attr("transform","rotate(-90)").attr("x",-(m.t+ih/2)).attr("y",13)
    .attr("text-anchor","middle").attr("font-size",11).attr("fill","{MUTED}").text("{ylabel}");
  const leg=svg.append("g").attr("transform",`translate(${{m.l}},10)`);
  let lx=0;
  series.forEach(s=>{{
    leg.append("rect").attr("x",lx).attr("y",-6).attr("width",9).attr("height",9)
      .attr("rx",2).attr("fill",s.color);
    leg.append("text").attr("x",lx+14).attr("y",2).attr("font-size",11)
      .attr("fill","{MUTED}").text(s.name);
    lx += 22 + s.name.length*6.1;
  }});
"""
    return _shell("", script, uid, height, maxw=width)


def grouped_bar(groups, series_names, colors, uid="gbar", width=620, height=340,
                ylabel="", y_pct=False):
    """groups: [{label, values:[v1,v2]}]"""
    data = json.dumps(groups)
    snames = json.dumps(series_names)
    cols = json.dumps(colors)
    script = f"""
  const groups={data}, names={snames}, colors={cols};
  const W={width}, H={height}, m={{t:26,r:20,b:44,l:58}};
  const iw=W-m.l-m.r, ih=H-m.t-m.b;
  const svg=d3.select(root).append("svg").attr("width","100%")
    .attr("viewBox",`0 0 ${{W}} ${{H}}`).style("overflow","visible");
  const g=svg.append("g").attr("transform",`translate(${{m.l}},${{m.t}})`);
  const x0=d3.scaleBand().domain(groups.map(d=>d.label)).range([0,iw]).padding(0.28);
  const x1=d3.scaleBand().domain(names).range([0,x0.bandwidth()]).padding(0.12);
  const ymax=d3.max(groups,d=>d3.max(d.values));
  const y=d3.scaleLinear().domain([0,ymax*1.12]).range([ih,0]);
  g.selectAll("line.gy").data(y.ticks(5)).join("line").attr("class","gy")
    .attr("x1",0).attr("x2",iw).attr("y1",d=>y(d)).attr("y2",d=>y(d)).attr("stroke","{GRID}");
  groups.forEach(grp=>{{
    names.forEach((nm,j)=>{{
      g.append("rect").attr("x",x0(grp.label)+x1(nm)).attr("y",ih)
        .attr("width",x1.bandwidth()).attr("height",0).attr("rx",3)
        .attr("fill",colors[j]).style("cursor","pointer")
        .on("mousemove",ev=>showTip(`<b>${{grp.label}}</b><br/>${{nm}}: ${{{str(y_pct).lower()}?(grp.values[j]*100).toFixed(1)+"%":grp.values[j].toFixed(2)}}`,ev))
        .on("mouseleave",hideTip)
        .transition().duration(650).delay(j*90)
        .attr("y",y(grp.values[j])).attr("height",ih-y(grp.values[j]));
    }});
  }});
  g.append("g").attr("transform",`translate(0,${{ih}})`)
    .call(d3.axisBottom(x0).tickSize(0).tickPadding(8))
    .call(s=>s.select(".domain").attr("stroke","{GRID}"))
    .selectAll("text").attr("font-size",11).attr("fill","{CHARCOAL}");
  g.append("g").call(d3.axisLeft(y).ticks(5).tickSize(0).tickPadding(8)
      .tickFormat(d=>{str(y_pct).lower()}?(d*100).toFixed(0)+"%":d))
    .call(s=>s.select(".domain").remove())
    .selectAll("text").attr("font-size",11).attr("fill","{MUTED}");
  svg.append("text").attr("transform","rotate(-90)").attr("x",-(m.t+ih/2)).attr("y",13)
    .attr("text-anchor","middle").attr("font-size",11).attr("fill","{MUTED}").text("{ylabel}");
  const leg=svg.append("g").attr("transform",`translate(${{m.l}},12)`);
  let lx=0;
  names.forEach((nm,j)=>{{
    leg.append("rect").attr("x",lx).attr("y",-7).attr("width",9).attr("height",9)
      .attr("rx",2).attr("fill",colors[j]);
    leg.append("text").attr("x",lx+13).attr("y",1).attr("font-size",11)
      .attr("fill","{MUTED}").text(nm);
    lx += 22 + nm.length*6.1;
  }});
"""
    return _shell("", script, uid, height, maxw=width)
