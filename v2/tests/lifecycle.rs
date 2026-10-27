use mastodon_search_v2::Adapter;
use serde_json::{json, Value};
use tezbar_extension_sdk::{Extension, ExtensionPaths, TestContext};

#[tokio::test]
async fn scope_drop_after_handler_return_releases_140_then_accepts_128_live() {
    let adapter = Adapter::production().unwrap();
    for i in 0..140 {
        let ctx = TestContext::new(ExtensionPaths::default(), &[]);
        let mut staged = json!({});
        let result = adapter
            .handle(
                &ctx.context,
                "search",
                "extension:run-command",
                &json!({"sessionId":format!("cancel-{i}"),"preferences":{}}),
                &mut staged,
            )
            .await
            .unwrap();
        assert_eq!(result["mode"], "view");
        // Actual SDK TestContext::drop stops the scope; no adapter dispose call.
        drop(ctx);
        tokio::task::yield_now().await;
    }
    let mut live = Vec::new();
    for i in 0..128 {
        let ctx = TestContext::new(ExtensionPaths::default(), &[]);
        adapter
            .handle(
                &ctx.context,
                "search",
                "extension:run-command",
                &json!({"sessionId":format!("live-{i}")}),
                &mut Value::Null,
            )
            .await
            .unwrap();
        live.push(ctx);
    }
    let extra = TestContext::new(ExtensionPaths::default(), &[]);
    assert!(adapter
        .handle(
            &extra.context,
            "search",
            "extension:run-command",
            &json!({"sessionId":"overflow"}),
            &mut Value::Null
        )
        .await
        .unwrap_err()
        .contains("capacity"));
    drop(live);
    tokio::task::yield_now().await;
    adapter
        .handle(
            &extra.context,
            "search",
            "extension:run-command",
            &json!({"sessionId":"recovered"}),
            &mut Value::Null,
        )
        .await
        .unwrap();
}
