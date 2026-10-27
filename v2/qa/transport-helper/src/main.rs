// QA executable only. Never included in the development/release ZIP.
#[tokio::main(worker_threads = 2)]
async fn main() {
    let ca = std::fs::read(std::env::args().nth(1).expect("Owned fixture CA path")).unwrap();
    let client = mastodon_search_v2::http::configure(reqwest::Client::builder())
        .https_only(true)
        .add_root_certificate(reqwest::Certificate::from_pem(&ca).unwrap())
        .build()
        .unwrap();
    if std::env::args().nth(2).as_deref() == Some("--direct-preferences") {
        use serde_json::json;
        use tezbar_extension_sdk::Extension;
        let instance = std::env::args().nth(3).unwrap();
        let ctx = tezbar_extension_sdk::TestContext::new(Default::default(), &[]);
        let adapter = mastodon_search_v2::Adapter::with_client(client);
        let mut state = json!({});
        adapter.handle(&ctx.context,"search","extension:run-command",&json!({"sessionId":"direct","preferences":{"instance":instance},"searchText":"slow-direct-preferences"}),&mut state).await.unwrap();
        // Parent waits for its TLS body fixture to start, then permits the edit.
        let mut line = String::new();
        std::io::stdin().read_line(&mut line).unwrap();
        let result = adapter
            .handle(
                &ctx.context,
                "search",
                "extension:search-text-changed",
                &json!({"sessionId":"direct","preferences":{"instance":9},"searchText":"new"}),
                &mut state,
            )
            .await
            .unwrap();
        assert!(result["message"].as_str().unwrap().contains("Instance"));
        assert_eq!(result["root"]["props"]["isLoading"], false);
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
        println!("{}", json!({"invalidPreferenceCancelled":true}));
        return;
    }
    tezbar_extension_sdk::serve(mastodon_search_v2::Adapter::with_client(client))
        .await
        .unwrap();
}
