# Explicit provider player identity discovery

`PlayerIdentityDiscovery.run(targets=..., reference_date=...)` receives a nonempty
 tuple of `PlayerIdentityTeamTarget(provider_slug, team_id)` values. `team_id` is
an existing SMS24 `SportsCompetitor` UUID, not a provider ID. All targets must be
teams of the specified active source and an active sport. Registry agreement and
both discovery methods are checked before any provider call.

The sequential flow is:

1. Reuse `fetch_team_player_ids(team_external_id=..., reference_date=...)` for
   active memberships. Sportmonks retains its existing strict start/end rules.
2. Deduplicate opaque player IDs per source within the run (including failures).
3. Call `fetch_player_identity(athlete_external_id=...)` independently of Statistics.
   Sportmonks uses `/players/{id}` without includes, through its existing HTTP client.
4. Validate `ProviderPlayerIdentity(external_id, name, fetched_at)`, including exact
   returned/requested ID agreement. No placeholder name or optional fields inferred.
5. Within a per-player savepoint, call `SMS24IngestionRepository.upsert_competitor`
   with `competitor_type="athlete"` and **`country_code=None`**.

The unique identity remains `(source_id, external_id)`. The existing canonical
helper consequently creates a **provider_scoped** competitor key based on sport,
source and external ID, never on the name. Replaying or renaming refreshes the same
provider row. The shared repository retains the original canonical display name;
this service does not rewrite canonical facts. Existing conflicting sport/type or
canonical resolution is rejected locally, rather than silently replaced.

`teams_processed` counts successful membership responses, including empty ones.
`players_discovered` counts unique source/player pairs, including failed identities.
`players_processed` counts successful upserts, including refreshes.
`failures` identifies source, team and optional player with an internal reason code.
Targets run in caller order; player IDs run in lexical order. A local provider or
validation failure continues with other targets. SQLAlchemy and unexpected ingestion
errors propagate. The service never commits: the caller owns the outer transaction,
including rollback of all successful savepoints if desired.

There is no worker, scheduler, automatic Statistics invocation or capability change.
Only explicitly supplied teams are queried; no global player catalogue is scanned.
Calls are sequential; there is no persistent retry queue or continuation in this layer.
An identity unavailable under the subscription is a local failure, retryable in a
later explicit call. No real Sportmonks calls are made by the tests.

No User, Profile, Athlete, AthletePerformance or SportsAthleteIdentityLink is created
or resolved. Provider-scoped canonical competitors are not verified human identities.
No cross-provider, name, name+country or fuzzy matching is performed.
