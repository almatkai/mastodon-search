# Separate, unapplied host prerequisites

`host-prerequisites.patch` targets immutable host commit `ea100cee3f69711de12485ba061950c5fc65258f`. No real host working file, SDK, sibling extension, profile, ledger or registration has been changed. The fixture copies came only from `git show <exact-pin>:<path>`. Do not apply this proposal as part of publishing the extension source.

The generic changes are necessary for this source UI:

1. Fence typed input at input time, before the existing debounce; send a draft-only native revocation and later promote the same client revision. Independently reject older native snapshots, refreshes and action results. Propagate generic input callbacks through the parent surface and add optional typed request fields.
2. Honor a controlled dropdown value and source `storeValue`, retaining only the selected value under an extension/command storage key. Keep optimistic selection during a pending draft. Preserve source tooltip and option ordering.
3. Expose an Actions button and source row shortcuts, including the Windows control-key equivalent of command modifiers. Native error retries are bound to row action IDs so the selected-row action filter cannot hide them.
4. Honor custom empty/loading states, rounded avatar masks, bot/follower icons and tooltips, and Hashtag/ComputerChip/TwoPeople symbols.
5. Bound remote raster reads and validate dimensions before using an object URL; abort/release on ownership change and unmount. Original extension icon bytes remain an asset, with no redraw or image conversion.

Regenerate and test the proposal entirely inside the clone:

```sh
python3 qa/prepare-host-patch.py
python3 qa/env.py node qa/renderer.cjs
python3 qa/env.py node qa/typecheck-host.cjs
```

`qa/fixtures/host` is the exact original. `.work/host-patched` is a disposable derived fixture; the tracked patch is the review artifact. The original List, parent and icon/accessory functions reproduce the deficiencies; corrected functions pass the same tests. The seam-based type check has no baseline or proposed diagnostics. It does not replace a full host build or installed native acceptance, which remain parent follow-up work.
