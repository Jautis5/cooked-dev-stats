# Official account read broker

Owner project: https://script.google.com/home/projects/1x5-pDb37ER4TRfTB173sj5xPbtY6ECjNARnphNBS5Ovw9Pi9SgqdHRKe/edit

The standalone project is owned by `hello@lostastronaut.space`. Keep it private;
do not bind it to the shared tracker Sheet or share its source project. Source
and the explicit manifest are in this directory. `YouTube` is the only Advanced
Service. Google scopes are `youtube.readonly` and `script.external_request`;
there is no publishing, Drive, Gmail or Sheets scope. The owner explicitly
approved these scopes and connecting the broker to the existing GitHub runner.

## Data flow

`GitHub Actions -> authenticated Apps Script doPost -> official platform reads -> normalized public observations -> existing snapshots`

GitHub supplies the channel, platform and known post IDs. It signs the entire
request with HMAC-SHA256, a timestamp and nonce. The server restricts all reads
to the three hard-coded channel identities. The client verifies returned owner,
channel, public URLs and observation times before applying any response.
Missing metrics never become zero. Known posts/Drive assets are not deleted.
Tokens never leave the broker. The initial Meta/TikTok grants and subsequent
token refreshes use platform endpoints only. TikTok refresh-token rotation is
persisted under a server lock before any next API call.

## Deployment

1. Save `Code.gs` and `appsscript.json` in the standalone project.
2. Review/authorize exactly the two Google scopes. `verifyYouTubeConnection`
   performs real public reads of all three registered channels.
3. Put `BROKER_SIGNING_KEY` in Script properties. Use a random 32-byte or longer
   key; never paste it into source, a Sheet, a chat response or public logs.
4. Deploy a Web app that executes as the owner and accepts unauthenticated
   transport requests. Access to data is still gated by the signed request.
   GET serves only the service name or a validated one-use OAuth callback.
5. Put its exact `/macros/s/<deployment>/exec` URL in `WEB_APP_URL` in Script
   properties. Configure `SOCIAL_STATS_BROKER_URL` and `SOCIAL_STATS_BROKER_KEY`
   as GitHub repository Secrets, never repository variables or public files.
6. Run the hosted refresh and inspect actual official observation dates. The
   workflow remains functional when Secrets are absent; it uses public fallbacks.

## TikTok, one initial authorization per brand

The developer portal currently requires a separate developer login/registration.
Create an owner-controlled Sandbox, add Login Kit and Display API, and add only
the three owned target users. Register the exact web-app URL as redirect URI.
Configure `user.info.basic`, `user.info.profile`, `user.info.stats`, `video.list`.
There are no content posting, messaging or advertising scopes.

Put `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` in Script properties. Run one
of `connectTikTokCooked`, `connectTikTokIndian`, `connectTikTokTraced` to obtain
a short-lived authorization link. Open it with the intended account, review
the actual permission grant, and complete authorization. The callback rejects
the wrong username/open_id and never returns tokens. A Sandbox is a test
environment; do not represent it as a production-reviewed app.

## Meta, one grant for each brand's assets

Complete the owner-controlled Meta developer enrollment, then create/reuse a
read-only app supporting Facebook Login for managed Pages and Instagram.
Set `META_APP_ID`, `META_APP_SECRET`, and `META_GRAPH_VERSION` to the version
actually selected in its developer dashboard. Register the exact callback URL.

Requested permissions: `pages_show_list`, `pages_read_engagement`,
`read_insights`, `instagram_basic`, `instagram_manage_insights`,
`instagram_manage_comments` (required by Meta even for reading comments). Configure any
additional current platform requirement only after reviewing its necessity.
Do not request publishing, messages or ads. The comment permission also supports
moderation on Meta's side; this backend exposes only GET reads. Review the exact
grant with the owner before accepting it.

Run `connectMetaCooked`, `connectMetaIndian`, `connectMetaTraced` and grant only
the corresponding owned Page and linked professional Instagram account. The
callback filters to the registered Page ID and verifies the linked Instagram
handle. Other managed Pages are not persisted.

Instagram insights are requested one metric at a time so an unsupported field
does not invalidate all other metrics. Facebook `video.views` is stored with its
original API metric name and a conservative partial inventory. Before declaring
Facebook coverage complete, verify that the API includes each known Reel and
compare its view definition with the Page's UI. There is no fabricated fallback
from another video metric.

## Verification status

Local validation: 80 Python tests, all existing dashboard suites and the broker
Node suite passed. Tests cover request tampering/replay, owner/public filters,
refresh-token persistence, no secret output, true zero vs missing, cutoff and
exclusions, and transactional rejection of invalid observations.

An authorized and deployed service, live account identity checks, a real token
refresh and a subsequent scheduled successful run are separate acceptance
steps. Update the handoff state after each; local tests alone are not live access.

## Current priority

Instagram is the first priority, TikTok second (owner instruction 2026-10-22).
The Google broker is deployed and rejects unsigned requests. One real YouTube
read was verified. The hosted GitHub run
https://github.com/Jautis5/cooked-dev-stats/actions/runs/39740943535
then verified official reads of all 7 Cooked Dev and the Indian Builds video.
Meta developer terms were accepted with explicit owner confirmation. Enrollment
now requires an owner-entered mobile number and SMS verification. No Meta app
or account token exists yet. TikTok is at developer email verification. Do not
claim Instagram or TikTok official access until their actual grants succeed.

## Read-only Instagram/TikTok MCP

The same deployment was updated to version 2 on 2026-10-22 at 11:05 Vilnius
without changing the URL or Google scopes. It now provides signed `capabilities`,
`posts`, `comments` and `traffic` operations for the two platform-scoped MCPs in
[`../mcp`](../mcp/README.md). No arbitrary URLs, accounts, publishing, comment
moderation or message operations are exposed. Raw comments are returned privately
on demand and are never added to the public collection feed or workflow artifacts.

Both custom MCPs were registered and verified through real stdio initialization,
tools/list and tool calls. Each lists seven read-only tools. Both read the existing
18 Cooked Dev platform posts with original source dates. Live cloud status confirms
Instagram has no Meta token for any of the three brands; TikTok has neither a
Display nor an Accounts API token. Actual comment/traffic probes return
`CONFIGURATION_REQUIRED` and `BUSINESS_ACCESS_REQUIRED`, with incomplete coverage.
This is an installed and tested integration, not completed platform authorization.
