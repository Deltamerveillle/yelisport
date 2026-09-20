# Transfers foundation (0034)

This is local persistence and domain validation only. There is no transfer runner,
HTTP adapter, API endpoint, automatic human linking, or new capability activation.
The existing `transfers` capability and provider registry remain the integration boundary.

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
