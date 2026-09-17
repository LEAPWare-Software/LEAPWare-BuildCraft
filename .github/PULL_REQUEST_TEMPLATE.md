## Summary

<!-- What changed and why. -->

## Checklist

- [ ] `python -m pytest -q` passes
- [ ] `python scripts/lwb_build.py --check` passes (or `scripts/lwb_build.py` was
      run and the resulting `vendor/` diff is included, if this PR is
      expected to change it)
- [ ] `python scripts/lwb_validate_claude_plugin.py` passes
- [ ] `python scripts/lwb_validate_codex_plugin.py` passes
- [ ] No third-party runtime import added under `core/` or `adapters/`
- [ ] If a rule was added or changed: unit tests cover `off`/`warn`/`deny`
      and a non-applicable-event case, and `docs/rules/` was updated
