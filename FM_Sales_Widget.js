// ===== FM Sales — premium home-screen widget (Scriptable, iOS) =====
// Reads the live summary feed published by your dashboard and shows today's
// revenue, Depop/Vinted split, this month + live listings. Tap = open dashboard.
// Supports Small / Medium / Large. Auto-refreshes ~every 30 min.

const URL  = "https://notanotherwholesale-sudo.github.io/fm-dashboard/summary.json";
const SITE = "https://notanotherwholesale-sudo.github.io/fm-dashboard/";

// premium jewel-tone palette (matches the website)
const BG_TOP = new Color("#0b1020");
const BG_BOT = new Color("#161f33");
const CARD   = new Color("#1a2336");
const LINE   = new Color("#26314a");
const TXT    = new Color("#f2f6fc");
const MUTED  = new Color("#93a1bd");
const DEPOP  = new Color("#ff4d5e");
const VINTED = new Color("#23d3bf");
const ACCENT = new Color("#8b5cf6");
const CYAN   = new Color("#22d3ee");
const AMBER  = new Color("#ffb020");
const BLUE   = new Color("#3b82f6");
const PURPLE = new Color("#a78bfa");

function money(n){ n = Number(n||0); return "\u00a3" + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
function money0(n){ n = Number(n||0); return "\u00a3" + Math.round(n).toLocaleString("en-GB"); }

async function getData(){
  try{ const r = new Request(URL); r.timeoutInterval = 15; return await r.loadJSON(); }
  catch(e){ return null; }
}
function symImg(name, size){
  try{ const s = SFSymbol.named(name); s.applyFont(Font.boldSystemFont(size)); return s.image; }
  catch(e){ return null; }
}
function addIcon(stack, name, size, color){
  const img = symImg(name, size); if(!img) return;
  const el = stack.addImage(img); el.imageSize = new Size(size, size); el.tintColor = color;
}
function badge(stack, name, size, color){
  // gradient-ish rounded icon tile
  const b = stack.addStack(); b.size = new Size(size+14, size+14); b.cornerRadius = 9;
  b.backgroundColor = new Color(color.hex, 0.18); b.centerAlignContent();
  addIcon(b, name, size, color);
  return b;
}
function chip(parent, name, label, value, color, w){
  const c = parent.addStack(); c.layoutVertically(); c.size = new Size(w, 60);
  c.backgroundColor = CARD; c.cornerRadius = 13; c.setPadding(9, 10, 9, 10);
  c.borderWidth = 1; c.borderColor = LINE;
  const top = c.addStack(); top.centerAlignContent();
  addIcon(top, name, 10, color); top.addSpacer(5);
  const l = top.addText(label); l.textColor = MUTED; l.font = Font.semiboldSystemFont(9);
  c.addSpacer(3);
  const v = c.addText(value); v.textColor = TXT; v.font = Font.boldSystemFont(15);
  v.minimumScaleFactor = 0.6; v.lineLimit = 1;
}
function splitBar(parent, dep, vin, who, width){
  const total = (dep + vin + who) || 1;
  const bar = parent.addStack(); bar.size = new Size(width, 10); bar.cornerRadius = 5;
  bar.backgroundColor = LINE;
  let dW = dep > 0 ? Math.max(4, Math.round(width * dep / total)) : 0;
  let wW = who > 0 ? Math.max(4, Math.round(width * who / total)) : 0;
  let vW = width - dW - wW; if(vW < 0) vW = 0;
  const d = bar.addStack(); d.size = new Size(dW, 10); d.backgroundColor = DEPOP;
  const v = bar.addStack(); v.size = new Size(vW, 10); v.backgroundColor = VINTED;
  const wo = bar.addStack(); wo.size = new Size(wW, 10); wo.backgroundColor = new Color("#f97316");
}
function legendItem(stack, color, label, rev, u){
  const s = stack.addStack(); s.centerAlignContent();
  addIcon(s, "circle.fill", 9, color); s.addSpacer(5);
  const t = s.addText(label + "  " + money(rev) + "  (" + u + ")"); t.textColor = TXT; t.font = Font.mediumSystemFont(12.5);
}

async function main(){
  const data = await getData();
  const fam = (typeof config !== "undefined" && config.widgetFamily) ? config.widgetFamily : "large";
  const w = new ListWidget();
  const g = new LinearGradient(); g.colors = [BG_TOP, BG_BOT]; g.locations = [0, 1];
  g.startPoint = new Point(0, 0); g.endPoint = new Point(0.6, 1);
  w.backgroundGradient = g;
  w.setPadding(15, 16, 15, 16);
  w.url = SITE;

  if(!data){
    const t = w.addText("FM SALES"); t.textColor = ACCENT; t.font = Font.heavySystemFont(13);
    w.addSpacer(6);
    const e = w.addText("Couldn't load data.\nTap to open dashboard."); e.textColor = MUTED; e.font = Font.systemFont(12);
    finish(w, fam); return;
  }

  const today = data.today, month = data.month || {}, week = data.week || {}, L = data.listings || {};

  // header
  const head = w.addStack(); head.centerAlignContent();
  addIcon(head, "sparkles", 13, CYAN); head.addSpacer(6);
  const brand = head.addText("FM SALES"); brand.textColor = TXT; brand.font = Font.heavySystemFont(13);
  head.addSpacer();
  const pill = head.addStack(); pill.backgroundColor = new Color(ACCENT.hex, 0.20); pill.cornerRadius = 8;
  pill.setPadding(3, 8, 3, 8); pill.centerAlignContent();
  const pt = pill.addText("TODAY"); pt.textColor = PURPLE; pt.font = Font.boldSystemFont(9);
  w.addSpacer(fam === "small" ? 9 : 12);

  // hero
  const hero = w.addStack(); hero.centerAlignContent();
  badge(hero, "sterlingsign.circle.fill", fam === "small" ? 15 : 17, AMBER);
  hero.addSpacer(10);
  const hc = hero.addStack(); hc.layoutVertically();
  const rev = hc.addText(money(today.rev)); rev.textColor = TXT; rev.font = Font.boldSystemFont(fam === "small" ? 25 : 33);
  const un = hc.addStack(); un.centerAlignContent();
  addIcon(un, "bag.fill", 10, MUTED); un.addSpacer(5);
  const ut = un.addText(today.u + (today.u === 1 ? " item today" : " items today")); ut.textColor = MUTED; ut.font = Font.systemFont(11);

  if(fam === "small"){
    w.addSpacer(9);
    splitBar(w, today.depop.rev, today.vinted.rev, (today.wholesale||{rev:0}).rev, 150);
    w.addSpacer(7);
    const r = w.addStack(); r.centerAlignContent();
    addIcon(r, "circle.fill", 8, DEPOP); r.addSpacer(4);
    const a = r.addText(money0(today.depop.rev)); a.textColor = TXT; a.font = Font.mediumSystemFont(12);
    r.addSpacer(12);
    addIcon(r, "circle.fill", 8, VINTED); r.addSpacer(4);
    const b = r.addText(money0(today.vinted.rev)); b.textColor = TXT; b.font = Font.mediumSystemFont(12);
    finish(w, fam); return;
  }

  w.addSpacer(12);
  const barW = fam === "large" ? 300 : 300;
  splitBar(w, today.depop.rev, today.vinted.rev, (today.wholesale||{rev:0}).rev, barW);
  w.addSpacer(8);
  const lg = w.addStack(); lg.centerAlignContent();
  legendItem(lg, DEPOP, "Depop", today.depop.rev, today.depop.u);
  lg.addSpacer();
  legendItem(lg, VINTED, "Vinted", today.vinted.rev, today.vinted.u);
  if((today.wholesale||{u:0}).u > 0){
    w.addSpacer(5);
    const wl = w.addStack(); legendItem(wl, new Color("#f97316"), "Wholesale", today.wholesale.rev, today.wholesale.u);
  }

  if(fam === "large"){
    w.addSpacer(14);
    const avg = today.u ? today.rev / today.u : (month.u ? month.rev / month.u : 0);
    const row = w.addStack(); row.spacing = 9;
    chip(row, "calendar.badge.clock", "THIS WEEK", money0(week.rev), CYAN, 90);
    chip(row, "calendar", "THIS MONTH", money0(month.rev), ACCENT, 90);
    chip(row, "chart.line.uptrend.xyaxis", "AVG SALE", money(avg), AMBER, 90);
    w.addSpacer(12);
    const lr = w.addStack(); lr.centerAlignContent(); lr.backgroundColor = CARD; lr.cornerRadius = 13;
    lr.setPadding(9, 12, 9, 12); lr.borderWidth = 1; lr.borderColor = LINE;
    addIcon(lr, "tag.fill", 12, CYAN); lr.addSpacer(7);
    const lt = lr.addText("Live listings"); lt.textColor = MUTED; lt.font = Font.semiboldSystemFont(11);
    lr.addSpacer();
    const txt = (L.depop != null) ? ("D " + L.depop + "   V " + L.vinted + "   \u00b7 " + L.total)
                                  : (L.total != null ? ("" + L.total) : "\u2014");
    const lv = lr.addText(txt); lv.textColor = TXT; lv.font = Font.boldSystemFont(12);
  } else {
    w.addSpacer(11);
    const ml = w.addStack(); ml.centerAlignContent();
    addIcon(ml, "calendar", 10, ACCENT); ml.addSpacer(5);
    const m = ml.addText("Month " + money0(month.rev) + "  \u00b7  " + (month.u || 0)); m.textColor = MUTED; m.font = Font.systemFont(11);
    ml.addSpacer();
    addIcon(ml, "tag.fill", 10, CYAN); ml.addSpacer(5);
    const li = ml.addText(L.total != null ? (L.total + " live") : "\u2014"); li.textColor = MUTED; li.font = Font.systemFont(11);
  }

  w.addSpacer();
  const ft = w.addStack(); ft.centerAlignContent();
  addIcon(ft, "clock", 9, MUTED); ft.addSpacer(4);
  const f = ft.addText("Updated " + (data.generated || "")); f.textColor = MUTED; f.font = Font.systemFont(9);

  finish(w, fam);
}

function finish(w, fam){
  w.refreshAfterDate = new Date(Date.now() + 30*60*1000);
  if(typeof config !== "undefined" && config.runsInWidget){ Script.setWidget(w); }
  else if(fam === "small"){ w.presentSmall(); }
  else if(fam === "medium"){ w.presentMedium(); }
  else { w.presentLarge(); }
  Script.complete();
}

await main();
