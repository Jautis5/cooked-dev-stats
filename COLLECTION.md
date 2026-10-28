# Social Stats collection and reconciliation

Canonical repository: `Jautis5/cooked-dev-stats`, branch `main`.
Local maintenance checkout: `/Users/jonassendzikasdarbas/Documents/lOSTaSTRONOUT/work/cooked-dev-stats-autonomous`.
The earlier `work/cooked-dev-stats-cloud` checkout is obsolete for maintenance.
Dashboard source lives in `site/`; Sites is a published mirror of this source.

## Sources and identities

`data/channels.json` identifies every channel feed. Read each feed's `accounts`
and `tracking` settings before collecting. There are three channels: Cooked Dev,
Indian Builds and DontGetTraced. DontGetTraced Instagram is **dontgettraced**;
the old dongettraced handle was wrong. Indian Builds Instagram/TikTok is
indian_builds; X is IndiaanBuilds. The former indiaanbuilds Instagram/TikTok
identity was corrected on 22 October. Read the feed rather than restoring an
older handle. Never mix channel IDs or Facebook Page IDs.

The cloud collector runs every 15 minutes without an owner computer. TikTok's
ordinary profile response can omit its video list; the public creator embed is
an additional bounded discovery source. YouTube's feed can fail; the exact
owner's Shorts tab also refreshes known public view counts. X now also uses
the anonymous FxEmbed public API for profile followers, attached-video discovery
and known-post views/likes/replies/reposts. Resolve the verified handle to its
numeric profile ID before reading the media timeline. Every returned post must
match the registered author and contain its own public attached video. At most
three timeline pages are read; the result stays partial. A 404 is not an empty
account. Null counters preserve prior observations. Metrics retain the canonical
post source plus `method=fxembed_public`, the actual `via` endpoint and an unknown
`upstreamObservedAt`: the service does not guarantee upstream cache freshness.
X's official public embed remains a fallback for likes and replies only.

Instagram and Facebook full inventory, Instagram grid views, and guaranteed X
inventory need the authorized browser or supported account access. The cloud
job cannot create that access. A completed process is not complete coverage.
`health.json` records view freshness separately from other metrics and discovery.

## Authorized browser pass

Use only the existing lostastronaut.space Chrome session through documented
cua_repl. Read whole account lists/grids in background tabs; do not activate
native windows, play audio, extract cookies/tokens, start new OAuth/developer
registrations, buy APIs, send messages, or publish social posts. A verification
challenge blocks that source only. Continue the other accounts.

Read all three channels independently. Collect actual publication IDs and URLs,
owner identity, public visibility, visible metrics, observation times and any
rounding. Mark `completeList` only after the entire relevant list was checked.
For Indian Builds exclude `tracking.excludedPostIds` and legacy White Hack.
Private, Unlisted, Scheduled, text-only posts, recommendations and reposts are
not public video publications. A quote with the owner's own attached video can
be tracked after checking that actual video and original status ID.

Keep raw captures private. Import a normalized public-only capture with:

```
python scripts/import_channel_capture.py --input <private-capture.json> --dashboard <channel dataPath>
```

The importer now supports all three channels, including cooked-dev. It preserves
original per-metric dates and reports the last fully checked inventory date.

## One video, many publications

`data/publications.json` is the durable, evidence-backed content map. Reconcile
it before and after collection and concurrent snapshot publication. New posts
may enter as unmatched rows. Do not infer a match from captions alone. Confirm
the same original asset or review the actual clips, then record exact URLs,
verifiedAt, evidence and YouTube/Facebook owner IDs in a publication group.
Reconciliation preserves metrics by observation time and removes duplicate rows.
After any authorized social upload, save its verified public URLs here as part
of the handoff, rather than leaving a receipt disconnected from the tracker.

## Publish and verify

Pull only a clean checkout. Preserve unrelated changes. Run the Python test
suite and the three dashboard suites after source changes. For data-only writes,
use `scripts/publish_refresh.py`; it merges with concurrent cloud observations
and never force-pushes. Re-read the published JSON and check one linked video
across its actual platforms. Do not advance metric dates just to appear fresh.

Synchronize only the existing managed Sheet tables and their existing formulas.
Cooked Dev uses Video, Statistika, Suvestinė; Indian Builds uses Indian Builds,
Indian Stats, Indian Summary. DontGetTraced has its own tab. Never import Indian
Builds through the Cooked-only MCP server. Use the canonical feed/ledger for
matching; never create a second Sheet row just because YouTube found the same
video later. Preserve source links, unknown values and observation times.

Routine successful sync and unchanged access blocks stay quiet. Notify only on
a meaningful failure, new identity ambiguity or required owner action. The
local browser automation's paused/enabled state is controlled separately from
the cloud collector; do not claim a paused browser task is collecting.

Inventory discovery must precede known-ID metric checks. A fresh like count
does not renew `discovery.lastCompleteAt`. Mark a list complete only after
checking its actual end; validate `reportedVideoCount` against the unique IDs
in the capture. The cloud health and dashboard flag a last full check older
than two hours independently of metric freshness.

Record local browser failures and notification state privately in
`../social-audit-2026-10-22/maintenance-state.json`. Report a new overdue
inventory failure once, and suppress the same unchanged failure until access
recovers. Missing the Lost profile in browser inventory or a closed native
control pipe is a maintenance failure, not proof that an account is empty.
Preserve measured data and continue the healthy cloud sources.

## Continuous coverage and Google Sheets

Every run exports `metrics.csv` for each channel as well as `posts.csv` and
`platforms.csv`. It contains one row per actual account/post/metric with the
metric's own source and observation time. Missing views/likes/comments/shares
are explicit `not_observed` entries, never measured zeros. Additional metrics
returned by a provider (including saves) are retained. `health.json` records
known, updated, missing and oldest observation for every per-post metric.

Google Sheets now imports the canonical CSVs with native `IMPORTDATA` formulas
in A1 of Statistika, Suvestinė, Indian Stats, Indian Summary, Traced Stats and
Traced Summary. Do not overwrite their spill areas with manual snapshots.
Verify the A1 formulas on every maintenance pass. If a formula was replaced
by static values, back up that managed table, clear its cell values only,
restore the canonical `main` CSV import and verify the resulting values.
Their dependent per-video totals update from the same source as the website.
Google controls import refresh timing; do not promise a 15-minute Sheets SLA.
This removes the manual-copy drift, not the platform authorization limits.

The Cooked-only local MCP seed is the current autonomous checkout, not the
obsolete cloud checkout. After a browser import, seed that local archive from
the canonical Cooked feed while preserving the original metric dates. The
hourly browser heartbeat complements the 15-minute cloud collector only while
the authorized desktop session is available. Neither can fabricate inaccessible
Instagram/Facebook analytics. Scheduled social posts stay outside public totals.

## GitHub ownership and browser delivery — 28 October 2026

The canonical repository and website belong to **Jautis5**. The owner explicitly
retired the previous workplace account. Do not use its saved CLI authentication,
old repository, old Pages URL, or upstream synchronization for ongoing work.
Historical source/run URLs remain historical evidence only.

The existing verified Jautis5 browser session owns the repository. No new login,
OAuth scope, cookie/token extraction, or paid service is needed. When the local
CLI has no verified Jautis5 credential, publish the normalized public-only feed
bundle through that existing browser to `incoming/browser-capture.json`. The
`Import verified browser observations` workflow validates channel identities and
merges snapshots through `scripts/publish_refresh.py`, preserving concurrent cloud
updates and original metric dates. Never upload private raw browser captures.

The GitHub cloud collector uses only its built-in temporary repository token.
Check public JSON, Actions results and the next clock successor anonymously or
through the existing Jautis5 browser; do not fall back to the old CLI account.
