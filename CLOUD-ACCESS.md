# Collection while the owner's Mac is off

Decision record, verified 2026-10-22. This distinguishes deployed collection
from the next account-connection work. No new platform credentials have been
created or granted by this change.

## Already deployed and tested

The existing public GitHub repository uses standard hosted Actions runners.
They do not depend on the owner's Mac, Chrome or Codex. Collection targets a
15-minute cadence; GitHub scheduling is not a real-time service guarantee.

The new FxEmbed integration reads public X metadata without cookies, account
tokens or a paid X API subscription. It verifies the registered author, numeric
post ID, public profile and attached video, then reads views, likes, replies and
reposts. It also reads bounded account media timelines. A failed handle lookup
can recover the numeric owner ID from an already verified video. It never
imports quoted media, recommendations or another author's repost.

Successful hosted verification:
https://github.com/jonass-pandos/cooked-dev-stats/actions/runs/39736067833

At 06:47 UTC this run refreshed views for 18 TikTok, 8 YouTube and 8 X posts
across the three brands. It also refreshed some Instagram engagement counters.
It did not refresh the 19 Instagram or 8 Facebook post view counts. All account
inventories remain explicitly partial/unavailable; a process exit of zero is
not proof of complete coverage. 67 Python tests and all three dashboard suites
passed. X observations include the actual provider endpoint and explicitly
unknown upstream observation time. An integer from a proxy is not a guarantee
of real-time platform accuracy or availability.

## Recommended route to fuller free coverage

Keep GitHub Actions as the main runner and publisher. Add narrowly scoped,
official account access for Meta and TikTok and a YouTube Data API key. Use
public fallbacks only where access is unavailable. Keep X's free fallback
labelled as third-party and partial.

| Source | Next connection | Limitation |
| --- | --- | --- |
| YouTube, all 3 brands | Enable Data API in an owner-controlled Google project; API key restricted to that API | Public list/statistics access is quota-limited; owner-only analytics need separate authorization. No key is configured yet. |
| Instagram + Facebook, all 3 brands | Owner-controlled Meta developer app; authorize managed Pages/professional Instagram accounts with only the read/insights permissions actually required | Account type, Page linkage, app roles/access and current metric availability must be verified. No connection is configured yet. |
| TikTok, all 3 brands | Prototype Login Kit + Display API in an official Sandbox with the three accounts as target users; authorize public video reads | Sandbox permits up to 10 target accounts without app review for testing. It is a development environment, not a production availability guarantee. Production has its own review requirements. |
| X, all 3 brands | Existing anonymous FxEmbed integration | No upstream completeness/cache guarantee. Official X reads are paid, including owned reads. |

For the current YouTube size, one batch channel request, three upload-playlist
requests and one batch video-statistics request per cycle would use about
5 * 96 = 480 quota units/day at a 15-minute cadence, before extra pagination,
retries or other API use. The published default allowance is 10,000 units/day.
This is a planning estimate, not a measurement of an enabled integration.

## Token persistence is part of reliability

Initial authorization must happen once with the owner present. Thereafter,
refresh runs on a server. TikTok's access token lasts 24 hours, and its refresh
response can rotate the refresh token: persist the replacement before using
it again. A static copied access token or a token kept only on this Mac does
not meet the requirement.

An owner-only standalone Google Apps Script project is one candidate for the
small token-refresh service, using Properties Service for durable state and
LockService to serialize rotation. It fits an existing Google account rather
than requiring a paid server. Consumer quotas currently include 20,000 URL
fetches/day, 50,000 property operations/day and 90 minutes/day for trigger
runtime. This candidate has not been deployed or tested with these accounts.
The integration must authenticate requests, expose only normalized public
observations and never return tokens. Keep the project private, separate from
the shared tracker Sheet; its editors can access script properties.

Do not put tokens in dashboard code, public JSON, Sheets, logs or artifacts.
Do not export browser cookies or create paid/trial subscriptions to bridge a
missing connection. Expired/revoked access must preserve previous values and
their dates, and show the source as requiring reconnection.

## Acceptance before claiming full operation

1. Independently verify the identity of each of the 15 brand/platform pairs.
2. Read each authorized public inventory through its actual pagination to the
   tracking cutoff, retaining exclusions and original publication URLs.
3. Refresh each available metric with source and retrieval time. Never replace
   missing/blocked metrics with zero; retain rounding and provider provenance.
4. Verify scheduled collection from hosted logs and confirm that it publishes
   fresh observations while no local helper process or browser is involved.
5. Observe token refresh and a subsequent successful scheduled run. Keep the
   local browser fallback until the authorized cloud replacement is proven.

There is no verified basis to promise all five platforms, all metrics, full
inventory, exact real-time accuracy and permanent zero cost simultaneously.
The practical zero-subscription design combines official authorized reads where
available with explicitly limited public fallbacks.

## Primary references checked

- GitHub free standard public runners: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- YouTube setup/default quota: https://developers.google.com/youtube/data/getting-started
- Video statistics request: https://developers.google.com/youtube/data/reference/rest/v3/videos/list
- Upload playlist pagination: https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/list
- Meta's official Instagram collection and token prerequisites: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
- TikTok Sandbox target users: https://developers.tiktok.com/docs/en/add-a-sandbox
- TikTok public-video pagination: https://developers.tiktok.com/docs/en/tiktok-api-v2-video-list
- TikTok token rotation: https://developers.tiktok.com/docs/en/oauth-user-access-token-management
- FxEmbed API and limits: https://docs.fxembed.com/api/introduction/
- Official X paid and owned-read pricing: https://docs.x.com/x-api/getting-started/pricing
- Apps Script quotas: https://developers.google.com/apps-script/guides/services/quotas
- Apps Script properties: https://developers.google.com/apps-script/guides/properties
- Metricool Free: one brand, no X, no general API: https://help.metricool.com/main-differences-between-free-and-paid-plans-bl0v9
