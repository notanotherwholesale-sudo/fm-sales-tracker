# FM Sales Tracker (cloud, email-driven)

Records every Depop / Vinted sale, rebuilds the phone dashboard, and publishes to
GitHub Pages — **on a schedule, in GitHub's cloud. No laptop, no Chrome, no Cowork.**

Sale emails → Gmail label → GitHub Actions cron → parse → `fm_sales.csv` →
`build_dashboard.py` → GitHub Pages + widget feed.

## How it works
- **`ingest.py`** logs into Gmail over IMAP and searches **All Mail by sender**
  (`sold@alerts.depop.com`, `vinted`) — no Gmail filter/label needed. It keeps only
  genuine sales (Depop "sale confirmation", Vinted "You've sold an item"), skipping
  offers/payouts/shipping updates, parses each into `date,time,sku,title,platform,price`,
  and appends to `fm_sales.csv`. A **watermark** (latest recorded sale) plus
  **SKU-aware dedupe** and processed-Message-ID tracking make every run idempotent and
  self-catch-up after a missed day.
- **`build_dashboard.py`** (unchanged) → `FM_Sales_Dashboard.html` + `summary.json`.
- **`.github/workflows/tracker.yml`** runs the above 4×/day, commits the updated
  CSV back to the repo (the repo *is* the database), and deploys Pages.
- State that survives between runs: `fm_sales.csv`, `processed_ids.json`,
  `collisions.csv` — all committed by the bot each run.

## One-time setup (all done)
1. **Gmail app password** for `francismurayclothing@gmail.com` (the inbox that
   receives Depop/Vinted sale emails) — created under Security → App passwords.
2. **Enable IMAP**: Gmail → Settings → Forwarding and POP/IMAP → **Enable IMAP** →
   Save. (Gmail rejects IMAP logins until this is on.)
3. **GitHub Actions secrets** (Settings → Secrets and variables → Actions):
   - `GMAIL_USER` = `francismurayclothing@gmail.com`
   - `GMAIL_APP_PASSWORD` = the 16-char app password (no spaces)
   - `PAGES_PUSH_TOKEN` = fine-grained PAT with Contents:RW on the public
     `fm-dashboard` repo (publishing target).
4. **Publishing**: this private repo builds the dashboard and pushes the rendered
   `index.html` + `summary.json` to the public `fm-dashboard` repo, which serves
   GitHub Pages at the existing URL (no change to the widget).

Manual run anytime: Actions tab → **FM Sales Tracker** → **Run workflow**.

## Tuning the parsers
The Depop/Vinted From-matchers are solid; the title/price/date regexes are
provisional until checked against real emails. To see exactly what the inbox
contains:

```bash
GMAIL_USER=you@gmail.com GMAIL_APP_PASSWORD=xxxx python3 ingest.py --dump 5
```

Forward one real Depop and one real Vinted sale email, adjust `parse_depop` /
`parse_vinted` in `ingest.py`, and re-run. Vinted is the known weak spot — if its
emails don't carry the price, fall back to a manual export drop for Vinted only.

## Cancellations / returns
Each run also scans Vinted order-update emails for reversals ("This sale has been
cancelled" / failed-delivery "returned to you instead … refund") over a 35-day
lookback, and removes the matching sale so revenue reflects only completed sales.
Depop sends no reversal emails. The generic "delivered — you *could* request a
refund" notice is deliberately ignored (it isn't a reversal).

## Safety
- Credentials live **only** in GitHub Actions secrets — never in the repo.
- Re-runs are idempotent (SKU-aware sale-key dedupe + processed Message-IDs).
- A missed day is caught up automatically — every run re-scans since the watermark.
- June was rebuilt from authoritative platform emails (149 sales / £2,215.39):
  Depop 68 (£937.79) + Vinted 81 (£1,277.60, 3 reversals excluded).
