use crate::core::{Results, MAX_BODY};
use reqwest::{redirect::Policy, Client, Url};
use std::time::Duration;

pub fn production_client() -> Result<Client, String> {
    configure(Client::builder())
        .https_only(true)
        .build()
        .map_err(|_| "Could not initialize secure search.".into())
}

/// Shared bounded client policy. A test-only caller can add its owned CA before
/// building; the executable has no trust, endpoint or environment override.
pub fn configure(builder: reqwest::ClientBuilder) -> reqwest::ClientBuilder {
    builder
        .no_proxy()
        .connect_timeout(Duration::from_secs(5))
        .timeout(Duration::from_secs(15))
        .read_timeout(Duration::from_secs(5))
        .pool_max_idle_per_host(0)
        .redirect(Policy::custom(|attempt| {
            if attempt.previous().len() >= 5 {
                return attempt.error("Search redirect limit reached");
            }
            let first = &attempt.previous()[0];
            let next = attempt.url();
            if next.scheme() != "https"
                || !next.username().is_empty()
                || next.password().is_some()
                || first.origin() != next.origin()
            {
                return attempt.error("Search redirect must stay on the same HTTPS origin");
            }
            attempt.follow()
        }))
}

pub async fn fetch(client: &Client, url: Url) -> Result<Results, String> {
    let mut response = client
        .get(url)
        .send()
        .await
        .map_err(|e| transport_error(&e))?;
    let status = response.status();
    // Locked useFetch rejects non-ok before JSON parsing.
    if !status.is_success() {
        return Err(format!("Search request failed (HTTP {}).", status.as_u16()));
    }
    // Exact locked parser MIME behavior is documented and oracle-tested.
    let mime = response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|h| h.to_str().ok())
        .unwrap_or_default();
    if !is_json_mime(mime) {
        return Err("The instance did not return a JSON media type.".into());
    }
    if response
        .content_length()
        .is_some_and(|n| n > MAX_BODY as u64)
    {
        return Err("Search response exceeds 2 MiB.".into());
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|e| transport_error(&e))? {
        if bytes.len() + chunk.len() > MAX_BODY {
            return Err("Search response exceeds 2 MiB.".into());
        }
        bytes.extend_from_slice(&chunk);
    }
    Results::parse(&bytes)
}
/// Port of locked utils 2.3.0 fetch-utils.ts's RFC 6838 grammar and json word
/// matching (including structured suffixes), rather than a substring guess.
pub fn is_json_mime(header: &str) -> bool {
    let media = header
        .split(';')
        .next()
        .unwrap_or_default()
        .trim()
        .to_ascii_lowercase();
    let Some((kind, subtype)) = media.split_once('/') else {
        return false;
    };
    let valid = |s: &str, extra: &[u8]| {
        (1..=127).contains(&s.len())
            && s.as_bytes()[0].is_ascii_alphanumeric()
            && s.bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"!#$&^_-".contains(&b) || extra.contains(&b))
    };
    if !valid(kind, b"") || !valid(subtype, b".+-") {
        return false;
    }
    subtype
        .split(|c: char| !(c.is_ascii_alphanumeric() || c == '_'))
        .any(|word| word == "json")
}
fn transport_error(error: &reqwest::Error) -> String {
    // Never format reqwest's URL-bearing Display or remote response content.
    if error.is_timeout() {
        "Search timed out. Try again when ready.".into()
    } else if error.is_redirect() {
        "Search redirect was rejected (same HTTPS origin, maximum 5).".into()
    } else {
        "Could not read the instance securely. Check the instance and try again.".into()
    }
}
