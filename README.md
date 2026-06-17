# FM Sales Tracker (cloud, email-driven)

Records every Depop / Vinted sale, rebuilds the phone dashboard, and publishes to
GitHub Pages — **on a schedule, in GitHub's cloud. No laptop, no Chrome, no Cowork.**

Sale emails → Gmail label → GitHub Actions cron → parse → `fm_sales.csv` →
`build_dashboard.py` → GitHub Pages + widget feed.

## How it works
- **`ingest.py`** logs into Gmail over IMAP, reads new emails under the `fm-sales`
  label, parses Depop/Vinted sales into `date,time,sku,title,platform,price`,
  dedupes (key = platform+date+title+price), and appends to `fm_sales.csv`.
- **`build_dashboard.py`** (unchanged) → `FM_Sales_Dashboard.html` + `summary.json`.
- **`.github/workflows/tracker.yml`** runs the above 4×/day, commits the updated
  CSV back to the repo (the repo *is* the database), and deploys Pages.
- State that survives between runs: `fm_sales.csv`, `processed_ids.json`,
  `collisions.csv` — all committed by the bot each run.

## One-time setup
### 1. Gmail app password
Google Account → Security → enable **2-Step Verification** → **App passwords** →
create one named "FM Tracker". Copy the 16-char code.

### 2. Gmail filter + label
Settings → Filters → Create filter:
`from:(depop.com OR vinted.com OR vinted.co.uk)` → Create filter →
**Apply the label** `fm-sales` (create it). Tick "also apply to matching
conversations" to backfill existing sale emails.

### 3. GitHub repo
Push this folder to a new repo, then:
- **Settings → Secrets and variables → Actions** → add:
  - `GMAIL_USER` = your Gmail address
  - `GMAIL_APP_PASSWORD` = the 16-char app password (no spaces)
- **Settings → Pages** → Source = **GitHub Actions**.

### 4. First run
Actions tab → **FM Sales Tracker** → **Run workflow**. Watch it parse, commit,
and deploy. The live URL appears in the deploy step.

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

## Safety
- Credentials live **only** in GitHub Actions secrets — never in the repo.
- Re-runs are idempotent (sale-key dedupe + processed Message-IDs).
- A missed day is caught up automatically — every run re-scans the whole label.
