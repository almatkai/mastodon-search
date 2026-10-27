# Reproduce the review evidence

All mutable dependency installations, Cargo homes, targets, fake HOME/XDG/temp directories, certificates, loopback fixture data, extracted packages and development ZIPs belong under this clone's `v2/`. No actual Mastodon request, user clipboard/browser/profile operation, host build, global configuration change or installer is part of QA.

Existing tools used: stable Rust 1.98.0, Rust 1.85.0, Node 26.7.0/npm 12.0.2, Python 3.9.6 and the already-installed Python 3.14 (`tomllib` for archive auditing), OpenSSL, macOS `file`/`otool`. No `rustup`, MinGW, SDK or global package installation is performed. `qa/env.py` chooses an existing toolchain, preserves its read-only Rustup home and changes only each child's environment; it never mutates the caller's HOME.

From `v2`, the complete workflow is:

```sh
python3 qa/run.py
```

It installs exact V1 dependencies into `.work/v1` from the frozen own package/lock, runs the unmodified V1 test and type check, installs exact schema QA dependencies under `qa/schema`, runs Rust/toolchain checks, audits real locked registry archives, builds the test-only transport helper, performs a fresh production build, extracts a deterministic development ZIP, tests actual pipes, regenerates the separate host proposal, and inventories the unstaged candidates. Source `artifacts` and both native verification states stay unchanged.

Useful focused commands:

```sh
python3 qa/env.py node qa/source-oracle.cjs
python3 qa/env.py cargo test --locked
python3 qa/env.py +1.85.0 cargo test --locked
python3 qa/env.py cargo fmt -- --check
python3 qa/env.py cargo clippy --locked --all-targets -- -D warnings
python3 qa/env.py +1.85.0 cargo clippy --locked --all-targets -- -D warnings
python3 qa/env.py node qa/schema/check.cjs
python3 qa/env.py cargo fetch --locked
PYTHONDONTWRITEBYTECODE=1 python3.14 qa/audit-dependencies.py
python3 qa/env.py cargo build --locked --manifest-path qa/transport-helper/Cargo.toml
PYTHONDONTWRITEBYTECODE=1 python3 qa/package.py
python3 qa/prepare-host-patch.py
python3 qa/env.py node qa/renderer.cjs
python3 qa/env.py node qa/typecheck-host.cjs
PYTHONDONTWRITEBYTECODE=1 python3 qa/provenance.py
PYTHONDONTWRITEBYTECODE=1 python3 qa/inventory.py
```

`package.json` evidence names the extracted binary directory. Run the real SDK pipe suites with that path:

```sh
python3 qa/env.py python3 qa/pipes.py .work/extracted-<recorded>/bin/mastodon-search .work/target/debug/mastodon-owned-transport-helper
python3 qa/env.py python3 qa/production.py .work/extracted-<recorded>/bin/mastodon-search
```

The first suite proves genuine production TLS rejection, then uses the separate trusted transport helper for successful owned TLS/data/actions. That helper accepts only its explicit CA-file argument, has a direct-adapter invalid-preference case, and is never packaged. The second suite exercises every applicable genuine extracted-production operation that needs no successful HTTPS. The first suite also sends malformed/oversized/truncated frames to the actual production executable. Native acceptance is never inferred from test-only trust.

## Evidence and its scope

| Evidence | Finite coverage |
|---|---|
| `source-oracle.json` / `source-oracle.txt` | 12 complete-source/locked-bundle checks, including 60 WHATWG raw-template URL vectors and 12 actual locked MIME vectors; defaults, both sections, source rows/actions, string/numeric IDs, follower/bot/handles, duplicate/order preservation, A/B/A exact-key cache, loading/failed/empty retention and custom source error toast without a retry |
| Rust test logs | 9 tests on stable and 1.85: source URL/MIME/mapping oracles, type/body/depth/row bounds, JS length, closed ACKs, 140 scope cancellations after handler return then 128 live leases, complete original host clipboard/open producer functions with replaced effect boundaries |
| `pipes.json` / `owned-tls-pipes.txt` | 71 process/owned-TLS checks: real SDK JSONL, production CA rejection, separate helper success, four source action families, duplicates/fresh tokens, malformed ACKs/frozen retries, request-free refresh, A/B/A, invalid drafts/dropdowns/preferences and actual body cancellation, raw URL cases, malformed HTTP/JSON/MIME/depth/rows/body, redirects, late response/ACK, input-time revocation/promotion, rapid dropdown revisions, disposal/EOF/shutdown, 128 live sessions, malformed frames |
| `production-pipes.json` | 16 genuine extracted-production checks for defaults, current/foreign/stale controls, invalid/oversized drafts and instance, draft promotion, operation rejection, effect absence, capacity, shutdown and EOF |
| `renderer.json` / `renderer.txt` | 48 checks of actual original/patched List, parent, parsing, icon/accessory and bounded image functions in a deterministic React hook VM; reproduces baseline failures and verifies ownership, native model separation, dropdown persistence, source shortcuts, empty/loading presentation and image cleanup. This is not a rendered DOM or full host build |
| `host-types.json` | Complete original/proposed component bodies against real React 19 types, pinned wire types and typed generic seams: zero diagnostics for both. No host dependency install/build |
| `schema.json` | 20 full draft-2020 schema-3 positive/negative cases using locked Ajv and formats, including artifact/inventory path constraints |
| `v1-test.txt`, `v1-typecheck.txt` | Original exact-lock disposable smoke test (1) and type check pass. No V1 edits were made to obtain a pass |
| Windows GNU logs | Both attempts stop in the external `ring` C build: missing `x86_64-w64-mingw32-gcc`. Distinct toolchain/compiler block, not a Rust code pass or MSVC/native acceptance |
| `dependencies.json` | All 142 locked registry archive SHA-256 values verified; authentic notices copied. `r-efi` AUTHORS MIT grant preserved. Fresh checked npm archive SRI/SHA evidence binds the locked source bundle; actual missing Raycast API/utils archive license text recorded separately |
| `package.json` | Distinct newly-created empty CargoHome/target, pinned HTTPS Git SDK fetch, source/lock checks, production binary/ZIP hashes, closed per-file inventory/modes, fixed ZIP metadata and extracted production protocol smoke. Existing toolchain strip warning retained in `fresh-release.txt` |
| `provenance.json` | Full original Git V1 boundary, exact immutable host/SDK/source fixture bytes, original icon, selected root/branch/HEAD/remote, XERJ coverage and temporary registration |
| `candidate-inventory.json` | Every Git-visible README/V2 candidate except itself, with SHA-256/length/mode; no ignored durable fixture gap. It is an unstaged working-file inventory. Parent must rehash **staged blobs** before its commit |

The pipe cancel/open race can finish before its cancel reaches the SDK; such successfully completed opens are explicitly disposed in that race test. The separate lease test is the one that proves **140 cancellations after handler return, without adapter dispose, then 128 live leases** using actual SDK scope stop. A cancel frame for an already-returned request is inert in the pinned SDK; the port does not claim otherwise.

No installed macOS GUI, Windows MSVC runtime, public Mastodon service, crash durability, or universal source parity is claimed. See [bounds and gaps](../BEHAVIOR.md).

XERJ used canonical prefix `ax-6d9e093035a8` and state `/Users/almat/.local/share/xerj/workspaces/ax-6d9e093035a8`. The initial generation covered all 11 original code files. The final bounded refresh aborted in 0.6 s because the frozen dataset could not accept the new `v2/Cargo.toml` docs family. V2 search is incomplete; `Adapter` returned no match. No new prefix, schema/settings edits, bypass or server restart was attempted. Complete source/Git/`rg`/hash checks provide the fallback evidence.
