<!--
Thanks for the PR. Please complete every section. PRs missing the test plan
or that don't update the relevant docs will be sent back.
-->

## Summary

<!-- 1-3 sentences. What is this changing and why. -->

## Type of change

- [ ] feat — new feature
- [ ] fix — bug fix
- [ ] refactor — internal change, no behavior difference
- [ ] perf — performance
- [ ] docs — documentation only
- [ ] chore / ci / build
- [ ] security — vulnerability fix or hardening

## Linked issues

Refs: #
Closes: #

## Test plan

<!--
Mandatory. List every check you ran. For UI changes include screenshots.
For backend changes include the curl/HTTPie request and the response.
For schema changes include the migration plan and rollback.
-->

- [ ] Unit tests added/updated
- [ ] Integration test for the happy path
- [ ] Manual verification: <describe>
- [ ] Negative paths exercised: <describe>

## Security checklist

- [ ] No secrets, tokens, or PII in the diff or in logs introduced
- [ ] Inputs validated at the boundary
- [ ] If touching auth/crypto/payments: request review from a `CODEOWNERS`
      security entry
- [ ] No `innerHTML` writes added without HTML escaping
- [ ] Rate limiting in place on any new endpoint
- [ ] Updated `docs/THREAT_MODEL.md` if this introduces a new trust boundary

## Documentation

- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] If endpoints changed: `docs/API.md` updated
- [ ] If schema changed: `docs/DATABASE.md` updated + migration created
- [ ] If a non-trivial decision was made: ADR added under `docs/adr/`

## Rollout

- [ ] Backwards compatible OR migration plan documented
- [ ] Feature flag if appropriate
- [ ] Rollback plan: <describe — usually `git revert <sha> && redeploy`>
