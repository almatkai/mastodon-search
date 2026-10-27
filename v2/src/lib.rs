pub mod core;
pub mod http;

use core::{draft_text, effect_ack, search_url, Kind, Results, MAX_INSTANCE, MAX_QUERY};
use serde_json::{json, Value};
use std::{
    collections::{HashMap, VecDeque},
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc, Mutex, Weak,
    },
    time::Duration,
};
use tezbar_extension_sdk::{unchanged, view, BoxFuture, CoreResult, Extension, ExtensionContext};
use tokio::sync::watch;

const ID: &str = "com.tezbar.native.mastodon-search";
const VERSION: &str = "2.0.0";
type Table = Arc<Mutex<HashMap<String, Arc<Mutex<Session>>>>>;

#[derive(Clone)]
enum Action {
    Kind,
    Search,
    Effect { method: &'static str, params: Value },
}
struct Session {
    http_context: ExtensionContext,
    nonce: u64,
    next_action: u64,
    revision: u64,
    surface_revision: u64,
    query: String,
    kind: Kind,
    instance: String,
    input_revision: Option<u64>,
    pending_draft: bool,
    results: Results,
    cache: VecDeque<(String, Results, usize)>,
    loading: bool,
    pending_effect: bool,
    valid: bool,
    message: Option<String>,
    retry: Option<Action>,
    search_error: Option<String>,
    search_retry: bool,
    actions: HashMap<String, Action>,
    surface: Value,
    cancel: watch::Sender<u64>,
}
impl Session {
    fn new(nonce: u64, ctx: &ExtensionContext) -> Self {
        Self {
            http_context: ctx.clone(),
            nonce,
            next_action: 0,
            revision: 0,
            surface_revision: 0,
            query: String::new(),
            kind: Kind::Accounts,
            instance: "mastodon.social".into(),
            input_revision: None,
            pending_draft: false,
            results: Results::default(),
            cache: VecDeque::new(),
            loading: false,
            pending_effect: false,
            valid: true,
            message: None,
            retry: None,
            search_error: None,
            search_retry: false,
            actions: HashMap::new(),
            surface: Value::Null,
            cancel: watch::channel(0).0,
        }
    }
    /// Ownership changes happen BEFORE validation. This table is outside SDK's
    /// staged JSON Value, so rollback cannot restore revoked/consumed actions.
    fn revoke(&mut self) -> Result<(), String> {
        self.revision = self
            .revision
            .checked_add(1)
            .ok_or("Search revision exhausted.")?;
        self.cancel.send_replace(self.revision);
        self.loading = false;
        self.pending_effect = false;
        self.valid = false;
        self.retry = None;
        self.message = None;
        self.search_error = None;
        self.search_retry = false;
        self.actions.clear();
        Ok(())
    }
    fn token(&mut self, action: Action, title: &str, shortcut: Option<Value>) -> Value {
        self.next_action += 1; // Bounded process lifetime; no remote-controlled integer.
        let id = format!("m:{}:{}", self.nonce, self.next_action);
        self.actions.insert(id.clone(), action);
        let mut value = json!({"id":id,"title":title,"kind":"action"});
        if let Some(shortcut) = shortcut {
            value["shortcut"] = shortcut;
        }
        value
    }
    fn cache_key(&self) -> String {
        format!(
            "https://{}/api/v2/search?type={}&q={}",
            self.instance,
            self.kind.text(),
            self.query
        )
    }
    fn cache_result(&mut self, key: String, results: Results) {
        self.cache.retain(|(k, _, _)| k != &key);
        let size =
            serde_json::to_vec(&json!({"accounts":results.accounts,"hashtags":results.hashtags}))
                .unwrap()
                .len();
        while self.cache.len() >= 4
            || self.cache.iter().map(|(_, _, n)| n).sum::<usize>() + size > 4 * 1024 * 1024
        {
            if self.cache.pop_front().is_none() {
                break;
            }
        }
        self.cache.push_back((key, results, size));
    }
    fn render(&mut self) -> Value {
        self.surface_revision += 1;
        self.actions.clear();
        let mut actions = Vec::new();
        // A value-change control is session-owned, unlike one-shot effects.
        // Client input revisions distinguish rapid A/B/A changes before a new
        // surface returns; no prior effect ID becomes live again.
        let dropdown =
            json!({"id":format!("m:{}:kind",self.nonce),"title":"Search for…","kind":"action"});
        self.actions
            .insert(dropdown["id"].as_str().unwrap().into(), Action::Kind);
        let mut people = Vec::new();
        let mut hashtags = Vec::new();
        // Never filter by current kind, rank, deduplicate or merge old arrays.
        for (index, account) in self.results.accounts.clone().into_iter().enumerate() {
            let handle = core::handle(&account, &self.instance);
            let specs = [
                (
                    "Visit Profile",
                    "host.shell.open",
                    json!({"target":account["url"]}),
                    None,
                ),
                (
                    "Copy Profile URL",
                    "host.clipboard.write",
                    json!({"text":account["url"]}),
                    Some(json!({"modifiers":["cmd","shift"],"key":"c"})),
                ),
                (
                    "Copy Handle",
                    "host.clipboard.write",
                    json!({"text":handle}),
                    Some(json!({"modifiers":["cmd","shift","opt"],"key":"c"})),
                ),
            ];
            let mut ids = Vec::new();
            for (title, method, params, shortcut) in specs {
                if self.pending_effect {
                    continue;
                }
                let action = self.token(Action::Effect { method, params }, title, shortcut);
                ids.push(action["id"].clone());
                actions.push(action);
            }
            people.push(json!({"type":"List.Item","props":{
                "id":format!("account:{index}"),"sourceId":account["id"],
                "title":account["display_name"],"subtitle":handle,
                "icon":{"source":account["avatar"],"mask":"roundedRectangle"},
                "accessories":core::accessories(&account),"actionIds":ids
            }}));
        }
        for (index, hashtag) in self.results.hashtags.clone().into_iter().enumerate() {
            let mut ids = Vec::new();
            if !self.pending_effect {
                let action = self.token(
                    Action::Effect {
                        method: "host.shell.open",
                        params: json!({"target":hashtag["url"]}),
                    },
                    "Visit Hashtag",
                    None,
                );
                ids.push(action["id"].clone());
                actions.push(action);
            }
            hashtags.push(json!({"type":"List.Item","props":{
                "id":format!("hashtag:{index}"),"title":hashtag["name"],"icon":"Icon.Hashtag","actionIds":ids
            }}));
        }
        let mut retries = Vec::new();
        if !self.pending_effect {
            if self.search_retry {
                retries.push(Action::Search);
            }
            if let Some(effect) = self.retry.clone() {
                retries.push(effect);
            }
        }
        for retry in retries {
            let title = if matches!(retry, Action::Search) {
                "Retry Search"
            } else {
                "Retry Last Action"
            };
            let retry = self.token(retry, title, None);
            // The pinned List's action panel filters by the selected row. A
            // retained result must still expose the explicit frozen retry.
            for row in people.iter_mut().chain(hashtags.iter_mut()) {
                row["props"]["actionIds"]
                    .as_array_mut()
                    .unwrap()
                    .push(retry["id"].clone());
            }
            actions.push(retry);
        }
        let mut root = json!({"type":"List","props":{
            "searchText":self.query,"searchBarPlaceholder":"Search Mastodon",
            "isLoading":self.loading,"__hasServerSearch":true,"__clientOwnedInput":true,"throttle":true,
            "__modelRevision":self.surface_revision,"__inputRevision":self.input_revision,"__draftOnly":self.pending_draft,
            "searchBarAccessory":{"type":"List.Dropdown","props":{
                "tooltip":"Search for&hellip;","storeValue":true,"value":self.kind.text(),"actionId":dropdown["id"]
            },"children":[
                {"type":"List.Dropdown.Item","props":{"title":"People","value":"accounts"}},
                {"type":"List.Dropdown.Item","props":{"title":"Hashtags","value":"hashtags"}}
            ]}
        },"children":[
            {"type":"List.Section","props":{"title":"People"},"children":people},
            {"type":"List.Section","props":{"title":"Hashtags"},"children":hashtags}
        ]});
        // Generic pinned renderer needs the separately supplied empty-view fix.
        root["children"].as_array_mut().unwrap().push(json!({"type":"List.EmptyView","props":{"title":if self.loading {"Loading…"} else {"No results"}}}));
        actions.push(dropdown);
        let mut value = view("Search Mastodon", root, actions);
        let messages: Vec<_> = [self.search_error.as_deref(), self.message.as_deref()]
            .into_iter()
            .flatten()
            .collect();
        if !messages.is_empty() {
            value["message"] = json!(messages.join("\n"));
        }
        self.surface = value.clone();
        value
    }
}

/// Scope-owned lease drops even if an SDK handler/open is cancelled after it
/// registered state but before the SDK commits its staged Value.
struct Lease {
    table: Weak<Mutex<HashMap<String, Arc<Mutex<Session>>>>>,
    id: String,
    nonce: u64,
}
struct WorkCheckpoint {
    state: Weak<Mutex<Session>>,
    revision: u64,
    effect: Option<Action>,
}
impl Drop for WorkCheckpoint {
    fn drop(&mut self) {
        if let Some(state) = self.state.upgrade() {
            let mut s = state.lock().unwrap();
            if s.revision != self.revision {
                return;
            }
            if let Some(effect) = &self.effect {
                if !s.pending_effect {
                    return;
                }
                s.pending_effect = false;
                s.message = Some(
                    "Could not confirm the action. It may have completed. Retry only when ready."
                        .into(),
                );
                s.retry = Some(effect.clone());
            } else {
                if !s.loading {
                    return;
                }
                s.loading = false;
                s.search_error = Some("Search was cancelled. Try again when ready.".into());
                s.search_retry = true;
            }
            s.render();
        }
    }
}
impl Drop for Lease {
    fn drop(&mut self) {
        if let Some(table) = self.table.upgrade() {
            let mut table = table.lock().unwrap();
            if table
                .get(&self.id)
                .is_some_and(|s| s.lock().unwrap().nonce == self.nonce)
            {
                if let Some(state) = table.remove(&self.id) {
                    let _ = state.lock().unwrap().revoke();
                }
            }
        }
    }
}

pub struct Adapter {
    client: reqwest::Client,
    sessions: Table,
    nonce: AtomicU64,
}
impl Adapter {
    pub fn production() -> Result<Self, String> {
        Ok(Self::with_client(http::production_client()?))
    }
    /// Dependency injection for test harnesses. Only production() is called by
    /// the packaged entrypoint. No test endpoints or trust material live here.
    pub fn with_client(client: reqwest::Client) -> Self {
        Self {
            client,
            sessions: Arc::default(),
            nonce: AtomicU64::new(1),
        }
    }
    fn lookup(&self, id: &str) -> Result<Arc<Mutex<Session>>, String> {
        self.sessions
            .lock()
            .unwrap()
            .get(id)
            .cloned()
            .ok_or("Search session is closed.".into())
    }
    fn start_fetch(
        &self,
        _ctx: &ExtensionContext,
        state: &Arc<Mutex<Session>>,
    ) -> Result<(), String> {
        let (revision, key, url, mut cancel, http_context) = {
            let mut s = state.lock().unwrap();
            if s.query.is_empty() || !s.valid {
                s.render();
                return Ok(());
            }
            let url = match search_url(&s.instance, s.kind, &s.query) {
                Ok(url) => url,
                Err(e) => {
                    s.search_error = Some(e);
                    s.search_retry = true;
                    s.render();
                    return Ok(());
                }
            };
            let key = s.cache_key();
            if let Some((_, result, _)) = s.cache.iter().find(|(k, _, _)| k == &key) {
                s.results = result.clone();
            }
            s.loading = true;
            s.render();
            (
                s.revision,
                key,
                url,
                s.cancel.subscribe(),
                s.http_context.clone(),
            )
        };
        let state = state.clone();
        let client = self.client.clone();
        // Search RPC cancellation is reader-ordered in the pinned SDK, before
        // client revisions can be validated. A stale RPC must not cancel newer
        // HTTP work. The open-session scope owns work; our revision watch owns
        // supersession. Disposal/cancelled-open/EOF still stop this scope.
        let notify = http_context.clone();
        let checkpoint = WorkCheckpoint {
            state: Arc::downgrade(&state),
            revision,
            effect: None,
        };
        http_context.spawn(async move {
            let _checkpoint = checkpoint;
            let result = tokio::select! { biased;
                _ = cancel.changed() => return,
                result = http::fetch(&client,url) => result,
            };
            let mut s = state.lock().unwrap();
            if s.revision != revision {
                return;
            }
            s.loading = false;
            match result {
                Ok(results) => {
                    s.cache_result(key, results.clone());
                    s.results = results;
                    s.search_error = None;
                    s.search_retry = false;
                }
                Err(e) => {
                    s.search_error = Some(e);
                    s.search_retry = true;
                }
            }
            s.render();
            let _ = notify.invalidate();
        })
    }
    fn update(
        &self,
        ctx: &ExtensionContext,
        state: &Arc<Mutex<Session>>,
        payload: &Value,
        kind: Option<Value>,
    ) -> CoreResult {
        {
            let mut s = state.lock().unwrap();
            if let (Some(new), Some(old)) = (
                payload.get("inputRevision").and_then(Value::as_u64),
                s.input_revision,
            ) {
                if new < old || (new == old && (!s.pending_draft || payload["draftOnly"] == true)) {
                    return Ok(unchanged());
                }
            }
            s.revoke()?;
            // Revocation has already cancelled body reads, even for invalid values.
            let validate = (|| {
                if let Some(rev) = payload.get("inputRevision") {
                    s.input_revision = Some(rev.as_u64().ok_or("Invalid input revision.")?);
                }
                if payload.get("draftOnly").is_some_and(|v| !v.is_boolean()) {
                    return Err("Invalid search draft mode.".into());
                }
                s.pending_draft = payload["draftOnly"] == true;
                if let Some(kind) = kind {
                    s.kind = Kind::parse(&kind)?;
                }
                if let Some(query) = payload.get("searchText") {
                    // Invalid draft is displayed without leaving the old query live.
                    s.query.clear();
                    s.query = draft_text(query, MAX_QUERY, "Search")?;
                }
                let prefs = &payload["preferences"];
                s.instance = match prefs.get("instance") {
                    Some(v) => draft_text(v, MAX_INSTANCE, "Instance")?,
                    None => "mastodon.social".into(),
                };
                if s.instance.is_empty() {
                    return Err("Enter a Mastodon instance.".into());
                }
                s.valid = true;
                Ok::<_, String>(())
            })();
            if let Err(error) = validate {
                s.message = Some(error);
                return Ok(s.render());
            }
        }
        if state.lock().unwrap().pending_draft {
            return Ok(state.lock().unwrap().render());
        }
        if let Err(error) = self.start_fetch(ctx, state) {
            let mut s = state.lock().unwrap();
            s.loading = false;
            s.search_error = Some(error);
            s.search_retry = true;
            s.render();
        }
        Ok(state.lock().unwrap().surface.clone())
    }
    fn invoke(
        &self,
        ctx: &ExtensionContext,
        state: &Arc<Mutex<Session>>,
        payload: &Value,
    ) -> CoreResult {
        let action = {
            let mut s = state.lock().unwrap();
            let Some(id) = payload["actionId"].as_str() else {
                return Ok(unchanged());
            };
            if id == format!("m:{}:kind", s.nonce) {
                if let (Some(new), Some(old)) = (
                    payload["formValues"]["inputRevision"].as_u64(),
                    s.input_revision,
                ) {
                    if new < old || (new == old && !s.pending_draft) {
                        return Ok(unchanged());
                    }
                }
                Action::Kind
            } else {
                if s.pending_effect {
                    return Ok(unchanged());
                }
                // Consume BEFORE await/spawn; SDK rollback cannot resurrect this ID.
                let Some(action) = s.actions.remove(id) else {
                    return Ok(unchanged());
                };
                action
            }
        };
        match action {
            Action::Kind => {
                let kind = payload["formValues"]["value"].clone();
                let mut draft = payload.clone();
                for field in ["searchText", "inputRevision"] {
                    if let Some(v) = payload["formValues"].get(field) {
                        draft[field] = v.clone();
                    }
                }
                self.update(ctx, state, &draft, Some(kind))
            }
            Action::Search => self.update(ctx, state, payload, None),
            effect @ Action::Effect { .. } => {
                let (revision, mut cancel) = {
                    let mut s = state.lock().unwrap();
                    s.message = Some("Working…".into());
                    s.pending_effect = true;
                    s.retry = None;
                    // Keep value-change controls available; suppress effect IDs.
                    s.render();
                    (s.revision, s.cancel.subscribe())
                };
                let state = state.clone();
                let worker_state = state.clone();
                let notify = ctx.clone();
                let call = ctx.clone();
                let frozen = effect.clone();
                let checkpoint = WorkCheckpoint {
                    state: Arc::downgrade(&state),
                    revision,
                    effect: Some(effect.clone()),
                };
                let result = ctx.spawn(async move {
                    let _checkpoint = checkpoint;
                    let Action::Effect { method, params } = frozen else { unreachable!() };
                    let result = tokio::select! { biased;
                        _ = cancel.changed() => return,
                        result = tokio::time::timeout(Duration::from_secs(20),call.host(method,params)) => result,
                    };
                    let mut s = worker_state.lock().unwrap();
                    if s.revision != revision { return; }
                    s.pending_effect = false;
                    if matches!(result,Ok(Ok(ref ack)) if effect_ack(ack)) {
                        s.message = Some(if method == "host.clipboard.write" {"Copied to clipboard."} else {"Opened in browser."}.into());
                        s.retry = None;
                    } else {
                        s.message = Some("Could not confirm the action. It may have completed. Retry only when ready.".into());
                        s.retry = Some(effect);
                    }
                    s.render();
                    let _ = notify.invalidate();
                });
                let mut s = state.lock().unwrap();
                if result.is_err() {
                    s.pending_effect = false;
                    s.message = Some("Could not start the action. Try again when ready.".into());
                    s.render();
                }
                Ok(s.surface.clone())
            }
        }
    }
}
impl Extension for Adapter {
    fn id(&self) -> &'static str {
        ID
    }
    fn version(&self) -> &'static str {
        VERSION
    }
    fn commands(&self) -> &'static [&'static str] {
        &["search"]
    }
    fn handle<'a>(
        &'a self,
        ctx: &'a ExtensionContext,
        command: &'a str,
        operation: &'a str,
        payload: &'a Value,
        _state: &'a mut Value,
    ) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            if command != "search" {
                return Err("Unknown command.".into());
            }
            let id = payload["sessionId"]
                .as_str()
                .filter(|s| !s.is_empty() && s.len() <= 1024)
                .ok_or("Invalid session identity.")?;
            match operation {
                "extension:run-command" => {
                    let nonce = self.nonce.fetch_add(1, Ordering::Relaxed);
                    let state = Arc::new(Mutex::new(Session::new(nonce, ctx)));
                    {
                        let mut table = self.sessions.lock().unwrap();
                        if table.len() >= 128 || table.contains_key(id) {
                            return Err("Search session capacity reached.".into());
                        }
                        table.insert(id.into(), state.clone());
                    }
                    let lease = Lease {
                        table: Arc::downgrade(&self.sessions),
                        id: id.into(),
                        nonce,
                    };
                    ctx.spawn(async move {
                        let _lease = lease;
                        std::future::pending::<()>().await;
                    })?;
                    self.update(ctx, &state, payload, None)
                }
                "extension:dispose-session" => {
                    if let Some(s) = self.sessions.lock().unwrap().remove(id) {
                        s.lock().unwrap().revoke()?;
                    }
                    Ok(unchanged())
                }
                "extension:search-text-changed" => {
                    self.update(ctx, &self.lookup(id)?, payload, None)
                }
                "extension:refresh-session" => Ok(self.lookup(id)?.lock().unwrap().surface.clone()),
                "extension:invoke-action" => self.invoke(ctx, &self.lookup(id)?, payload),
                _ => Err("Unsupported search operation.".into()),
            }
        })
    }
    fn shutdown<'a>(&'a self, _ctx: &'a ExtensionContext) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            for s in self.sessions.lock().unwrap().drain().map(|(_, s)| s) {
                s.lock().unwrap().revoke()?;
            }
            Ok(json!({}))
        })
    }
}
