#[tokio::main(worker_threads = 2)]
async fn main() {
    let result = match mastodon_search_v2::Adapter::production() {
        Ok(adapter) => tezbar_extension_sdk::serve(adapter).await,
        Err(error) => Err(error),
    };
    if let Err(error) = result {
        // Adapter errors contain no query, instance, account, URL or response body.
        eprintln!("Mastodon Search: {error}");
        std::process::exit(1);
    }
}
