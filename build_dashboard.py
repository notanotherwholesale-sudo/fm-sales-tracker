#!/usr/bin/env python3
"""
FM Sales Dashboard generator.
Reads the append-only store (fm_sales.csv) + optional listings snapshot
(fm_listings.json) and writes a single self-contained, phone-friendly
FM_Sales_Dashboard.html with a Shopify-style date-range picker.

Run:  python3 build_dashboard.py
The scheduled task calls this after appending new Crosslist sales.
"""
import csv, json, os, datetime

# Paths are derived from this script's own location so it stays portable
# across the fresh sessions the scheduler creates (the /sessions/<id> prefix changes).
FOLDER = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(FOLDER, "fm_sales.csv")
LISTINGS_PATH = os.path.join(FOLDER, "fm_listings.json")
OUT_PATH = os.path.join(FOLDER, "FM_Sales_Dashboard.html")
SUMMARY_PATH = os.path.join(FOLDER, "summary.json")  # compact feed for the phone widget

def load_sales():
    rows = []
    if not os.path.exists(CSV_PATH):
        return rows
    with open(CSV_PATH, newline="") as f:
        for r in csv.DictReader(f):
            if not r.get("date"):
                continue
            price = str(r.get("price", "0")).replace("\u00a3", "").replace(",", "").strip()
            try:
                price = float(price)
            except ValueError:
                price = 0.0
            rows.append({
                "date": r["date"].strip(),
                "time": (r.get("time") or "").strip(),
                "sku": (r.get("sku") or "").strip(),
                "title": (r.get("title") or r.get("sku") or "").strip(),
                "platform": (r.get("platform") or "").strip(),
                "price": price,
            })
    return rows

def load_listings():
    if os.path.exists(LISTINGS_PATH):
        try:
            with open(LISTINGS_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {"total": None, "depopLive": None, "vintedLive": None, "capturedAt": None}

# icons (inline SVG, stroke=currentColor handled via .badge svg)
IC_NOTE = '<svg viewBox="0 0 24 24"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01"/><path d="M18 12h.01"/></svg>'
IC_BAG  = '<svg viewBox="0 0 24 24"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>'
IC_TREND= '<svg viewBox="0 0 24 24"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>'
IC_TAG  = '<svg viewBox="0 0 24 24"><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L2.7 12.7A2 2 0 0 1 2 11.3V4a2 2 0 0 1 2-2h7.3a2 2 0 0 1 1.4.6l7.9 7.9a2 2 0 0 1 0 2.9Z"/><circle cx="7.5" cy="7.5" r="1.6"/></svg>'
IC_BOX  = '<svg viewBox="0 0 24 24"><path d="M21 8 12 3 3 8l9 5 9-5Z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></svg>'

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0a0e18">
<title>FM Sales Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    --bg1:#0a0e18;--card:#141c2e;--card2:#1a2336;--line:#26314a;--txt:#f2f6fc;--muted:#93a1bd;
    --depop:#ff4d5e;--vinted:#23d3bf;--accent:#8b5cf6;--cyan:#22d3ee;
    --amber:#ffb020;--blue:#3b82f6;--purple:#8b5cf6;--up:#34d399;--down:#fb7185;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    color:var(--txt);padding:22px;max-width:1200px;margin:0 auto;-webkit-font-smoothing:antialiased;
    background:#0a0e18;
    background-image:
      radial-gradient(900px 520px at 82% -12%, rgba(139,92,255,.16), transparent 60%),
      radial-gradient(760px 520px at -5% 2%, rgba(34,211,238,.10), transparent 55%),
      linear-gradient(180deg,#0a0e18 0%,#0b1120 60%,#0a1020 100%);
    min-height:100vh}
  header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:6px}
  h1{font-size:21px;font-weight:800;letter-spacing:.3px;display:flex;align-items:center;gap:10px}
  h1 .logo{width:24px;height:24px;border-radius:8px;background:linear-gradient(135deg,#8b5cf6,#22d3ee);box-shadow:0 4px 14px rgba(139,92,255,.5)}
  h1 .g{background:linear-gradient(90deg,#a78bfa,#22d3ee);-webkit-background-clip:text;background-clip:text;color:transparent}
  .legend{color:var(--muted);font-size:12.5px;margin-bottom:18px}
  .legend .pill{display:inline-flex;align-items:center;gap:6px;margin-right:14px}
  .dot{width:9px;height:9px;border-radius:50%;display:inline-block}
  /* badges */
  .badge{width:36px;height:36px;border-radius:11px;display:inline-flex;align-items:center;justify-content:center;
    box-shadow:0 5px 14px rgba(0,0,0,.4);flex:none}
  .badge svg{width:19px;height:19px;fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .badge.sm{width:30px;height:30px;border-radius:9px}.badge.sm svg{width:16px;height:16px}
  .b-amber{background:linear-gradient(135deg,#ffd166,#ff8a3d)}
  .b-blue{background:linear-gradient(135deg,#60a5fa,#2563eb)}
  .b-purple{background:linear-gradient(135deg,#a78bfa,#7c3aed)}
  .b-red{background:linear-gradient(135deg,#ff6b7a,#e11d48)}
  .b-teal{background:linear-gradient(135deg,#34e0cd,#0d9488)}
  .b-cyan{background:linear-gradient(135deg,#67e8f9,#0891b2)}
  .b-orange{background:linear-gradient(135deg,#fdba74,#f97316)}
  /* range picker */
  .rangewrap{position:relative}
  .rangebtn{background:linear-gradient(180deg,#1b2336,#161d2e);color:var(--txt);border:1px solid var(--line);border-radius:11px;
    padding:9px 14px;font-size:13.5px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:8px;box-shadow:0 4px 14px rgba(0,0,0,.3)}
  .rangebtn:hover{border-color:var(--accent)}
  .rangebtn .cal{opacity:.8}
  .panelpop{position:absolute;right:0;top:48px;z-index:50;background:#131a2b;border:1px solid var(--line);
    border-radius:16px;padding:14px;width:310px;box-shadow:0 22px 60px rgba(0,0,0,.6)}
  .panelpop.hidden{display:none}
  .presets{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:12px}
  .preset{background:#1a2336;border:1px solid var(--line);color:var(--txt);border-radius:9px;
    padding:8px 9px;font-size:12.5px;cursor:pointer;text-align:left}
  .preset:hover{border-color:var(--accent)}
  .preset.active{background:linear-gradient(135deg,#8b5cf6,#6d28d9);border-color:#8b5cf6;color:#fff}
  .custom{border-top:1px solid var(--line);padding-top:11px;font-size:12.5px;color:var(--muted)}
  .custom .row{display:flex;align-items:center;gap:8px;margin-bottom:8px}
  .custom input[type=date]{background:#1a2336;border:1px solid var(--line);color:var(--txt);
    border-radius:8px;padding:6px 8px;font-size:12.5px;flex:1;color-scheme:dark}
  .custom label{display:flex;align-items:center;gap:7px;cursor:pointer;margin-bottom:10px;color:var(--txt)}
  .applybtn{width:100%;background:linear-gradient(135deg,#8b5cf6,#22d3ee);border:none;color:#fff;border-radius:9px;padding:10px;
    font-size:13px;font-weight:700;cursor:pointer;box-shadow:0 6px 16px rgba(139,92,255,.4)}
  /* cards */
  .kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:13px;margin-bottom:13px}
  .pcards{display:grid;grid-template-columns:repeat(3,1fr);gap:13px;margin-bottom:13px}
  .card{background:linear-gradient(180deg,#161e31,#121a2b);border:1px solid var(--line);border-radius:16px;padding:15px 17px;
    box-shadow:0 8px 24px rgba(0,0,0,.28)}
  .cardhead{display:flex;align-items:center;gap:11px;margin-bottom:11px}
  .lbl{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:600;display:flex;align-items:center;gap:7px}
  .big{font-size:28px;font-weight:800;margin:2px 0 2px;letter-spacing:.2px}
  .sub{font-size:12.5px;color:var(--muted)}
  .delta{font-size:12px;font-weight:700;padding:1px 7px;border-radius:20px}
  .delta.up{color:var(--up);background:rgba(52,211,153,.14)}
  .delta.down{color:var(--down);background:rgba(251,113,133,.14)}
  .delta.flat{color:var(--muted);background:rgba(147,161,189,.14)}
  .delta.hide{display:none}
  /* listings */
  .listings{background:linear-gradient(180deg,#161e31,#121a2b);border:1px solid var(--line);border-radius:16px;padding:13px 17px;margin-bottom:13px;
    display:flex;align-items:center;gap:20px;flex-wrap:wrap;box-shadow:0 8px 24px rgba(0,0,0,.28)}
  .listings .t{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:600}
  .listings .it{font-size:14px;color:var(--muted)}.listings .it b{font-size:18px;font-weight:800;color:var(--txt);margin-left:3px}
  .listings .cap{margin-left:auto;font-size:11px;color:var(--muted)}
  /* charts + table */
  .grid2{display:grid;grid-template-columns:1.6fr 1fr;gap:13px;margin-bottom:13px}
  .panel{background:linear-gradient(180deg,#161e31,#121a2b);border:1px solid var(--line);border-radius:16px;padding:15px 17px;box-shadow:0 8px 24px rgba(0,0,0,.28)}
  .panel h2{font-size:12.5px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:13px;font-weight:700;display:flex;align-items:center;gap:9px}
  canvas{max-height:270px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line)}
  th{color:var(--muted);font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
  td.r,th.r{text-align:right}
  .tag{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700}
  .tag.Depop{background:rgba(255,77,94,.16);color:#ff8a96}
  .tag.Vinted{background:rgba(35,211,191,.16);color:#5fe6d6}
  .tag.Wholesale{background:rgba(249,115,22,.16);color:#fb9a4b}
  .empty{color:var(--muted);font-size:13px;text-align:center;padding:26px}
  .foot{color:var(--muted);font-size:12px;margin-top:16px;line-height:1.6}
  @media(max-width:860px){.kpis{grid-template-columns:1fr}.pcards{grid-template-columns:1fr}.grid2{grid-template-columns:1fr}
    body{padding:14px}
    .panelpop{width:90vw;position:fixed;top:74px;left:50%;right:auto;transform:translateX(-50%);max-height:78vh;overflow:auto}}
</style>
</head>
<body>
<header>
  <h1><span class="logo"></span>FM <span class="g">Sales Dashboard</span></h1>
  <div class="rangewrap">
    <button id="rangeBtn" class="rangebtn"><span class="cal">&#128197;</span><span id="rangeLabel">Today</span> &#9662;</button>
    <div id="rangePanel" class="panelpop hidden">
      <div class="presets" id="presets"></div>
      <div class="custom">
        <div class="row"><span>From</span><input type="date" id="cFrom"></div>
        <div class="row"><span>To</span><input type="date" id="cTo"></div>
        <label><input type="checkbox" id="cmp"> Compare to previous period</label>
        <button class="applybtn" id="applyBtn">Apply</button>
      </div>
    </div>
  </div>
</header>
<div class="legend">
  Depop &amp; Vinted &middot; auto-generated from Crosslist
  <span class="pill"><span class="dot" style="background:var(--depop)"></span>Depop</span>
  <span class="pill"><span class="dot" style="background:var(--vinted)"></span>Vinted</span>
  <span class="pill"><span class="dot" style="background:#f97316"></span>Wholesale</span>
</div>

<div class="kpis">
  <div class="card">
    <div class="cardhead"><span class="badge b-amber">__IC_NOTE__</span><span class="lbl">Revenue <span id="dRev" class="delta hide"></span></span></div>
    <div class="big" id="kRev">&pound;0.00</div><div class="sub" id="sRev">in range</div>
  </div>
  <div class="card">
    <div class="cardhead"><span class="badge b-blue">__IC_BAG__</span><span class="lbl">Units sold <span id="dU" class="delta hide"></span></span></div>
    <div class="big" id="kU">0</div><div class="sub" id="sU">in range</div>
  </div>
  <div class="card">
    <div class="cardhead"><span class="badge b-purple">__IC_TREND__</span><span class="lbl">Avg sale <span id="dA" class="delta hide"></span></span></div>
    <div class="big" id="kA">&pound;0.00</div><div class="sub">per item</div>
  </div>
</div>

<div class="pcards">
  <div class="card">
    <div class="cardhead"><span class="badge b-red">__IC_TAG__</span><span class="lbl">Depop <span id="dDep" class="delta hide"></span></span></div>
    <div class="big" id="kDepRev">&pound;0.00</div><div class="sub" id="kDepU">0 units</div>
  </div>
  <div class="card">
    <div class="cardhead"><span class="badge b-teal">__IC_TAG__</span><span class="lbl">Vinted <span id="dVin" class="delta hide"></span></span></div>
    <div class="big" id="kVinRev">&pound;0.00</div><div class="sub" id="kVinU">0 units</div>
  </div>
  <div class="card">
    <div class="cardhead"><span class="badge b-orange">__IC_BOX__</span><span class="lbl">Wholesale <span id="dWh" class="delta hide"></span></span></div>
    <div class="big" id="kWhRev">&pound;0.00</div><div class="sub" id="kWhU">0 units</div>
  </div>
</div>

<div class="listings">
  <span class="badge sm b-cyan">__IC_TAG__</span>
  <span class="t">Live listings</span>
  <span class="it"><span class="dot" style="background:var(--depop)"></span> Depop <b id="lDep">&mdash;</b></span>
  <span class="it"><span class="dot" style="background:var(--vinted)"></span> Vinted <b id="lVin">&mdash;</b></span>
  <span class="it">Total <b id="lTot">&mdash;</b></span>
  <span class="cap" id="lCap"></span>
</div>

<div class="grid2">
  <div class="panel"><h2 id="tsTitle">Revenue over time</h2><canvas id="tsChart"></canvas></div>
  <div class="panel"><h2>Platform split</h2><canvas id="splitChart"></canvas></div>
</div>

<div class="panel" style="margin-bottom:13px">
  <h2 id="tblTitle">Sales in range</h2>
  <div style="max-height:330px;overflow:auto">
    <table id="salesTbl"><thead><tr><th>Date</th><th>Time</th><th>Item</th><th>Platform</th><th class="r">Price</th></tr></thead><tbody></tbody></table>
  </div>
</div>

<div class="foot" id="foot"></div>

<script>
const SALES = __SALES_JSON__;
const LISTINGS = __LISTINGS_JSON__;
const GENERATED_AT = "__GENERATED_AT__";

const DEPOP="#ff4d5e", VINTED="#23d3bf", WHOLE="#f97316";
const TICK="#93a1bd", GRID="#26314a", CARDBG="#141c2e";
const gbp = n => "\u00a3" + (n||0).toLocaleString("en-GB",{minimumFractionDigits:2,maximumFractionDigits:2});
const pd = s => { const [y,m,d]=s.split("-").map(Number); return new Date(y,m-1,d); };
const addDays=(d,n)=>{const x=new Date(d);x.setDate(x.getDate()+n);return x;};
const dayMs=86400000;
const today=new Date(); today.setHours(0,0,0,0);
const monday=d=>{const x=new Date(d);x.setHours(0,0,0,0);const wd=(x.getDay()+6)%7;x.setDate(x.getDate()-wd);return x;};
const som=d=>new Date(d.getFullYear(),d.getMonth(),1);
const soy=d=>new Date(d.getFullYear(),0,1);
const minSale=SALES.length?SALES.reduce((a,s)=>{const d=pd(s.date);return d<a?d:a;},pd(SALES[0].date)):today;
const fmtShort=d=>d.toLocaleDateString("en-GB",{day:"numeric",month:"short"});
const fmtFull=d=>d.toLocaleDateString("en-GB",{weekday:"short",day:"numeric",month:"short",year:"numeric"});
const iso=d=>d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");

const PRESETS=[
  ["Today",()=>[today,today]],
  ["Yesterday",()=>[addDays(today,-1),addDays(today,-1)]],
  ["Last 7 days",()=>[addDays(today,-6),today]],
  ["Last 30 days",()=>[addDays(today,-29),today]],
  ["Last 90 days",()=>[addDays(today,-89),today]],
  ["Week to date",()=>[monday(today),today]],
  ["Month to date",()=>[som(today),today]],
  ["Last month",()=>{const f=new Date(today.getFullYear(),today.getMonth()-1,1);const l=new Date(today.getFullYear(),today.getMonth(),0);return [f,l];}],
  ["Year to date",()=>[soy(today),today]],
  ["All time",()=>[minSale,today]],
];

let state={start:today,end:today,label:"Today",compare:false};

function aggregate(start,end){
  let rev=0,u=0,dR=0,dU=0,vR=0,vU=0,wR=0,wU=0;
  for(const s of SALES){const d=pd(s.date); if(d<start||d>end) continue;
    rev+=s.price;u++;
    if(s.platform==="Depop"){dR+=s.price;dU++;}
    else if(s.platform==="Wholesale"){wR+=s.price;wU++;}
    else {vR+=s.price;vU++;}}
  return {rev,u,dR,dU,vR,vU,wR,wU,avg:u?rev/u:0};
}
function setDelta(el,cur,prev){
  if(!state.compare){el.className="delta hide";return;}
  el.className="delta";
  if(prev===0){ if(cur===0){el.classList.add("flat");el.textContent="0%";} else {el.classList.add("up");el.textContent="\u25b2 new";} return;}
  const p=(cur-prev)/prev*100; const r=Math.abs(p)<0.05;
  el.classList.add(r?"flat":(p>0?"up":"down"));
  el.textContent=(r?"":(p>0?"\u25b2 ":"\u25bc "))+Math.abs(p).toFixed(1)+"%";
}

let tsChart,splitChart;
function buckets(start,end){
  const span=Math.round((end-start)/dayMs)+1; let unit,labels=[],keys=[];
  if(span<=31){unit="day"; for(let d=new Date(start);d<=end;d=addDays(d,1)){labels.push(fmtShort(d));keys.push([new Date(d),new Date(d)]);}}
  else if(span<=182){unit="week"; for(let d=monday(start);d<=end;d=addDays(d,7)){labels.push(fmtShort(d));keys.push([new Date(d),addDays(d,6)]);}}
  else{unit="month"; let d=som(start); while(d<=end){const e=new Date(d.getFullYear(),d.getMonth()+1,0);labels.push(d.toLocaleDateString("en-GB",{month:"short",year:"2-digit"}));keys.push([new Date(d),e]);d=new Date(d.getFullYear(),d.getMonth()+1,1);}}
  const dep=keys.map(()=>0),vin=keys.map(()=>0),whole=keys.map(()=>0);
  for(const s of SALES){const sd=pd(s.date); if(sd<start||sd>end) continue;
    for(let i=0;i<keys.length;i++){if(sd>=keys[i][0]&&sd<=keys[i][1]){if(s.platform==="Depop")dep[i]+=s.price;else if(s.platform==="Wholesale")whole[i]+=s.price;else vin[i]+=s.price;break;}}}
  return {unit,labels,dep,vin,whole};
}
function render(){
  const cur=aggregate(state.start,state.end);
  const span=Math.round((state.end-state.start)/dayMs)+1;
  const pe=addDays(state.start,-1), ps=addDays(pe,-(span-1));
  const prev=aggregate(ps,pe);
  document.getElementById("kRev").textContent=gbp(cur.rev);
  document.getElementById("kU").textContent=cur.u;
  document.getElementById("kA").textContent=gbp(cur.avg);
  document.getElementById("kDepRev").textContent=gbp(cur.dR);
  document.getElementById("kDepU").textContent=cur.dU+" unit"+(cur.dU===1?"":"s");
  document.getElementById("kVinRev").textContent=gbp(cur.vR);
  document.getElementById("kVinU").textContent=cur.vU+" unit"+(cur.vU===1?"":"s");
  document.getElementById("kWhRev").textContent=gbp(cur.wR);
  document.getElementById("kWhU").textContent=cur.wU+" unit"+(cur.wU===1?"":"s");
  const sub = state.compare ? ("vs "+gbp(prev.rev)+" prev") : ("in "+state.label.toLowerCase());
  document.getElementById("sRev").textContent=sub;
  document.getElementById("sU").textContent=state.compare?("vs "+prev.u+" prev"):("in "+state.label.toLowerCase());
  setDelta(document.getElementById("dRev"),cur.rev,prev.rev);
  setDelta(document.getElementById("dU"),cur.u,prev.u);
  setDelta(document.getElementById("dA"),cur.avg,prev.avg);
  setDelta(document.getElementById("dDep"),cur.dR,prev.dR);
  setDelta(document.getElementById("dVin"),cur.vR,prev.vR);
  setDelta(document.getElementById("dWh"),cur.wR,prev.wR);

  const b=buckets(state.start,state.end);
  document.getElementById("tsTitle").textContent="Revenue over time \u00b7 by "+b.unit;
  if(!tsChart){
    tsChart=new Chart(document.getElementById("tsChart"),{type:"bar",
      data:{labels:b.labels,datasets:[{label:"Depop",data:b.dep,backgroundColor:DEPOP,stack:"s",borderRadius:4},{label:"Vinted",data:b.vin,backgroundColor:VINTED,stack:"s",borderRadius:4},{label:"Wholesale",data:b.whole,backgroundColor:WHOLE,stack:"s",borderRadius:4}]},
      options:{responsive:true,plugins:{legend:{labels:{color:TICK}}},
        scales:{x:{stacked:true,ticks:{color:TICK,maxRotation:0,autoSkip:true,maxTicksLimit:12},grid:{display:false}},
          y:{stacked:true,ticks:{color:TICK,callback:v=>"\u00a3"+v},grid:{color:GRID}}}}});
  } else { tsChart.data.labels=b.labels; tsChart.data.datasets[0].data=b.dep; tsChart.data.datasets[1].data=b.vin; tsChart.data.datasets[2].data=b.whole; tsChart.update(); }

  if(!splitChart){
    splitChart=new Chart(document.getElementById("splitChart"),{type:"doughnut",
      data:{labels:["Depop","Vinted","Wholesale"],datasets:[{data:[cur.dR,cur.vR,cur.wR],backgroundColor:[DEPOP,VINTED,WHOLE],borderColor:CARDBG,borderWidth:3}]},
      options:{responsive:true,cutout:"64%",plugins:{legend:{position:"bottom",labels:{color:TICK,padding:16}}}}});
  } else { splitChart.data.datasets[0].data=[cur.dR,cur.vR,cur.wR]; splitChart.update(); }

  const rows=SALES.filter(s=>{const d=pd(s.date);return d>=state.start&&d<=state.end;})
    .sort((a,b)=>(b.date+b.time).localeCompare(a.date+a.time));
  const tb=document.querySelector("#salesTbl tbody");
  document.getElementById("tblTitle").textContent="Sales in range ("+rows.length+")";
  tb.innerHTML = rows.length? rows.map(s=>`<tr><td>${pd(s.date).toLocaleDateString("en-GB",{day:"2-digit",month:"2-digit",year:"2-digit"})}</td><td>${s.time}</td><td>${s.title||s.sku}</td><td><span class="tag ${s.platform}">${s.platform}</span></td><td class="r">${gbp(s.price)}</td></tr>`).join("")
    : `<tr><td colspan="5"><div class="empty">No sales in this range yet</div></td></tr>`;
}
function setRange(start,end,label){
  state.start=start;state.end=end;state.label=label;
  document.getElementById("rangeLabel").textContent = (start.getTime()===end.getTime())
    ? fmtFull(start) : (fmtShort(start)+" \u2013 "+fmtShort(end)+" "+end.getFullYear());
  [...document.querySelectorAll(".preset")].forEach(p=>p.classList.toggle("active",p.dataset.label===label));
  render();
}

// listings snapshot
document.getElementById("lDep").innerHTML = LISTINGS.depopLive!=null?LISTINGS.depopLive:"&mdash;";
document.getElementById("lVin").innerHTML = LISTINGS.vintedLive!=null?LISTINGS.vintedLive:"&mdash;";
document.getElementById("lTot").innerHTML = LISTINGS.total!=null?LISTINGS.total:"&mdash;";
document.getElementById("lCap").textContent = LISTINGS.capturedAt? ("as of "+LISTINGS.capturedAt) : "updated on next refresh";

// build presets UI
const pc=document.getElementById("presets");
PRESETS.forEach(([label,fn])=>{const b=document.createElement("button");b.className="preset";b.dataset.label=label;b.textContent=label;
  b.onclick=()=>{const [s,e]=fn();document.getElementById("rangePanel").classList.add("hidden");setRange(s,e,label);};pc.appendChild(b);});
const btn=document.getElementById("rangeBtn"),panel=document.getElementById("rangePanel");
btn.onclick=e=>{e.stopPropagation();panel.classList.toggle("hidden");};
document.addEventListener("click",e=>{if(!panel.contains(e.target)&&e.target!==btn)panel.classList.add("hidden");});
document.getElementById("cmp").onchange=e=>{state.compare=e.target.checked;render();};
document.getElementById("applyBtn").onclick=()=>{
  const f=document.getElementById("cFrom").value,t=document.getElementById("cTo").value;
  if(!f||!t)return; let s=pd(f),en=pd(t); if(s>en){const tmp=s;s=en;en=tmp;}
  panel.classList.add("hidden"); setRange(s,en,"Custom");
};
document.getElementById("cFrom").value=iso(today);
document.getElementById("cTo").value=iso(today);

document.getElementById("foot").innerHTML =
  SALES.length+" sales tracked &middot; data store: fm_sales.csv &middot; generated "+GENERATED_AT+
  " &middot; refreshes from Crosslist at 8am, 3pm, 8pm &amp; midnight";

setRange(today,today,"Today");
</script>
</body>
</html>
"""

def _agg(sales, start, end):
    dR = dU = vR = vU = wR = wU = 0
    for s in sales:
        try:
            y, m, d = map(int, s["date"].split("-"))
            sd = datetime.date(y, m, d)
        except Exception:
            continue
        if sd < start or sd > end:
            continue
        if s["platform"] == "Depop":
            dR += s["price"]; dU += 1
        elif s["platform"] == "Wholesale":
            wR += s["price"]; wU += 1
        else:
            vR += s["price"]; vU += 1
    return {"rev": round(dR + vR + wR, 2), "u": dU + vU + wU,
            "depop": {"rev": round(dR, 2), "u": dU},
            "vinted": {"rev": round(vR, 2), "u": vU},
            "wholesale": {"rev": round(wR, 2), "u": wU}}

def compute_summary(sales, listings, gen):
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())  # Monday
    month_start = today.replace(day=1)
    dates = []
    for s in sales:
        try:
            y, m, d = map(int, s["date"].split("-"))
            dates.append(datetime.date(y, m, d))
        except Exception:
            pass
    min_date = min(dates) if dates else today
    return {
        "generated": gen,
        "currency": "\u00a3",
        "today": _agg(sales, today, today),
        "week": _agg(sales, week_start, today),
        "month": _agg(sales, month_start, today),
        "all": _agg(sales, min_date, today),
        "listings": {
            "total": listings.get("total"),
            "depop": listings.get("depopLive"),
            "vinted": listings.get("vintedLive"),
            "capturedAt": listings.get("capturedAt"),
        },
    }

def main():
    sales = load_sales()
    listings = load_listings()
    gen = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    html = (TEMPLATE
            .replace("__IC_NOTE__", IC_NOTE)
            .replace("__IC_BAG__", IC_BAG)
            .replace("__IC_TREND__", IC_TREND)
            .replace("__IC_TAG__", IC_TAG)
            .replace("__IC_BOX__", IC_BOX)
            .replace("__SALES_JSON__", json.dumps(sales))
            .replace("__LISTINGS_JSON__", json.dumps(listings))
            .replace("__GENERATED_AT__", gen))
    with open(OUT_PATH, "w") as f:
        f.write(html)
    summary = compute_summary(sales, listings, gen)
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f)
    print("Wrote", OUT_PATH, "and", SUMMARY_PATH, "with", len(sales), "sales;", "listings:", listings)

if __name__ == "__main__":
    main()
