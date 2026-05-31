# Workflow Document Project Exclusions

The deterministic inventory must skip these paths before any excerpt is created:

- VCS and generated/cache directories: `.git/`, `.worktrees/`, `node_modules/`, `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `dist/`, `build/`. The `evals/runs/` output directory is excluded **at any depth**, not only at the project root (e.g. `skills/x/framework/evals/runs/` is skipped too).
- Secret-bearing files and directories: `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.keystore`, `id_rsa*`, `credentials`, `*secret*`, `.npmrc`, `.pypirc`, `.aws/`, `.ssh/`, `.gnupg/`.
- Directory matching is **case-insensitive** (`.AWS/`, `.SSH/`, `Node_Modules/` are excluded the same as their lowercase forms).
- Large binary files and files that cannot be decoded as UTF-8.

Every stored excerpt must run through deterministic redaction. The redactor masks:

- assignment forms for a broad keyword set — `api_key`, `secret`, `token`, `password`, `passwd`, `authorization`, `bearer`, `access_key`/`access_token`, `private_key`, and underscore/dash-joined names such as `aws_secret_access_key=...` and `client_secret: ...` (a bare `\b` would miss these);
- known provider key shapes that appear bare (e.g. `sk-...`, `AKIA...`, `ghp_...`, `xoxb-...`);
- genuinely high-entropy, key-shaped tokens — including secrets containing `/ + = -` (e.g. AWS secret access keys) — while deliberately **preserving** git SHAs, hex UUIDs, lockfile integrity hashes, and long `snake_case`/identifier tokens so the excerpt the synthesis pass cites is not corrupted.
