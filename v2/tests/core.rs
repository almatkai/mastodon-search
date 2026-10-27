use mastodon_search_v2::{core::*, http::is_json_mime};
use serde_json::{json, Value};

fn oracle() -> Value {
    serde_json::from_str(include_str!("../qa/evidence/source-oracle.json")).unwrap()
}

#[test]
fn exact_source_whatwg_urls() {
    for v in oracle()["urlVectors"].as_array().unwrap() {
        assert_eq!(
            search_url(
                v["instance"].as_str().unwrap(),
                Kind::Accounts,
                v["query"].as_str().unwrap()
            )
            .unwrap()
            .as_str(),
            v["url"].as_str().unwrap()
        );
    }
    assert!(search_url("u:p@host.invalid", Kind::Accounts, "x").is_err());
}
#[test]
fn exact_locked_mime_vectors() {
    for v in oracle()["mimeVectors"].as_array().unwrap() {
        assert_eq!(
            is_json_mime(v["mime"].as_str().unwrap()),
            v["json"].as_bool().unwrap(),
            "{v}"
        );
    }
}
#[test]
fn real_source_account_and_hashtag_mapping() {
    let o = oracle();
    let r = Results::parse(&serde_json::to_vec(&o["payload"]).unwrap()).unwrap();
    assert_eq!(r.accounts.len(), 3);
    assert_eq!(r.hashtags.len(), 2);
    assert_eq!(r.accounts[0]["id"], "109912345678901234");
    assert_eq!(r.accounts[1]["id"], 7);
    for (i, a) in r.accounts.iter().enumerate() {
        assert_eq!(handle(a, "mastodon.social"), o["rows"][i]["subtitle"]);
        assert_eq!(accessories(a), o["rows"][i]["accessories"]);
        assert_eq!(a["display_name"], o["rows"][i]["title"]);
    }
    for (i, h) in r.hashtags.iter().enumerate() {
        assert_eq!(h["url"], o["rows"][i + 3]["actions"][0]["url"]);
    }
}
#[test]
fn malformed_responses_fail_without_partial_rows() {
    for v in [
        json!(null),
        json!({}),
        json!({"accounts":null,"hashtags":[]}),
        json!({"accounts":[],"hashtags":"bad"}),
        json!({"accounts":[{}],"hashtags":[]}),
        json!({"accounts":[],"hashtags":[{"name":3,"url":"x"}]}),
    ] {
        assert!(Results::parse(&serde_json::to_vec(&v).unwrap()).is_err());
    }
    let mut p = oracle()["payload"].clone();
    p["accounts"][0]["id"] = json!({});
    assert!(Results::parse(&serde_json::to_vec(&p).unwrap()).is_err());
    let many =
        json!({"accounts":[],"hashtags":vec![json!({"name":"x","url":"https://x.invalid"});513]});
    assert!(Results::parse(&serde_json::to_vec(&many).unwrap())
        .unwrap_err()
        .contains("512"));
    assert!(Results::parse(&vec![b' '; MAX_BODY + 1])
        .unwrap_err()
        .contains("2 MiB"));
    let deep = format!("{}0{}", "[".repeat(66), "]".repeat(66));
    assert!(Results::parse(deep.as_bytes()).is_err());
    p = oracle()["payload"].clone();
    p["accounts"][0]["acct"] = json!("x".repeat(MAX_FIELD + 1));
    assert!(Results::parse(&serde_json::to_vec(&p).unwrap()).is_err());
}
#[test]
fn strict_closed_effect_acknowledgements() {
    for v in [json!({"ok":true}), json!({"ok":true,"message":"done"})] {
        assert!(effect_ack(&v));
    }
    for v in [
        json!(null),
        json!(true),
        json!("ok"),
        json!({}),
        json!({"ok":false}),
        json!({"ok":true,"extra":1}),
        json!({"ok":true,"message":null}),
        json!({"ok":1}),
    ] {
        assert!(!effect_ack(&v));
    }
}
#[test]
fn js_length_and_untrimmed_drafts() {
    assert_eq!(
        draft_text(&json!(" \t "), MAX_QUERY, "Search").unwrap(),
        " \t "
    );
    assert!(draft_text(&json!("😀".repeat(2049)), MAX_QUERY, "Search").is_err());
    assert!(draft_text(&json!(9), MAX_QUERY, "Search").is_err());
}
