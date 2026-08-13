# Golden-set authoring rules

`seed_cases.jsonl` contains policy-critical seed cases for the first evaluation harness. They are scaffolding, not a substitute for the 250–300 case human-reviewed canonical set required before release.

Each line must conform to `schemas/golden_case.schema.json` and record:

- the expected intent, product type, grain, date, filters, metrics, sort, and clarification behavior;
- deterministic result assertions such as included/excluded counts, tie handling, currency separation, or quarantine behavior;
- answer semantics that must appear and prohibited claims that must not appear;
- a review record that truthfully identifies who reviewed the case and the supporting source.

## Review workflow

1. Derive the deterministic answer with the reference implementation.
2. Inspect the exact official source rows and evidence locators.
3. Have a human reviewer approve the case.
4. Replace `AI-handoff-seed` in the review block with the reviewer name or team role.
5. Run schema validation and the scoring harness.

Never generate expected product IDs or numeric results with an LLM and accept them without deterministic verification.
