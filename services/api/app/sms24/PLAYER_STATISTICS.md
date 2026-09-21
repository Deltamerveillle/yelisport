# Player Statistics foundation (0037)

These are multisport provider observations, **not AthletePerformance or SMS Proof**.
No adapter, runner, worker, scheduler, public endpoint, capability activation or
HTTP call is introduced. Existing Transfers code and migrations through 0036 are
unchanged; its worker remains disabled by default.

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
