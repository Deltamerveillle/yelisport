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

## Explicit commercial entitlements V1

Each server-side CommercialPlan may declare an `entitlements` object with six strict
boolean fields: talent_access, enhanced_profile, discover_visibility, connect_access,
statistics_insights and priority_visibility. Every field defaults to false. Unknown
fields and boolean coercions are rejected; no existing plan gains implicit capabilities.
No prices or plan configurations are introduced.

SubscriptionService.get_access is the authoritative resolution path exposed by authenticated
GET /api/v1/subscriptions/me/access. It reads the current subscription once and resolves its
plan_code in the current server catalogue. No subscription, free/inactive/expired access,
unknown plan or omitted configuration means no explicit capabilities. Active and trialing
subscriptions can receive exactly the configured flags. As before, a subscription without
an end date may be current. Plan active/purchasable flags govern new sales, not existing
subscribers: retain the plan entry when discontinuing sales but maintaining its capabilities.
Entitlements are current server policy, not a payment terms snapshot. Removing a plan
from the catalogue fails closed for explicit capabilities.

The legacy has_premium_access contract remains active/trialing, unexpired, non-free access,
including unknown or unconfigured paid plans. It can be true while every explicit flag is
false. SMS Talent still uses this legacy authorization; talent_access does not replace it
in V1. Future enforcement changes require a separate explicit compatibility decision.

These flags currently expose policy only: no new Discover/Connect paywall or sporting
ranking/scoring advantage is introduced, including for priority_visibility. Athlete
available_for_opportunities remains separate consent and is never read, inferred or changed
by entitlement resolution. Payments, subscriptions, capabilities and consent remain distinct.
Clients cannot submit entitlements through payment initiation or update subscription access.
No migration or entitlement persistence table is required.
