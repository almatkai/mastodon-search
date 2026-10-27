# Mastodon Search — Rust V2

Standalone Rust implementation of **Search Mastodon**. Search People or Hashtags on your selected instance, visit profiles or hashtag pages, and copy a profile URL or handle. The required **Instance** text preference defaults to `mastodon.social`. No account, credentials, posting, following, or authentication is required.

This is a source candidate for parent review. `extension.json` uses schema 3, Rust process execution and protocol 1, replaces `com.tezbar.mastodon-search` and `raycast.mastodon-search`, and intentionally has `artifacts: {}`. Both native verification entries remain **not-run**. Nothing has been published or installed.

The executable uses the independent SDK 0.1.1 over immutable HTTPS Git revision `e955911f0bf5b558f9d3eb5183df0adc95c22af2`. It has no JavaScript engine and no runtime dependency on the parent, host, SDK checkout, or another extension. Rust 1.85 is the minimum. Intended targets are macOS ARM64 and Windows x64 MSVC.

The original 512 × 512 Raycast command icon is copied byte for byte. Its SHA-256 is `cf8072956e54114ab4044849f5e5441577ec56676a942c9d8aced00648169c09`. Fresh upstream bytes at `6734d85992290066fd31a7f5bee3cca3d3545a1a` match the own Git asset and this copy. Source/provenance and authentic licenses are retained under `qa/fixtures`, `qa/evidence`, and `licenses`.

See [behavior and bounds](BEHAVIOR.md), [reproducible verification](qa/README.md), and the [unapplied host prerequisites](integration/README.md). The host proposal must be reviewed separately before installed-host acceptance; the actual host and SDK were never edited or built.

Build independently with existing toolchains:

```sh
cd v2
python3 qa/env.py cargo build --locked --release --bin mastodon-search
python3 qa/env.py cargo test --locked
```

The wrapper changes only the child environment and places mutable build/cache/temp data in this `v2/.work` directory. Full reproduction uses `python3 qa/run.py`. It never installs a toolchain or a host. The development ZIP, extracted executable, file hashes/modes and fresh-build provenance are recorded in [package evidence](qa/evidence/package.json); the ZIP itself stays ignored in `.work`.

Review checkout: `feat/native-v2-rust`, base/HEAD `dd73024af23ed7d716421592aac26c323500206d`. Temporary project registration for eventual **parent-only** cleanup: `mcp:66119403-0acd-46af-b333-f17db1a00bde`. The clone stays intact, unstaged and uncommitted.
