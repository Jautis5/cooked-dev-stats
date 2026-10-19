# Cooked Dev social stats

Public statistics for the Cooked Dev accounts on Instagram, TikTok, YouTube, X and Facebook. The public dashboard is hosted with Sites. GitHub Actions refreshes public metrics hourly at minute 17 UTC, independently of the owner's computer. GitHub may delay scheduled jobs.

`data/latest.json` holds public observations with a source and timestamp for every metric. `data/posts.csv` and `data/platforms.csv` feed Google Sheets. Failed collection preserves earlier observations and updates the source status; it never fabricates a zero or advances a metric's observation time. Platform view counts are additive plays, not unique cross-platform reach.

Run `python scripts/collect.py` to refresh. Python 3.12 and yt-dlp are required for collection. `python scripts/test_data.py` validates the snapshot. Public pages can withhold metrics or block server requests; official account API connections are required for reliable private insights and may be needed for automatic discovery of new posts. The initial registry contains 12 verified videos. New TikTok records are adopted only when the public profile actually exposes an author-matched item list. Existing public posts are refreshed separately.

No cookies, account tokens or private analytics are included in this repository.
