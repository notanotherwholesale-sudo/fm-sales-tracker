#!/usr/bin/env python3
"""
FM Sales Tracker — email ingestion.

Replaces the old Crosslist/Chrome scraping. Reads Depop & Vinted "you made a
sale" emails over Gmail IMAP, parses each into the 6-col schema, dedupes against
the append-only store, and appends new rows. No browser, no laptop — designed to
run headless in GitHub Actions.

Usage:
  GMAIL_USER=...  GMAIL_APP_PASSWORD=...  python3 ingest.py            # full run
  GMAIL_USER=...  GMAIL_APP_PASSWORD=...  python3 ingest.py --dump 5   # debug: print recent emails so the parsers can be tuned

State files (committed back to the repo each run, so state survives between runs):
  fm_sales.csv        append-only store        (date,time,sku,title,platform,price)
  processed_ids.json  Gmail Message-IDs already parsed (cheap skip on re-runs)
  collisions.csv      cross-platform SKU collisions flagged for human review (§4.6)
"""
import csv, json, os, re, sys, imaplib, email, datetime, html
from email.header import decode_header, make_header

try:
    from zoneinfo import ZoneInfo
    LONDON = ZoneInfo("Europe/London")   # sale dates/times in UK local time, regardless of runner TZ
except Exception:
    LONDON = None

FOLDER = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(FOLDER, "fm_sales.csv")
PROCESSED_PATH = os.path.join(FOLDER, "processed_ids.json")
COLLISIONS_PATH = os.path.join(FOLDER, "collisions.csv")

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
FIELDS = ["date", "time", "sku", "title", "platform", "price"]

# --------------------------------------------------------------------------- #
# Email -> sale parsing
#
# NOTE: the From/subject matchers below are robust, but the title/price/date
# regexes are PROVISIONAL until tuned against one real Depop email and one real
# Vinted email. Run `ingest.py --dump 5` (or forward samples) to finalise them.
# Each parser returns a dict {date,time,sku,title,platform,price} or None.
# --------------------------------------------------------------------------- #

class ParseError(Exception):
    """Raised when an email IS a sale notification but its fields can't be extracted
    (a real problem worth flagging) — as opposed to a non-sale email, which parsers
    skip silently by returning None."""


def _money(s):
    """'£18.50' / '18,50 £' / 'GBP 18.5' -> 18.50 (float) or None."""
    if not s:
        return None
    s = s.replace("£", "").replace("GBP", "").replace("EUR", "").strip()
    s = s.replace("\xa0", " ").strip()
    # handle both 18.50 and 18,50 decimal styles
    m = re.search(r"(\d+)[.,](\d{2})\b", s)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.search(r"\b(\d+)\b", s)
    return float(m.group(1)) if m else None


def _sku_from_title(title):
    m = re.match(r"\s*(\d+)\b", title or "")
    return m.group(1) if m else ""


def _to_iso_date(s):
    """Accept DD/MM/YYYY, YYYY-MM-DD, '14 Jun 2026' -> YYYY-MM-DD, else None."""
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_depop(subject, body, sent_dt):
    """Depop 'sale confirmation' email (subject: 'Your [Evri shipping label and]
    sale confirmation for @buyer'). Uses 'Item price' = the actual sale price.
    Returns None for payout ('£X is about to be credited') and all other Depop mail.
    Note: Depop truncates long titles with '...'; the leading SKU stays intact."""
    if "sale confirmation" not in subject.lower():
        return None  # payout / shipping-only / other Depop mail — not a sale, skip silently
    # Title is the rest of the line after 'image'; captured independently of price
    # because clothing items insert a 'Size:' line between the title and the £.
    title = _first(body, [r"Order details\s+image\s+([^\n£]+)"])
    price = _money(_first(body, [r"Item price\s*£\s*([\d.,]+)"]))
    if not title or price is None:
        raise ParseError("Depop sale confirmation but couldn't extract title/price")
    title = re.sub(r"\.{2,}$", "", title.strip()).strip()   # drop trailing '...'
    return _row(sent_dt.strftime("%Y-%m-%d"), sent_dt.strftime("%H:%M"), title, "Depop", price)


def parse_vinted(subject, body, sent_dt):
    """Vinted sale email (subject: 'You've sold an item on Vinted').
    Body: '<buyer> has bought  <title>  £<price>'. Full title, price = sale price.
    Returns None for offers / order updates / 'order is completed' notifications."""
    if "sold an item" not in subject.lower():
        return None  # offer / order update / 'completed' / shipping label — skip silently
    m = re.search(r"has bought\s+(.+?)\s+£\s*([\d.,]+)", body, re.S)
    if not m:
        raise ParseError("Vinted sold-item email but couldn't extract title/price")
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    price = _money(m.group(2))
    if not title or price is None:
        return None
    return _row(sent_dt.strftime("%Y-%m-%d"), sent_dt.strftime("%H:%M"), title, "Vinted", price)


# From-address / subject signatures -> parser. Order matters (first match wins).
PARSERS = [
    ("Depop",  lambda frm, subj: "depop" in frm,  parse_depop),
    ("Vinted", lambda frm, subj: "vinted" in frm, parse_vinted),
]


def _first(text, patterns):
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1)
    return None


def _row(date, time, title, platform, price):
    return {
        "date": date, "time": time, "sku": _sku_from_title(title),
        "title": title.strip(), "platform": platform, "price": round(float(price), 2),
    }


# --------------------------------------------------------------------------- #
# IMAP
# --------------------------------------------------------------------------- #

def _decode(s):
    try:
        return str(make_header(decode_header(s or "")))
    except Exception:
        return s or ""


def _clean_body(s):
    """Strip the invisible preheader padding Depop/Vinted stuff their emails with,
    decode HTML entities, and collapse runs of spaces — so the parsers see plain text."""
    for ch in ("­", "͏", "‌", "​", "﻿", " ", "‎", "‏"):
        s = s.replace(ch, " ")
    s = html.unescape(s)
    return re.sub(r"[ \t]+", " ", s)


def _body_text(msg):
    """Prefer text/plain; fall back to a crude HTML-stripped text/html."""
    plain, html = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.get("Content-Disposition", "").startswith("attachment"):
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                txt = payload.decode(part.get_content_charset() or "utf-8", "replace")
            except Exception:
                continue
            if ctype == "text/plain":
                plain += txt + "\n"
            elif ctype == "text/html":
                html += txt + "\n"
    else:
        try:
            txt = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")
        except Exception:
            txt = msg.get_payload() or ""
        if msg.get_content_type() == "text/html":
            html += txt
        else:
            plain += txt
    if plain.strip():
        return plain
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;", " ", html)
    html = re.sub(r"&amp;", "&", html)
    return re.sub(r"[ \t]+", " ", html)


# Sale notifications come from these senders. Searched directly in All Mail, so no
# Gmail filter/label setup is required. The per-email subject check in each parser
# separates real sales from offers / payouts / shipping updates.
SENDERS = ["sold@alerts.depop.com", "vinted"]


def connect():
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        sys.exit("ERROR: set GMAIL_USER and GMAIL_APP_PASSWORD (app password, not your login password).")
    M = imaplib.IMAP4_SSL(IMAP_HOST)
    M.login(user, pw)
    typ, _ = M.select('"[Gmail]/All Mail"', readonly=True)
    if typ != "OK":
        M.logout()
        sys.exit("ERROR: could not open the Gmail mailbox (is IMAP enabled in Gmail settings?).")
    return M


def fetch_messages(M, since_date=None):
    """Fetch sale-sender emails. `since_date` bounds the IMAP search server-side so we
    never pull the whole archive — the precise watermark cut happens later per-email."""
    crit = ["SINCE", since_date.strftime("%d-%b-%Y")] if since_date else []
    seen, out = set(), []
    for sender in SENDERS:
        typ, data = M.search(None, "FROM", sender, *crit)
        ids = data[0].split() if data and data[0] else []
        for num in ids:
            if num in seen:
                continue
            seen.add(num)
            typ, raw = M.fetch(num, "(RFC822)")
            if typ == "OK" and raw and raw[0]:
                out.append(email.message_from_bytes(raw[0][1]))
    return out


# --------------------------------------------------------------------------- #
# Store / dedupe
# --------------------------------------------------------------------------- #

def load_rows():
    rows = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="") as f:
            rows = [r for r in csv.DictReader(f) if r.get("date")]
    return rows


def _row_dt(date_s, time_s):
    """A CSV row's (date,time) -> aware datetime, tolerant of '5:39 PM' / '17:39' / blank."""
    try:
        d = datetime.datetime.strptime((date_s or "").strip(), "%Y-%m-%d")
    except ValueError:
        return None
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            t = datetime.datetime.strptime((time_s or "").strip(), fmt)
            d = d.replace(hour=t.hour, minute=t.minute)
            break
        except ValueError:
            continue
    return d.replace(tzinfo=LONDON) if LONDON else d


def watermark(rows):
    """Latest recorded sale instant. We only ingest emails strictly newer than this,
    so the historical CSV (built from authoritative exports) is never re-ingested as
    truncated-title duplicates."""
    dts = [d for d in (_row_dt(r.get("date"), r.get("time")) for r in rows) if d]
    return max(dts) if dts else None


def _key(r):
    """Dedupe identity for a sale. Prefer SKU (stable) over title, because email titles
    differ from the export titles already stored (Depop truncates; emails add words)."""
    plat = r.get("platform", "")
    date = r.get("date", "")
    price = f"{float(r.get('price') or 0):.2f}"
    sku = (r.get("sku") or "").strip()
    if sku:
        return (plat, date, "sku:" + sku, price)
    title = re.sub(r"\s+", " ", (r.get("title") or "").lower()).strip()
    return (plat, date, title, price)


def append_rows(existing, new_rows):
    # Dedupe new emails against the EXISTING store only — not against each other —
    # so genuine repeat-seller sales (same item/price/day) are each kept (§4.5),
    # while sales already recorded from authoritative exports are never re-added.
    seen = {_key(r) for r in existing}
    added = [r for r in new_rows if _key(r) not in seen]
    if added:
        write_header = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
        with open(CSV_PATH, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if write_header:
                w.writeheader()
            for r in added:
                w.writerow({k: r.get(k, "") for k in FIELDS})
    return added


def report_collisions(all_rows):
    """Same SKU on both Depop and Vinted -> flag (likely relist/oversell, §4.6)."""
    by_sku = {}
    for r in all_rows:
        sku = (r.get("sku") or "").strip()
        if not sku:
            continue
        by_sku.setdefault(sku, set()).add(r.get("platform", ""))
    collisions = sorted(s for s, p in by_sku.items() if len({x for x in p if x}) > 1)
    if collisions:
        with open(COLLISIONS_PATH, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["sku", "platforms", "note"])
            for sku in collisions:
                plats = ",".join(sorted(p for p in by_sku[sku] if p))
                w.writerow([sku, plats, "appears on multiple platforms — review for relist/oversell"])
    return collisions


def load_processed():
    if os.path.exists(PROCESSED_PATH):
        try:
            return set(json.load(open(PROCESSED_PATH)))
        except Exception:
            pass
    return set()


def save_processed(ids):
    json.dump(sorted(ids), open(PROCESSED_PATH, "w"), indent=0)


# --------------------------------------------------------------------------- #
# Run modes
# --------------------------------------------------------------------------- #

def dump(n):
    M = connect()
    since = datetime.datetime.now() - datetime.timedelta(days=21)
    msgs = fetch_messages(M, since_date=since)[-n:]
    M.logout()
    print(f"=== {len(msgs)} most recent sale-sender emails (last 21 days) ===\n")
    for msg in msgs:
        frm = _decode(msg.get("From"))
        subj = _decode(msg.get("Subject"))
        body = _clean_body(_body_text(msg))
        print(f"FROM:    {frm}\nSUBJECT: {subj}\nDATE:    {msg.get('Date')}\nMSG-ID:  {msg.get('Message-ID')}")
        print("BODY (first 1200 chars):")
        print(re.sub(r"\n{3,}", "\n\n", body)[:1200])
        print("\n" + "-" * 72 + "\n")


def run():
    if not (os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD")):
        print("No Gmail credentials set — skipping email ingest this run "
              "(dashboard still rebuilds + publishes from existing data).")
        return 0
    processed = load_processed()
    existing = load_rows()
    wm = watermark(existing)
    if wm:
        print(f"watermark: only ingesting sales after {wm:%Y-%m-%d %H:%M %Z}")
    since = (wm - datetime.timedelta(days=1)) if wm else None

    M = connect()
    msgs = fetch_messages(M, since_date=since)
    M.logout()

    new_rows, parsed_ids, skipped, pre_wm = [], set(), 0, 0
    for msg in msgs:
        mid = msg.get("Message-ID", "")
        if mid and mid in processed:
            continue
        frm = _decode(msg.get("From")).lower()
        subj = _decode(msg.get("Subject"))
        body = _clean_body(_body_text(msg))
        try:
            sent_dt = email.utils.parsedate_to_datetime(msg.get("Date"))
            sent_dt = sent_dt.astimezone(LONDON) if LONDON else sent_dt.astimezone()
        except Exception:
            sent_dt = datetime.datetime.now()
        if wm and sent_dt <= wm:
            pre_wm += 1
            continue
        for name, matches, parser in PARSERS:
            if matches(frm, subj):
                try:
                    row = parser(subj, body, sent_dt)
                except ParseError as e:
                    skipped += 1
                    print(f"  ! {e} — subject: {subj!r}")
                    break
                if row:
                    new_rows.append(row)
                    if mid:
                        parsed_ids.add(mid)
                break

    added = append_rows(existing, new_rows)
    if parsed_ids:
        save_processed(processed | parsed_ids)
    collisions = report_collisions(load_rows())

    print(f"emails scanned: {len(msgs)} | parsed: {len(new_rows)} | "
          f"new rows added: {len(added)} | unparsed: {skipped} | "
          f"sku collisions: {len(collisions)}")
    for r in added:
        print(f"  + {r['date']} {r['time']:<8} {r['platform']:<9} £{r['price']:>6.2f}  {r['title']}")
    return len(added)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        dump(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    else:
        run()
