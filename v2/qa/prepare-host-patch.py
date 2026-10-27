#!/usr/bin/env python3
"""Generate a separate UNAPPLIED proposal from exact pinned host fixtures only."""
from pathlib import Path
import difflib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'qa/fixtures/host'
DEST = ROOT/'.work/host-patched'
PATCH = ROOT/'integration/host-prerequisites.patch'
changes = {}


def edit(path, replacements):
    original = (SOURCE/path).read_text()
    result = original
    for old,new in replacements:
        assert old in result, (path,old)
        result = result.replace(old,new)
    changes[path] = (original,result)


edit('src/renderer/src/raycast-api/list-runtime.tsx',[
    ("    tintColor?: unknown\n", "    tintColor?: unknown\n    mask?: unknown\n"),
    ("  actionId?: string\n", "  actionId?: string\n  value?: string\n  storeValue?: boolean\n  tooltip?: string\n"),
    ("    actionId: typeof node.props?.actionId", "    tooltip: typeof node.props?.tooltip === 'string' ? node.props.tooltip : undefined,\n    storeValue: node.props?.storeValue === true,\n    value: typeof node.props?.value === 'string' ? node.props.value : undefined,\n    actionId: typeof node.props?.actionId"),
    ("const icon = value as { fileIcon?: unknown; source?: unknown; tintColor?: unknown }", "const icon = value as { fileIcon?: unknown; source?: unknown; tintColor?: unknown; mask?: unknown }"),
    ("return { source: icon.source, tintColor: icon.tintColor }", "return { source: icon.source, tintColor: icon.tintColor, mask: icon.mask }"),
    ("      icon: entry.icon,\n", "      icon: entry.icon,\n      tooltip: entry.tooltip,\n"),
    ("date?: unknown; icon?: unknown }>", "date?: unknown; icon?: unknown; tooltip?: unknown }>"),
    ("{label.includes('check') ? (", "{label.includes('hashtag') ? (\n          <path d=\"M9 3 7 21M17 3l-2 18M4 9h16M3 15h16\" />\n        ) : label.includes('computerchip') ? (\n          <><rect x=\"6\" y=\"6\" width=\"12\" height=\"12\" rx=\"2\" /><path d=\"M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4\" /></>\n        ) : label.includes('twopeople') ? (\n          <><circle cx=\"9\" cy=\"8\" r=\"3\" /><path d=\"M3 21v-2a6 6 0 0 1 12 0v2m1-16a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v2\" /></>\n        ) : label.includes('check') ? ("),
    ('return <img src={row.icon.source} alt="" className="h-5 w-5 shrink-0" draggable={false} />', 'return <SafeListImage source={row.icon.source} mask={row.icon.mask} />'),
    ("      {value}\n    </span>\n  )\n}\n\nfunction markdownFromListDetail", "      {accessory.icon ? <SymbolIcon icon={accessory.icon} title={value} /> : null}\n      {value}\n    </span>\n  )\n}\n\nfunction markdownFromListDetail"),
    ("    <span\n      className={\n        isTag", "    <span\n      title={textValue(accessory.tooltip) || undefined}\n      className={\n        isTag"),
    ("'max-w-[240px] shrink-0 truncate text-[12px] text-ink-3'", "'inline-flex max-w-[240px] shrink-0 items-center gap-1 truncate text-[12px] text-ink-3'"),
    ("  onSearchTextChanged,\n  onLoadMore,", "  onSearchTextChanged,\n  onSearchInput,\n  storageKey,\n  onLoadMore,"),
    ("onSearchTextChanged: (searchText: string) => Promise<void> | void", "onSearchTextChanged: (searchText: string, inputRevision?: number) => Promise<void> | void\n  onSearchInput?: (searchText: string, inputRevision: number) => void\n  storageKey?: string"),
    ("searchAccessory?.options[0]?.value ?? '',", "searchAccessory?.value ?? searchAccessory?.options[0]?.value ?? '',"),
    ("  const lastSentQuery = useRef('')", "  const lastSentQuery = useRef('')\n  const inputRevision = useRef(0)\n  const clientOwned = root.props?.__clientOwnedInput === true"),
    ("    if (typeof root.props?.searchText === 'string') {\n      setQuery(root.props.searchText)\n    }\n  }, [root.props?.searchText])", "    if (typeof root.props?.searchText === 'string') {\n      // Once typed, client text stays authoritative, including invalid drafts.\n      // Native snapshot revisions acknowledge ownership; they do not replace input.\n      if (!clientOwned || inputRevision.current === 0) {\n        setQuery(root.props.searchText)\n      }\n    }\n  }, [root.props?.searchText, root.props?.__inputRevision, clientOwned])"),
    ("      return searchAccessory.options.some((option)", "      if (clientOwned && (root.props?.__draftOnly === true || (inputRevision.current > 0 && root.props?.__inputRevision !== inputRevision.current))) return current\n      if (searchAccessory.value !== undefined) return searchAccessory.value\n      return searchAccessory.options.some((option)"),
    ("  const loadingMoreRef = useRef(false)", """  const loadingMoreRef = useRef(false)
  const restoredDropdown = useRef(false)
  useEffect(() => {
    if (restoredDropdown.current || !storageKey || !searchAccessory?.storeValue) return
    restoredDropdown.current = true
    let saved: string | null = null
    try { saved = window.localStorage.getItem(`tezbar-list-dropdown:${storageKey}`) } catch { return }
    if (saved === null || saved === accessoryValue || !searchAccessory.options.some(option => option.value === saved)) return
    setAccessoryValue(saved)
    if (clientOwned) onSearchInput?.(query, ++inputRevision.current)
    if (searchAccessory.actionId) onRunPrimaryAction(searchAccessory.actionId, {value: saved, ...(clientOwned ? {searchText: query, inputRevision: inputRevision.current} : {})})
  }, [storageKey, searchAccessory])"""),
    ("    debounceTimer.current = setTimeout(() => {", "    const scheduledInputRevision = inputRevision.current\n    debounceTimer.current = setTimeout(() => {\n      if (clientOwned && scheduledInputRevision !== inputRevision.current) return"),
    ("void onSearchTextChanged(query)", "void onSearchTextChanged(query, clientOwned ? scheduledInputRevision : undefined)"),
    ("  }, [query, onSearchTextChanged])", "  }, [query, onSearchTextChanged, clientOwned])"),
    ("                  setQuery(event.target.value)\n                  setSelected(0)", "                  if (clientOwned) onSearchInput?.(event.target.value, ++inputRevision.current)\n                  setQuery(event.target.value)\n                  setSelected(0)"),
    ("                        setAccessoryValue(option.value)\n                        setSelected(0)", "                        if (accessoryValue === option.value) return\n                        setAccessoryValue(option.value)\n                        setSelected(0)\n                        if (clientOwned) {\n                          onSearchInput?.(query, ++inputRevision.current)\n                          if (debounceTimer.current) clearTimeout(debounceTimer.current)\n                          lastSentQuery.current = query\n                        }"),
    ("                        setAccessoryValue(option.value)\n", "                        setAccessoryValue(option.value)\n                        if (storageKey && searchAccessory.storeValue) { try { window.localStorage.setItem(`tezbar-list-dropdown:${storageKey}`, option.value) } catch {} }\n"),
    ("onRunPrimaryAction(searchAccessory.actionId, { value: option.value })", "onRunPrimaryAction(searchAccessory.actionId, { value: option.value, ...(clientOwned ? {searchText: query, inputRevision: inputRevision.current} : {}) })"),
    ("    : hasQuery\n      ? 'No matching applications'", "    : emptyView?.title ? emptyView.title : hasQuery\n      ? 'No matching applications'"),
    ("    : hasQuery\n      ? 'Try a different app name or keyword.'", "    : emptyView ? emptyView.description : hasQuery\n      ? 'Try a different app name or keyword.'"),
    ("      : emptyView?.description || ''", "      : ''"),
    ('        {shouldShowSearch ? (', '        {root.props?.isLoading === true ? <p role="status" className="text-[11px] text-ink-3">Loading…</p> : null}\n        {shouldShowSearch ? ('),
    ("    if (filteredRows.length === 0) return", """    if (filteredRows.length === 0) return
    const shortcutAction = actions.find(action => filteredRows[selected]?.actionIds?.includes(action.id)
      && matchesListShortcut(e, action.shortcut, /Win/i.test(navigator.platform)))
    if (shortcutAction) {
      e.preventDefault()
      e.stopPropagation()
      onRunPrimaryAction(shortcutAction.id)
      return
    }"""),
    ('                      key={option.value}', '                      key={option.value}\n                      title={searchAccessory.tooltip}'),
    ('          <Hint label="Actions" keys={<><Kbd>⌘</Kbd><Kbd>K</Kbd></>} />', '          <button type="button" aria-label="Actions" onClick={() => onOpenActions(filteredRows[selected]?.actionIds)}><Hint label="Actions" keys={<><Kbd>⌘</Kbd><Kbd>K</Kbd></>} /></button>'),
    ("function RowIcon({ row }", (ROOT/'qa/safe-list-image.tsx.txt').read_text()+"\n"+(ROOT/'qa/list-shortcut.ts.txt').read_text()+"\n\nfunction RowIcon({ row }"),
])
edit('src/renderer/src/raycast-api/index.tsx',[
    ("    if (!actionFilterIds) return actions\n    const visibleIds = new Set(actionFilterIds)\n    return actions.filter((action) => visibleIds.has(action.id))\n  }, [actionFilterIds, actions])", "    const accessory = root.props?.searchBarAccessory as ExtensionRuntimeNode | undefined\n    const controlId = accessory?.type === 'List.Dropdown' ? accessory.props?.actionId : undefined\n    const visibleActions = actions.filter(action => action.id !== controlId)\n    if (!actionFilterIds) return visibleActions\n    const visibleIds = new Set(actionFilterIds)\n    return visibleActions.filter((action) => visibleIds.has(action.id))\n  }, [actionFilterIds, actions, root.props?.searchBarAccessory])"),
    ("onSearchTextChanged: (searchText: string) => Promise<void> | void", "onSearchTextChanged: (searchText: string, inputRevision?: number) => Promise<void> | void\n  onSearchInput?: (searchText: string, inputRevision: number) => void"),
    ("    onSearchTextChanged,\n", "    onSearchTextChanged,\n    onSearchInput,\n"),
    ("              onLoadMore={onLoadMore}", "              onSearchInput={onSearchInput}\n              storageKey={`${extensionId}:${commandName}`}\n              onLoadMore={onLoadMore}"),
])
edit('src/renderer/ExtensionRuntimeView.tsx',[
    ("  const searchRequestSeq = useRef(0)", """  const searchRequestSeq = useRef(0)
  const clientInputRevision = useRef(0)
  const nativeModelRevision = useRef(0)
  const acceptModel = useCallback((result: {root: ExtensionRuntimeNode}) => {
    if (result.root.props?.__clientOwnedInput !== true) return true
    const revision = result.root.props.__modelRevision
    if (typeof revision !== 'number' || revision < nativeModelRevision.current) return false
    nativeModelRevision.current = revision
    return true
  }, [])
  const handleSearchInput = useCallback((text: string, revision: number) => {
    clientInputRevision.current = revision
    searchRequestSeq.current += 1
    const owner = currentSession.current
    // Revoke native work immediately, then promote this same input revision
    // to a request after the List's existing debounce has elapsed.
    void window.tezbar.extensionSearchTextChanged({sessionId: state.sessionId, searchText: text, inputRevision: revision, draftOnly: true}).then(result => {
      if (currentSession.current !== owner || revision !== clientInputRevision.current) return
      if (result.ok && result.mode === 'view' && result.root.props?.__inputRevision === revision && acceptModel(result)) setState(fromRunResult(result))
    }).catch(error => {
      if (currentSession.current === owner && revision === clientInputRevision.current) setError(error instanceof Error ? error.message : String(error))
    })
  }, [state.sessionId, acceptModel])"""),
    ("    setState(fromRunResult(initial))", "    clientInputRevision.current = 0\n    nativeModelRevision.current = typeof initial.root.props?.__modelRevision === 'number' ? initial.root.props.__modelRevision : 0\n    setState(fromRunResult(initial))"),
    ("          const result = await window.tezbar.extensionRefreshSession", "          const startedRevision = clientInputRevision.current\n          const result = await window.tezbar.extensionRefreshSession"),
    ("          setState(fromRunResult(result))", "          if (!acceptModel(result)) return\n          setState(fromRunResult(result))"),
    ("      setState({\n        refreshMs: result.refreshMs,", "      if (!acceptModel(result)) return\n      setState({\n        refreshMs: result.refreshMs,"),
    ("              const effectNoticeValue", "              if (result.mode === 'view' && !acceptModel(result)) return\n              const effectNoticeValue"),
    ("          if (cancelled || (result.ok && result.mode === 'unchanged')) return", "          if (cancelled || startedRevision !== clientInputRevision.current || (result.ok && result.mode === 'unchanged')) return\n          if (result.ok && result.mode === 'view' && result.root.props?.__clientOwnedInput === true && clientInputRevision.current > 0 && result.root.props.__inputRevision !== clientInputRevision.current) return"),
    ("async (searchText: string) => {", "async (searchText: string, inputRevision?: number) => {\n      if (inputRevision !== undefined && inputRevision !== clientInputRevision.current) return"),
    ('      console.log(`[RuntimeView] Search text changed, sending to sandbox: "${searchText}"`)\n', ''),
    ("        searchText,\n", "        searchText,\n        inputRevision,\n"),
    ("      if (requestSeq !== searchRequestSeq.current || currentSession.current !== sessionOwner) return", "      if (requestSeq !== searchRequestSeq.current || currentSession.current !== sessionOwner) return\n      if ((result as {mode?: string}).mode === 'unchanged') return"),
    ("            sessionId={state.sessionId}\n            title=", "            key={`${state.sessionId}:${state.generation ?? ''}`}\n            sessionId={state.sessionId}\n            onSearchInput={handleSearchInput}\n            title="),
    ("              const result = await window.tezbar.extensionInvokeAction", "              const startedRevision = clientInputRevision.current\n              const result = await window.tezbar.extensionInvokeAction"),
    ("              if (currentSession.current !== sessionOwner) return", "              if (currentSession.current !== sessionOwner || startedRevision !== clientInputRevision.current) return\n              if ((result as {mode?: string}).mode === 'unchanged') return"),
])
edit('src/shared/desktop-api.ts',[
    ("  extensionSearchTextChanged: (payload: {\n", "  extensionSearchTextChanged: (payload: {\n    inputRevision?: number\n    draftOnly?: boolean\n"),
])
edit('src/shared/extensionRuntime.ts',[
    ("export type ExtensionSearchTextChangedRequest = {\n", "export type ExtensionSearchTextChangedRequest = {\n  inputRevision?: number\n    draftOnly?: boolean\n"),
])

PATCH.parent.mkdir(exist_ok=True)
patch=[]
for name,(old,new) in changes.items():
    out=DEST/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(new)
    patch.extend(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile='a/'+name,tofile='b/'+name))
PATCH.write_text(''.join(patch))
print(f'UNAPPLIED: {PATCH}; {len(changes)} files; real host untouched')
