# TODO-040 Provider Failover Design

## Goal

Add automatic provider failover for concrete imagery texture downloads so a
temporarily failing provider does not stall an entire tile build when another
loaded provider can serve the same orthogrid texture.

## Scope

The first failover layer applies to the async Step 3 texture download scheduler.
That scheduler already owns texture retry policy and receives texture attributes
as `(til_x_left, til_y_top, zoomlevel, provider_code)`, so it is the narrowest
place to detect repeated provider failures and choose a replacement provider.

Combined providers remain outside this first failover surface. They already
encode layered regional selection, extent masks, and priority rules, so treating
them as a simple provider list would risk changing intended scenery output.
Concrete providers are eligible when they are present in `providers_dict`.

## Provider State Contract

`O4_Provider_Failover` owns a small thread-safe registry:

- consecutive failure count per provider code;
- blacklist expiration timestamp per provider code;
- configurable threshold of 3 consecutive failures;
- configurable timeout of 300 seconds.

Every failed texture attempt records a provider failure. When the count reaches
the threshold, the provider is blacklisted until the timeout expires. Every
successful texture attempt records provider success and clears that provider's
failure count and blacklist state.

The registry uses a `threading.RLock` so parallel download tasks and future
parallel build surfaces can update state safely.

## Provider Selection

Failover selection is deterministic. Candidate providers come from
`IMG.providers_dict`, excluding the failed provider and any currently
blacklisted provider. GUI-visible providers are preferred over hidden providers;
ties are resolved by provider code. This gives stable behavior while preserving
the existing provider inventory as the source of truth.

When a queued texture fails and the original provider is blacklisted, the
scheduler rewrites only the provider code and requeues
`(til_x_left, til_y_top, zoomlevel, replacement_provider_code)`. Tile
coordinates and zoom level remain unchanged. If no replacement provider is
available, the existing retry and final failure summary behavior remains in
effect for the original provider.

## Diagnostics

Provider blacklist and failover decisions are logged with structured
`UI.log_event()` calls and concise visible output. Logs include the failed
provider, replacement provider when one is selected, texture attributes, failure
count, threshold, and blacklist expiration.

## Tests

Unit tests cover:

- success resets provider failure state;
- 3 consecutive failures blacklist a provider for 5 minutes;
- expired blacklist entries become eligible again;
- provider selection skips blacklisted providers and is deterministic;
- the async download scheduler requeues a failed texture with a replacement
  provider after the threshold is reached;
- a later successful replacement texture is enqueued for conversion and resets
  replacement provider state.
