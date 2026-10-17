# Player Statistics foundation (0037)

These are multisport provider observations, **not AthletePerformance or SMS Proof**.
The foundation itself performs no HTTP calls. The optional Sportmonks adapter
below returns provider contract values only. The explicit-target runner described
below persists observations. No Statistics worker, scheduler, public endpoint or
capability activation is introduced. Transfers
behavior and migrations through 0037 remain unchanged.

## Explicit-target transactional runner

`PlayerStatisticsRunner.run(targets=...)` accepts a nonempty mapping from normalized
provider slugs to frozen `PlayerStatisticsTarget(athlete_external_id, sport_id)`
values. The athlete ID uses the existing text validator (160 characters maximum),
and sport_id must already be a UUID, never a string to coerce. Subclasses or other
target shapes are rejected. A copy of the input mapping fixes targets for the call.

The caller explicitly supplies the sport context for each target; the authoritative
catalogue is `Sport`. One query validates that every requested UUID exists and is
active before any provider call or observation write. An invalid target rejects the
whole request with ValueError. There is no provider-to-sport mapping and no inference
from a URL, name, team, metadata or existing SportsCompetitor. The same provider can
be called with different explicit sports. Choosing the appropriate sport for the
upstream request remains the caller's responsibility.

Only active sources with an active `statistics` capability are eligible. The runner
uses the existing provider registry, callable method check, health result and
Player Statistics validators (the result contract requires a tuple). Every returned
athlete_external_id must match the requested string exactly. Failures expose static
internal reason codes; restricted access is distinguished from health/fetch failure.

Each complete provider batch gets a savepoint, including its final flush. Only
`SMS24PlayerStatisticsRepository.record_observation` writes observations, receiving
the exact source UUID and target sport UUID. ValueError during ingestion rolls back
the batch and records `ingestion_validation_failed`; SQLAlchemyError and unexpected
persistence failures propagate. The caller owns the outer commit/rollback. No source
health or capability is changed.

All eligible targeted providers are attempted. One successful provider is sufficient
for a result; otherwise `PlayerStatisticsAllProvidersFailed` retains the sanitized
attempts. A valid empty tuple is success with zero processed observations and deletes
nothing. Processed counts include idempotent replays and ignored stale snapshots.

No provider athlete row is required or created. The runner never resolves
athlete_competitor_id, fixture_id, canonical_fixture_id or season_id. In particular,
Sportmonks season/team/position IDs stay raw metadata, not canonical graph UUIDs.
No human model, identity link, performance or verification is created or updated.
The actual Statistics capability remains unactivated; tests enable it only in their
disposable fixtures. There is no runtime scheduling or public entry point here.

## Sportmonks Football V3 season adapter

`SportmonksProvider.fetch_player_statistics(athlete_external_id=...)` uses the
existing authenticated `_get_json` path for `/players/{id}` with
`include=statistics.details.type`. The request ID, player response ID and every
statistics.player_id must match exactly under the existing strict Sportmonks
positive ASCII decimal ID rules. A valid `statistics=[]` returns an empty tuple.

Each season statistics object's own `id` is its `external_id` (for example
27324842 in the verified payload), independently of player/team/season IDs.
`record_reference`, `fixture_external_id`, `period_label` and `source_updated_at`
stay None: no supported period label or record timestamp has been demonstrated.
The scope is always `season`; a valid player name is display evidence only.

Metrics use sorted string type-ID keys. Each contains the validated raw detail ID,
raw type ID, available type labels (including model_type), and the exact JSON-native
value. Missing `value` is rejected; explicit null and zero stay distinct. Missing
type labels remain absent; a supplied `type` must be an object. Duplicate statistics
IDs, duplicate type IDs and mismatching parent/type/player IDs reject the response.
Output observations are sorted by their normalized opaque external ID.

Metadata is limited to team_id, season_id, position_id, jersey_number and has_values.
Optional nulls remain null; absent fields remain absent. IDs are validated without
rewriting their raw representation. A known jersey number must be a nonnegative
integer (never bool, float or numeric string); a known has_values must be a bool.
No arbitrary HTTP/player fields are copied, and no local season or identity is
resolved. Calling this adapter does not persist anything or enable a capability.

## Provider identity and unknown facts

`ProviderPlayerStatistic` requires an opaque `athlete_external_id` and either a
genuinely stable provider row `external_id`, or a stable opaque `record_reference`.
Neither field may be manufactured from metrics, names, dates, period labels or
list positions. A future adapter must document the stability of its identifier;
the foundation cannot prove upstream semantics. Without such evidence ingestion
must not proceed. Switching identity strategies requires explicit reconciliation.

`observation_key` hashes a tagged pair of identity kind and exact opaque value,
preferring `external_id` when supplied. Source/key and source/external-ID uniqueness
keep different providers separate. The hash excludes athlete names, athlete IDs,
sport, fixture context and all metrics. Reusing a record for a different athlete
or sport is rejected, including for a stale snapshot.

The caller supplies explicit `sport_id` and `source_id`; the provider contract has
no local graph UUIDs. `scope` is unknown/fixture/season/competition/career/other.
`period_label` remains an opaque provider label, never a season-resolution rule.
Metrics and metadata must be JSON objects containing finite, native JSON values
with string keys: no tuple/key coercion, NaN or Infinity. Values stay provider facts:
an absent key, explicit null, and zero remain distinct. Snapshot updates replace
the JSON objects rather than retaining stale keys. No verification status exists.

`fixture_external_id` is intentionally nullable and provider-neutral: a snapshot
can refer to a provider contest before its local fixture is ingested/resolved.
This enables later exact-ID validation without parsing a record reference or
canonical key. It does not identify the statistics record. No season external-ID
convention, sport-specific metric columns or provider-specific type mapping is
assumed. Other raw context can remain in metadata.

## Persistence and explicit resolution

`SMS24PlayerStatisticsRepository.record_observation` uses PostgreSQL uniqueness
plus a row lock to serialize competing inserts/updates. A strictly older
`fetched_at` is ignored; an equal timestamp may update, as in Transfers.
`source_updated_at` is preserved but does not replace this freshness rule.
Savepoints isolate invalid attempts; the caller owns commit/rollback, and SQL
errors propagate. This is the latest snapshot, not an append-only history.

Only `resolve_observation` sets graph foreign keys, using explicitly supplied IDs:

- Athlete: exact source, external ID, sport and `competitor_type='athlete'`.
- An already-linked canonical athlete must have the same sport and athlete type;
  the repository never creates or changes that link.
- Provider fixture: same source/sport and exact reported `fixture_external_id`.
  A new fixture resolution without that reported ID is rejected.
- Canonical fixture: requires the resolved provider fixture's existing explicit
  canonical mapping, and matching sport. A canonical fixture alone is insufficient.
- Season: its canonical competition must have the same sport. With a fixture,
  that fixture's provider competition must explicitly map to the same canonical
  competition. Missing mappings are rejected, never guessed from labels/dates.

The existing graph does not have a fixture-to-season foreign key. The foundation
therefore validates competition membership and sport, **not** an inferred season
calendar or an athlete's actual participation. The caller authorizes these explicit
decisions. Omitted optional resolution IDs preserve existing links; different IDs
are rejected. No removal/replacement workflow is introduced.

Ingestion never changes graph links and checks their coherence on accepted
snapshots. A conflicting reported fixture ID is rejected; a later unknown fixture
ID can remain null without erasing an earlier explicit mapping. Direct SQL writers
must use this repository for cross-table consistency: foreign keys alone cannot
enforce the source/type/sport graph. Graph changes outside this repository remain
the responsibility of their existing explicit reconciliation workflows.

The only written table is `sports_player_statistic_observations`. No User, Athlete,
Profile, SportsCompetitor, canonical entity, identity link or AthletePerformance
is created or mutated. Any future promotion to human performance/proof requires a
separate explicit authorization and evidence layer.

## Migration and tests

0037 creates only this table, with explicit non-null sport/source foreign keys,
nullable resolution foreign keys (`ON DELETE RESTRICT`), identity uniqueness,
scope/identity/JSON-object checks, and indexes on sport, source, each resolution ID
and fetched_at. Downgrade drops only this table. No capability is seeded.

PostgreSQL tests reuse the opt-in `SMS24_MIGRATION_TEST_DATABASE_URL` fixture with
unique rollback-only schemas and no public fallback. Alembic round trips must use
the disposable `yelisport_0037_test` database, never the development database.
