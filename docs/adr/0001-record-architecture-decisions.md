# ADR-0001: Record architecture decisions

## Status

Accepted

## Date

2026-04-16

## Context

FingerPay has accumulated a number of significant architectural choices
without explicit records. New engineers reverse-engineer rationale from
code, which is slow and often wrong. Decisions get re-litigated because
nobody remembers why we picked option A over B.

We need a lightweight way to capture decisions as they're made, so that:

- A new engineer can read 30 ADRs and understand "why is it like this?"
  without bothering anyone.
- We can revisit and supersede a decision explicitly rather than via
  silent code change.
- Reviewers can flag PRs that contradict prior decisions.

## Decision

Adopt **Architecture Decision Records (ADRs)** in the repository under
`docs/adr/`, following [Michael Nygard's format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

Conventions:

- Files named `NNNN-<short-slug>.md`, sequentially numbered, never
  renumbered.
- One decision per file.
- Status values: `Proposed`, `Accepted`, `Deprecated`, `Superseded by
  ADR-XXXX`.
- Use the template at `docs/adr/0000-template.md`.

When to write an ADR:

- Picking between two or more credible technical options.
- Adding a new core dependency.
- Changing a public contract (API, schema, env vars) in a non-trivial
  way.
- Establishing a new conventional pattern others will be expected to
  follow.
- Anything you'd want explained if you came back in six months.

When **not** to write an ADR:

- Bug fixes.
- Internal refactors that don't change a contract.
- Anything fully captured by the PR description.

## Consequences

### Positive

- Decisions are durable and discoverable.
- New engineers ramp faster.
- Architectural drift is visible — superseded ADRs make the change
  history obvious.

### Negative

- Slight overhead per significant change.
- Risk of ADRs being written but never read; mitigated by linking from
  CONTRIBUTING.md and the onboarding guide.

### Neutral

- We need to backfill ADRs for the most consequential decisions already
  made (next several ADRs do this).

## References

- https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- https://adr.github.io/
