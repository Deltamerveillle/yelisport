# SMS commercial plans and local payment initiation V1

`SMS_COMMERCIAL_PLANS` is a JSON array parsed by application Settings. Default: `[]`.
No commercial price, currency or offer is seeded. Configuration errors fail validation.
Each entry requires `plan_code`, public `name` / `description`, `amount_minor` (positive
integer in minor units), uppercase three-letter `currency`, and `duration_days`
(a fixed prepaid term, not recurring billing). `active` and `purchasable` both default
to false. Both must be true to list/buy an offer. Duplicate codes and paid `free`
are rejected. No new entitlements are granted by configuration.

Use versioned plan codes. Keep commercial terms for an issued code immutable;
create a new code when changing a term, and retain old definitions for verification.
The existing payment table snapshots amount, currency and plan code, not duration.
The trusted verification layer remains responsible for period_start / period_end,
including applying the purchased term. This block neither calculates nor automatically
validates that period against the catalogue. Do not treat the mutable current catalogue
as evidence of the terms of an older purchase. A future external integration needing
self-contained durable term snapshots will require a dedicated schema extension.

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
pending transaction for that user and plan. Replay returns its original amount/currency
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

No migration, mobile changes, external payment credentials, entitlements redesign,
Discover/Connect access changes, or consent changes are included.
