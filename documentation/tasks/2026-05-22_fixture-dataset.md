# fixture-dataset

**Identified by:** Veteran Developer (review 01), task 9; First-Time Contributor (review 02), task 6

## Problem

The test suite (36+ tests) has no shared plaintext fixture corpus. Tests that exercise the parsing pipeline must either generate synthetic input inline or depend on live data files that are gitignored. This means:

- A new contributor cannot run the full test suite after `git clone` without either obtaining the ZDF corpus (requires a data agreement) or understanding which tests are data-dependent
- Pipeline regressions triggered by real-data edge cases cannot be added to the test suite without exposing private data
- Two reviewers independently flag this as the single most important contributor-experience gap below CI setup

## Action (code-scope, deferred)

Create a 5-episode plaintext fixture dataset in `speakermining/test/fixtures/`:

1. Construct 5 synthetic or anonymised episode text files that exercise all known `parsing_rule` values in mention detection
2. Include at least: one episode with a single explicit guest, one with multiple guests, one with an ambiguous name form, one with a "Gast:" label variant, one with no guests (negative case)
3. Add corresponding expected-output rows to a `fixtures/expected_persons.csv`
4. Update existing tests to use these fixtures as the default data source; gate live-data tests with a `@pytest.mark.requires_corpus` marker
5. Document fixture construction approach in `speakermining/test/README.md` (or add a section to `CONTRIBUTING.md`)

Prerequisite: T27 (CI setup) — fixtures only fully pay off once CI is running.

## Definition of done

1. `speakermining/test/fixtures/` contains at least 5 episode text files and one `expected_persons.csv`.
2. All `parsing_rule` values in mention detection are exercised by at least one fixture.
3. Tests that require the live corpus are marked `@pytest.mark.requires_corpus` and skipped in CI by default.
4. CI passes on a fresh `git clone` with no corpus files present.
