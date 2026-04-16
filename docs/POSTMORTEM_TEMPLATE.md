# Postmortem — <Title>

> Save as `docs/runbooks/postmortems/YYYY-MM-DD-<slug>.md` and remove this
> note before publishing.

## Metadata

- **Severity:** SEV-N
- **Status:** Resolved / Mitigated / Ongoing
- **Date of incident:** YYYY-MM-DD
- **Detection time (UTC):** HH:MM
- **Mitigation time (UTC):** HH:MM
- **Resolution time (UTC):** HH:MM
- **Total duration:** Hh Mm
- **Customer impact window:** HH:MM → HH:MM
- **Affected:** <count of users / merchants / transactions>
- **IC:** @handle
- **Author:** @handle

## Summary

<2-4 sentences: what happened, who was affected, how long, what we did.>

## Impact

- Users / merchants affected: <count + how>
- Transactions affected: <count + total $>
- Data integrity: <none / <describe>>
- Reputation / external: <internal-only / customer-visible / public>
- Money moved incorrectly: <yes/no, amount, status>

## Timeline (UTC)

```
HH:MM   Event
HH:MM   Event
HH:MM   Detection
HH:MM   On-call paged
HH:MM   Incident channel opened
HH:MM   Hypothesis: ...
HH:MM   Mitigation attempt: ...
HH:MM   Mitigation succeeded
HH:MM   Confirmed via <metric / log / customer report>
HH:MM   Incident resolved
```

## Root cause

<What actually broke, in technical detail. Walk through the failure chain.
Include code links / commit SHAs / log snippets where relevant. Do not
write "X did Y" — write "X happened because Z".>

## Contributing factors

- <Factor 1, e.g., "no integration test for the application_fee_amount edge case">
- <Factor 2, e.g., "alert threshold was set 10× too high">
- <Factor 3, e.g., "rollback runbook was out of date">

## What went well

- <e.g., "On-call ACK'd within 90 seconds">
- <e.g., "Render rollback completed cleanly">
- <e.g., "Postmortem channel made customer outreach decision in 5 minutes">

## What went poorly

- <e.g., "We didn't have a metric for this; detection came from a customer email">
- <e.g., "The fix required schema knowledge that only one person had">
- <e.g., "Communication to merchants was delayed by 40 minutes while we drafted">

## Where we got lucky

- <e.g., "The bug was deployed at 2am; only 3 transactions were attempted before mitigation">
- <e.g., "Stripe rejected the bad PaymentIntents instead of accepting them">

## Action items

| ID | Action | Owner | Severity | Due | Issue/PR |
|---|---|---|---|---|---|
| AI-1 | <add metric for X> | @handle | high | YYYY-MM-DD | #N |
| AI-2 | <add integration test for Y> | @handle | medium | YYYY-MM-DD | #N |
| AI-3 | <update runbook Z> | @handle | low | YYYY-MM-DD | #N |

Action items must be:
- Concrete (a PR can close it)
- Owned (one human, not "the team")
- Dated
- Tracked in the issue tracker

## Lessons

<2-3 sentences. The non-actionable insight worth carrying forward. What
will we look at differently the next time we design a feature?>

## Appendix

- Logs:
- Dashboards / charts:
- Related incidents / postmortems:
- Stripe dashboard cross-reference (if payments touched):
