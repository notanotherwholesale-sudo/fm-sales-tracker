# Tracker → Auto-Delister sync

The sales tracker detects sales from **Depop/Vinted emails**, which means it knows —
authoritatively, with no Crosslist scraping — *exactly which platform each item sold on*.
That is precisely the signal the FM Auto-Delister otherwise has to read from a flaky
Crosslist "Manage sales" popup. So the tracker hands it over.

## The contract: `delist_queue.csv`
Every run, when the tracker records a new sale it appends a row here (committed to this
repo, so a `git pull` on the Mac gets the latest):

| column | meaning |
|---|---|
| `detected_at` | when the tracker saw the sale (London time) |
| `sold_date` / `sold_time` | when the sale happened |
| `sku` | leading SKU parsed from the title (blank if none) |
| `title` | full item title |
| `sold_on` | platform it sold on — **keep this listing** |
| `delist_from` | the **opposite** platform — the one to delist |
| `status` | `pending` (the tracker never flips this; the delister tracks its own completion) |

The queue is **append-only and idempotent** — the same sale is never queued twice.

## How the delister should consume it (safely)
The delister keeps **all** its safety rules (blueprint §2) — the queue only replaces the
"what sold where" discovery step. Recommended flow, added to `delister.mjs`:

1. `git pull` the tracker repo (or read the local checkout) to refresh `delist_queue.csv`.
2. `readDelistQueue()` (see `lib/queue.mjs`) → pending items not already in `delister_log.csv`
   (dedupe on `sku`+`sold_date`, exactly as the watermark already does).
3. For each: still open Crosslist, **assert both-active**, **assert single-opposite**, honour
   posting-in-progress / logged-out / not-found rules — then delist `delist_from` only.
4. Append the result to `delister_log.csv` as today. The queue's `sold_on` is trusted in
   place of the Manage-sales popup read; everything else is unchanged.

`status` stays `pending` in the queue — completion lives in `delister_log.csv`, so the two
repos never fight over the same file.

## Safety — unchanged
- **Still `--dry-run` by default.** The queue is just a more reliable input; it does not make
  anything destructive. Live still requires `DELISTER_LIVE=1`.
- The delister must still verify both-active on Crosslist before delisting — the tracker
  knows *what sold*, not the current *listing state*.
- `lib/queue.mjs` is **read-only** (parse + dedupe). It performs no browser or delist actions.
