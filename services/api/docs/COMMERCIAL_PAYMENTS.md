# SMS commercial plans and local payment initiation V1

`SMS_COMMERCIAL_PLANS` is a JSON array parsed by application Settings. Default: `[]`.
No commercial price, currency or offer is seeded. Configuration errors fail validation.
Each entry requires `plan_code`, public `name` / `description`, `amount_minor` (positive
integer in minor units), uppercase three-letter `currency`, and `duration_days`
(a fixed prepaid term, not recurring billing). `active` and `purchasable` both default
to false. Both must be true to list/buy an offer. Duplicate codes and paid `free`
are rejected. No new entitlements are granted by configuration.

## Purchased term snapshot (0041)

Initiation snapshots plan code, amount, currency and positive duration_days. Pending
reuse preserves all four terms even when the catalogue changes. The owner-safe payment
response exposes duration_days (nullable for legacy purchases). No client can set it.

Migration 20260926_0041 adds a nullable integer and CHECK duration_days > 0, with no
default or historical backfill. NULL explicitly means there is no authoritative
purchased duration. New commercial initiations always set the configured positive value.
Legacy pending rows remain NULL even when reused and cannot be activated; manual historical
reconciliation is outside this block. Never infer their duration from today's catalogue.
Downgrade removes only this check/column, losing duration snapshots.

Verified activation requires an aware period_start and normalizes it to UTC. SMS derives
period_end = UTC period_start + duration_days elapsed 24-hour days. An optional provider
period_end is accepted only when aware and exactly equal to that derived instant.
Shorter/longer terms, expired terms and datetime overflow are rejected before mutation.
The current catalogue is never consulted. No external provider integration is included.

Already-succeeded payments with matching verified facts and provider transaction identity
return unchanged before term validation: replay cannot create or modify a subscription,
even after expiry or for an already-succeeded legacy payment. This is not a legacy
activation bypass. A different provider transaction identity still fails.

## API

- GET `/api/v1/payments/plans`: public purchasable offers only.
- POST `/api/v1/payments/initiate`: authenticated; body contains only `plan_code`.
  Extra fields (price, currency, provider, duration, status, user identity) are rejected.
- GET `/api/v1/payments/{transaction_id}`: owner only; absent and foreign IDs return 404.

Initiation stores a pending transaction with a cryptographically random SMS reference
and `subscription_id=NULL`. `manual` is the explicit local verification channel,
not a connected payment processor. There is no checkout URL, external request,
success simulation, or client confirmation route. Pending does not mean paid.
Public transaction fields exclude user ID, provider transaction/customer information.

## Transactions and retries

Initiation locks the existing user row with SELECT FOR UPDATE, then reuses an existing
pending transaction for that user and plan. Replay returns its original amount/currency/duration
and timestamps even if the configuration's price changes. No cross-user reuse occurs.
Once terminal, a new request can create a new purchase: this is pending-intent deduplication,
not an indefinitely retained idempotency-key protocol. Pending intents have no automatic
expiry/cancellation in V1. Disabled/removed offers cannot be initiated or replayed, but
existing payments remain owner-readable and internally verifiable.

Verified confirmation/failure acquire the same user lock and then reread/lock the
payment before mutation. This prevents concurrent confirmations from activating twice
and serializes subscription replacement for the same user. Existing unique reference
and provider transaction constraints remain the final database safeguards. SQL errors
propagate; collisions are never silently treated as successful replays.

The HTTP endpoint validates its response before commit and rolls back on any exception.
Repositories/services do not commit. PaymentService.confirm_verified_payment remains
the sole activation boundary; it is never routed to clients. Its caller must commit
or roll back the entire verified operation. Historic has_premium_access behavior is unchanged.

Other than migration 0041, no mobile changes, external payment credentials, entitlements redesign,
Discover/Connect access changes, or consent changes are included.
