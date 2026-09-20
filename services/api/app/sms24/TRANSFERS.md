# Transfers foundation (0034)

This provides local persistence, domain validation, and a generic Transfers runner.
Sportmonks supplies a Transfers HTTP adapter. There is no public Transfers endpoint,
automatic human linking, or new capability activation.
The existing `transfers` capability and provider registry remain the integration boundary.

## Sportmonks adapter

`fetch_transfers(athlete_external_id=...)` uses `/transfers/players/{player_id}`,
based on subscription responses supplied for this integration. The generic
`/transfers?filters=playerIds:...` route is not used: the supplied probe did not filter.
Numeric transfer `id` is the sole observation identity; `player_id` must match the
requested string exactly. Team IDs map directly; missing/null IDs remain unknown.
Dates accept only valid `YYYY-MM-DD` strings or null. Malformed records reject the batch.

`reported_type` preserves `str(type_id)` without a business interpretation. The raw
transfer object is copied to `metadata` (persisted as `metadata_json`), preserving
`amount`, `completed`, `career_ended`, position IDs and other provider facts as supplied.
No fee currency, season, canonical status, names or update timestamps are inferred.

Pagination uses local `page`/`per_page=50` requests and requires valid `current_page`
and `has_more`. Upstream next-page URLs/cursors are never followed. Duplicate IDs,
missing pagination, empty nonterminal pages and the configured page limit cause failure
instead of returning incomplete results. Existing sanitized HTTP handling is reused.
Actual subscription access is not re-probed by the tests, which use mocked HTTP.

## Automatic targets

`run_sms24_automatic_transfers(session, reference_date=D, max_teams=20, max_players=100)`
composes `SportmonksTransfersTargetDiscovery` and `TransfersBatchOrchestrator`.
The existing single-player `TransfersRunner.run(targets={...})` is unchanged.

Discovery reads existing `SportsCompetitor` team rows belonging to Sportmonks and
the active football sport, gated by the active source and Transfers capability.
It uses their `external_id` directly, never a parsed canonical key. The path is:
known team → `/teams/{id}?include=players` → active membership `player_id` → runner.
No global `/players` scan or individual `/players/{id}` requests are made.

The team object and every membership must match the requested team. `players=[]`
is a valid empty result; absent/malformed includes reject that team's payload.
`start` and `end` must be present, either null or strict `YYYY-MM-DD` dates.
Membership is active exactly when `(start is null or start <= D)` and
`(end is null or end >= D)`. Invalid/inverted dates or invalid IDs reject the whole
team payload, including rows that would otherwise be inactive. IDs use the existing
Transfers numeric ASCII positive-ID validator; their string representation is preserved.

Targets are ephemeral: memberships supply no reliable player name. No provider
athlete row, human profile, identity link, canonical event or resolution is created.
Discovery is read-only; ingestion is delegated exclusively to the existing runner;
identity resolution remains a separate explicit action.

Teams and deduplicated player IDs use lexicographic string ordering. Defaults are
20 teams and 100 players per run, configurable positive integer limits. Discovery
reports `teams_limited`; the batch reports discovered/attempted/succeeded/failed/
deferred counts and observations processed (including replays, as in the runner).
Discovery counts apply only to the teams visited. Runs are sequential without retries
or following upstream next-page URLs/cursors. A batch is bounded by the team limit
plus the player limit times the existing health-check and `max_pages` fetch bound.
This is a call budget, not a time-based rate limiter or scheduler.

### Stateless continuation

The repository's public lists generally use limit/offset; this traversal instead
uses identifier keysets so deleting the previous boundary cannot shift an offset.
`discover(reference_date=D, after_team_external_id=cursor)` selects IDs strictly
greater than the cursor using the same PostgreSQL `COLLATE "C"` as its ordering.
It reads at most `max_teams + 1` rows to detect a following page. `has_more`
(also exposed as the existing `teams_limited`) and `next_cursor` describe continuation.
The next cursor is the last attempted team ID, including failed attempts, or null
when no further teams remain. No cursor means the unchanged first page.

`batch.run(player_ids=ids, after_player_external_id=cursor)` similarly selects
deduplicated, lexicographically sorted IDs strictly after the cursor. Its
`targets_discovered` counts the entire supplied deduplicated set;
`targets_before_cursor` counts IDs at or below the boundary in that set (not proven
prior successes). `targets_deferred` counts only IDs remaining after this page.
`has_more` and `next_cursor` identify the next page, including when this page fails.
Both cursor types use the existing positive ASCII decimal ID validator and preserve
the exact string; a boundary need not still exist. Invalid cursors fail before I/O.

The runtime accepts an explicit `AutomaticTransfersCursor(after_team_external_id,
after_player_external_id)` via `cursor=` and returns `result.next_cursor` of the same
type. Pass that value to the next invocation with the same reference date and team
limit. While players remain, it retains the input team boundary and advances only
the player boundary. Once those players are exhausted, it advances to the next team
page and clears the player boundary. The last result has `next_cursor=None`; callers
must stop that traversal rather than interpret null as another continuation.
This may fetch the current teams again while draining their players. Alternatively,
call discovery once and drain its ephemeral `player_ids` through the batch component.

For stable sets, these exclusive boundaries cover every team/player page without
repeating entries within that traversal of a set. They are not snapshot isolation:
new IDs at or below a consumed boundary are visited on a later sweep started without
cursors. Keep the reference date, selection parameters and player set stable when
requiring exact per-sweep coverage. A player appearing in different team pages can
be attempted again; cross-run deduplication is not stored here and observation
ingestion remains idempotent. Failed attempts advance to avoid blocking later IDs;
retry policy, cursor persistence and starting subsequent sweeps belong to the caller.
Discovery eligibility/configuration errors must be handled using `discovery.reason`,
not mistaken for a completed traversal. No global state, table, worker or scheduler
is introduced.

Team failures carry sanitized discovery codes and other teams continue. A runner's
`TransfersAllProvidersFailed` becomes `transfers_target_failed` for that target and
other players continue, including when every target fails. Empty discovery yields
zero batch attempts; eligibility/configuration failures are explicit discovery reasons.
Unexpected batch errors and SQL errors propagate. The caller owns the transaction;
the runner's savepoints protect valid prior targets. No component writes source health
or enables any capability, including API-Football Transfers.

## Explicit runner

`build_sms24_transfers_runner(session)` uses the existing provider registry. Call
`run(targets={"provider-slug": "opaque-player-id"})` with explicit, normalized slugs.
Only targeted active sources with an active Transfers capability and a callable
`fetch_transfers` are probed. Registration alone never enables Transfers.

All eligible targets run in capability-priority/slug order. Results are validated
against the contract and requested player, then persisted only with
`record_observation`, in a savepoint per provider batch. The caller owns the outer
transaction. Validation failures produce sanitized attempt codes; database errors
during persistence propagate. No outcome updates global source health.

A valid empty result succeeds without deleting previous observations. At least one
success returns a result; otherwise `TransfersAllProvidersFailed` carries attempts.
`observations_processed` counts accepted batch entries, including replays and stale
snapshots, not newly inserted or changed rows. No graph or human resolution occurs.

## Identity and review

- `Athlete.id` remains the human/profile identity. Canonical sports athletes remain
  `SportsCanonicalCompetitor(competitor_type="athlete")`. External athletes need no
  SMS account, and transfer observations never create users or athlete profiles.
- `SportsAthleteIdentityLink` records an explicitly authorized decision with method,
  reviewer/claimant reference, evidence reference, trust state, and timestamps.
  `declared` is the default. `verified` requires an institutional review and timestamp;
  a provider response is not such a review. This does not verify national eligibility.
- Partial unique indexes permit at most one active link on each side. End an old link
  before replacement; retain ended rows as history. Supporting multiple provider-scoped
  canonical nodes per human later requires an explicit reconciliation/cardinality decision.
- The domain checks canonical athlete type and matching sport. No name comparison is
  used. Existing canonical resolver behavior is unchanged. In particular, its current
  name/country context is **not** used here to establish human or transfer identity.
- This module is not an authorization layer. A future API must authorize review actions
  and control who may assert institutional verification. Direct SQL bypasses cross-table
  type/sport validation; foreign keys, uniqueness, and scalar checks remain enforced.

## Events and observations

- `SportsCanonicalTransfer` is an explicit event UUID, with an athlete graph FK and
  optional same-sport team FKs. Unknown clubs, date, fee, and display type are NULL.
  Normalized movement type/status default to `unknown`; raw provider codes are never
  automatically translated to confirmed facts. Zero fee is distinct from unknown fee.
- A season FK is optional and references an explicitly mapped, competition-scoped
  `SportsSeason` of the same sport. No calendar-year or season-label inference occurs.
- `SportsTransferObservation` retains source, external athlete identity, optional event
  ID, raw team IDs/names, provider date/type, metadata, and fetch/update timestamps.
  Its optional provider-athlete and canonical-event links require explicit resolution.
  Repeated provider snapshots preserve these links and do not overwrite canonical facts.
- Identity is `(source_id, observation_key)`. The key hashes a tagged opaque event ID,
  or a stable source-record reference supplied by an adapter when no event ID exists.
  A source-record reference must not be built from names, dates, teams, or list position.
  If neither identity exists, the record is rejected rather than guessed into an event.
  Provider-local IDs must be scoped appropriately by the adapter. Identity strategy
  changes require explicit reconciliation; corrections cannot silently change the player.
- Equivalent-looking observations from different sources remain separate. Canonical
  event creation does not deduplicate by facts. Mapping multiple observations onto an
  event requires explicit IDs and coherent existing athlete mappings.
- Observations follow the existing latest-snapshot convention; they are not an append-only
  payload history. Older fetched snapshots are ignored. Equal timestamps may update.
  A future audit-history requirement should add explicit versions rather than redefine IDs.
- FKs use RESTRICT to avoid silently erasing graph provenance. Deletion/reconciliation
  workflows must account for these links. Downgrade drops only the three new tables;
  it intentionally discards their data and leaves pre-existing SMS/SMS24 tables intact.

## Validation

`SMS24_MIGRATION_TEST_DATABASE_URL` must explicitly name disposable PostgreSQL.
Tests create unique schemas with no public search-path fallback and roll back all DDL/data.
Run the new contract/PostgreSQL tests plus existing canonical-identity/provider-contract
unit tests. Do not point the migration tests at the application database.
# Durable worker checkpoint foundation (0036)

The delivery chain is FOUNDATION → RUNNER → SPORTMONKS ADAPTER → CAPABILITY →
AUTOMATIC TARGETS → DURABLE WORKER CHECKPOINT → future WORKER/SCHEDULER.
This layer starts **no worker**, timer, HTTP request, scheduler or Docker service.
It never enables a capability or changes source health or domain identity.

Migration `20260920_0036` follows `20260920_0035` and creates only
`sms24_job_checkpoints`, without seeding any job. Downgrade drops only that table.
The table is generic; `SMS24TransfersCheckpointRepository` supplies the typed
Transfers API for the stable job key `sms24:sportmonks:transfers`.

| Column | Type / purpose |
| --- | --- |
| `job_key` | varchar(160), primary key: one durable record per logical job |
| `status` | varchar(32): idle, running, completed, completed_with_errors |
| `reference_date` | nullable date: fixed membership date for this traversal |
| `cursor` | non-null JSONB object: `after_team_external_id` and `after_player_external_id`, both nullable strings; empty object outside a traversal |
| `parameters` | non-null JSONB object: fixed `max_teams` and `max_players` for Transfers |
| `failed_attempts` | non-negative integer, initially zero: cumulative failed team/player attempts, so a successful final page cannot erase earlier errors |
| `started_at` | nullable timestamptz: start of the current/latest traversal |
| `completed_at` | nullable timestamptz: explicit traversal completion |
| `created_at` | non-null timestamptz: job record creation |
| `updated_at` | non-null timestamptz: latest checkpoint mutation |

There are no retry counters, next-due timestamps, payloads, secrets, human foreign
keys or cycle history here. Retry cadence belongs to the future scheduler. The
single record preserves the current/latest traversal only. JSON columns allow
other SMS24 jobs to define their own cursor/parameters without another table.
Transfers uses validated `AutomaticTransfersCursor` values, never a raw upstream URL.
Database checks enforce nonempty identity, allowed statuses, object-shaped JSON,
nonnegative failure count and consistent lifecycle dates. Transfers parameter and
cursor validation, and parameter immutability, are enforced by the repository API;
direct SQL writers must not bypass this protocol.

## Transaction and lock protocol

The caller opens the outer transaction **before** calling `try_acquire_lock()`.
The key is the first 8 bytes of SHA-256 of UTF-8
`sms24-job-checkpoint:v1:` + job key, interpreted as a signed big-endian int64.
It uses `pg_try_advisory_xact_lock(bigint)`: nonblocking, stable between processes,
independent of Python `hash()`. A theoretical hash collision only serializes two
different jobs; it cannot permit two holders for the same job. Every participant
must use the same database and key. These are cooperative PostgreSQL locks.

`False` means do not read/process that job; leave the transaction and retry later.
Other repository methods acquire/check the lock too, raising the static
`CheckpointLockNotAcquired` if busy. They never rely on cached lock ownership.
Lock acquisition inside a savepoint is rejected; acquire it before the runner's
savepoints. Commit, rollback or connection loss releases it automatically.
No repository method commits or rolls back. No lock is held across scheduler sleep.

The future caller performs in **one transaction on one session**:

1. Acquire the lock, then `get()` or `get_or_create()`.
2. For an idle/completed job only, `start_run(reference_date=..., max_teams=..., max_players=...)`.
3. Call `run_sms24_automatic_transfers` with the stored date, limits and cursor.
4. For a nonterminal result, call `save_progress(result)`.
5. For a terminal result, inspect business outcomes and explicitly call `complete_run(result)`.
6. Commit observations and checkpoint together.

`get()` returns None for an absent job. `get_or_create()` creates an idle job;
`start_run()` also supports an absent job. Progress/completion without a running
traversal fails. Starting another traversal while one is running fails, even with
the same parameters: resume instead. Read results are immutable snapshots, not
mutable ORM rows. Only a new traversal can change its date/limits and reset its
cursor/failure count. Existing `TransfersRunner` savepoints remain unchanged.

`next_cursor=None` is **not automatic success**. `save_progress` rejects it.
`complete_run` is an explicit caller decision, rejects remaining pages and rejects
any `discovery.reason` (including unavailable capability/provider). Individual
team/player failures may advance progress; completion retains their count as
`completed_with_errors`. This is traversal exhaustion, not a claim that every
target was successfully ingested. The future scheduler decides when to retry.

Before commit, rollback/connection loss discards both observations and the new
checkpoint, preserving the previous continuation for replay. After commit, both
advance together. This is at-least-once execution, with possible repeated HTTP
requests and existing observation idempotence. SQL failures propagate.

A subsequent explicit `start_run` resets both cursor bounds and fixes a new date
and limits. This new sweep discovers IDs added before old bounds. Continuations
remain stateless keyset boundaries, not snapshots: changing provider memberships
can still affect a resumed team slice. No human identity or canonical resolution
is created by checkpointing.
