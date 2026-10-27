use reqwest::Url;
use serde_json::{json, Value};

pub const MAX_QUERY: usize = 4096; // UTF-16 code units, like JS length.
pub const MAX_INSTANCE: usize = 2048;
pub const MAX_BODY: usize = 2 * 1024 * 1024;
pub const MAX_ROWS: usize = 512;
pub const MAX_FIELD: usize = 16 * 1024;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Accounts,
    Hashtags,
}
impl Kind {
    pub fn text(self) -> &'static str {
        match self {
            Self::Accounts => "accounts",
            Self::Hashtags => "hashtags",
        }
    }
    pub fn parse(value: &Value) -> Result<Self, String> {
        match value.as_str() {
            Some("accounts") => Ok(Self::Accounts),
            Some("hashtags") => Ok(Self::Hashtags),
            _ => Err("Choose People or Hashtags.".into()),
        }
    }
}

/// Parse the original raw template with a WHATWG URL parser. In particular &, +,
/// % and # are NOT encoded as a form parameter. Fetch never transmits fragments.
pub fn search_url(instance: &str, kind: Kind, query: &str) -> Result<Url, String> {
    let mut url = Url::parse(&format!(
        "https://{instance}/api/v2/search?type={}&q={query}",
        kind.text()
    ))
    .map_err(|_| "The instance does not form a valid HTTPS address.".to_string())?;
    if url.scheme() != "https" || url.host_str().is_none() {
        return Err("The instance must form an HTTPS address.".into());
    }
    if !url.username().is_empty() || url.password().is_some() {
        return Err("The instance address must not contain credentials.".into());
    }
    url.set_fragment(None);
    Ok(url)
}

pub fn draft_text(value: &Value, limit: usize, label: &str) -> Result<String, String> {
    let text = value
        .as_str()
        .ok_or_else(|| format!("{label} must be text."))?;
    if text.encode_utf16().count() > limit {
        return Err(format!("{label} is too long (maximum {limit} characters)."));
    }
    Ok(text.into())
}

#[derive(Clone, Debug, Default)]
pub struct Results {
    pub accounts: Vec<Value>,
    pub hashtags: Vec<Value>,
}
fn field<'a>(value: &'a Value, name: &str) -> Result<&'a str, String> {
    value[name]
        .as_str()
        .filter(|s| s.len() <= MAX_FIELD)
        .ok_or_else(|| format!("Invalid or oversized {name} in search response."))
}
fn bounds(value: &Value, depth: usize, work: &mut usize) -> Result<(), String> {
    *work += 1;
    if depth > 64 || *work > 100_000 {
        return Err("Search response exceeds nesting or work limits.".into());
    }
    match value {
        Value::Array(a) => {
            for v in a {
                bounds(v, depth + 1, work)?;
            }
        }
        Value::Object(o) => {
            for v in o.values() {
                bounds(v, depth + 1, work)?;
            }
        }
        _ => {}
    }
    Ok(())
}
impl Results {
    pub fn parse(bytes: &[u8]) -> Result<Self, String> {
        if bytes.len() > MAX_BODY {
            return Err("Search response exceeds 2 MiB.".into());
        }
        let value: Value = serde_json::from_slice(bytes)
            .map_err(|_| "The instance returned invalid JSON.".to_string())?;
        bounds(&value, 0, &mut 0)?;
        let accounts = value["accounts"]
            .as_array()
            .ok_or("Search response has no accounts array.")?;
        let hashtags = value["hashtags"]
            .as_array()
            .ok_or("Search response has no hashtags array.")?;
        if accounts.len() + hashtags.len() > MAX_ROWS {
            return Err("Search response exceeds 512 rows.".into());
        }
        for a in accounts {
            if !a["id"].is_string() && !a["id"].is_number() {
                return Err("Invalid account id in search response.".into());
            }
            if a["id"].as_str().is_some_and(|s| s.len() > MAX_FIELD) {
                return Err("Oversized account id in search response.".into());
            }
            for name in ["display_name", "acct", "avatar", "url"] {
                field(a, name)?;
            }
            if !a["bot"].is_boolean() || !a["followers_count"].is_number() {
                return Err("Invalid bot or follower count in search response.".into());
            }
        }
        for h in hashtags {
            field(h, "name")?;
            field(h, "url")?;
        }
        Ok(Self {
            accounts: accounts.clone(),
            hashtags: hashtags.clone(),
        })
    }
}

pub fn handle(account: &Value, instance: &str) -> String {
    let acct = account["acct"].as_str().unwrap_or_default();
    if acct.contains('@') {
        format!("@{acct}")
    } else {
        format!("@{acct}@{instance}")
    }
}
pub fn accessories(account: &Value) -> Value {
    let mut values = Vec::new();
    if account["bot"] == true {
        values.push(
            json!({"icon":"Icon.ComputerChip","tooltip":"Account is a bot","text":"Bot Account"}),
        );
    }
    // JS Number#toString, including 1e+21 and negative zero.
    let n = account["followers_count"].as_f64().unwrap_or_default();
    let text = ryu_js::Buffer::new().format(n).to_string();
    values.push(json!({"icon":"Icon.TwoPeople","tooltip":"Number of followers","text":text}));
    json!(values)
}

/// Closed producer contract for the two source effect methods.
pub fn effect_ack(value: &Value) -> bool {
    value.as_object().is_some_and(|v| {
        v.get("ok") == Some(&Value::Bool(true))
            && v.keys().all(|k| k == "ok" || k == "message")
            && v.get("message").is_none_or(Value::is_string)
    })
}
