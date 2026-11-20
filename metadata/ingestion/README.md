# ING1.01 feasibility evidence

`ING1.01.json` records the initial partial audit; `ING1.01-local.json` records the
bounded development-host samples. Neither is dataset acceptance or redistribution
permission. Host and observation timestamps must remain distinct.
`ING1.01-github.json` is the generated metadata from successful manual run
`44717385649` at commit `6cd8c2d7d3728afe47ac43f0981cdf545b014ea2`;
individual access/schema failures remain visible. A green audit is not all-source success.

Manual-only `.github/workflows/ing1-access-audit.yml` runs the same
`scripts/ing1_access_probe.py` on a standard public Ubuntu runner with read-only
repository permissions, no private credentials, no schedule and no payload uploads.
Its stdout records sanitized metadata/checksums; inspect failed sources individually.

Offline tests: `python -m pytest tests/test_ing1_access_probe.py`.
Local live run: `python scripts/ing1_access_probe.py --host-label local-development`.
No installation, private DB access or collector execution is needed.

This directory is tracked because the existing repository deliberately ignores
`docs/`; that ignore policy is unchanged. Canonical dataset definitions/approval
ledger remain in private ArthikaMF, not duplicated here.
