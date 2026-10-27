// Complete original host producer functions; only effect boundaries are fakes.
// This is not an installed-host or actual clipboard/browser test.
#![allow(dead_code)]
use ::std::io::Cursor;
use serde_json::{json, Value};
type CoreResult = Result<Value, String>;
#[derive(Default)]
struct Worker {
    text: String,
    fail: bool,
    entries: Vec<Value>,
    last_sequence: Option<u64>,
    last_id: String,
    ctx: Ctx,
}
#[derive(Default)]
struct Ctx;
impl Ctx {
    fn emit(&self, _: &str, _: Value) {}
}
impl Worker {
    fn native(&mut self) -> Result<&mut Self, String> {
        Ok(self)
    }
    fn get_text(&self) -> Result<String, arboard::Error> {
        Ok(self.text.clone())
    }
    fn write_text(&mut self, text: String) -> Result<(), String> {
        if self.fail {
            return Err("Owned write failed".into());
        }
        self.text = text;
        Ok(())
    }
    fn write_image(&self, _: &[u8]) -> Result<(), String> {
        Err("Image producer disabled".into())
    }
    fn cleanup(&self, _: bool) -> CoreResult {
        Err("Cleanup disabled".into())
    }
    fn load(&self) -> Result<(), String> {
        Ok(())
    }
    fn insert(&mut self, v: Value) -> Result<(), String> {
        self.entries.push(v);
        Ok(())
    }
    fn items(&self) -> &Vec<Value> {
        &self.entries
    }
    fn save_items(&mut self, v: Vec<Value>) -> Result<(), String> {
        self.entries = v;
        Ok(())
    }
    fn remove_image(&self, _: &Value) {}
}
fn text_arg(a: &[Value], n: usize) -> Result<&str, String> {
    a.get(n)
        .and_then(Value::as_str)
        .ok_or("Expected text".into())
}
fn now_ms() -> u64 {
    0
}
fn text_entry(_: &str, _: u64) -> Option<Value> {
    None
}
mod arboard {
    #[derive(Debug)]
    pub enum Error {
        ContentNotAvailable,
        Other,
    }
    impl ::std::fmt::Display for Error {
        fn fmt(&self, f: &mut ::std::fmt::Formatter<'_>) -> ::std::fmt::Result {
            write!(f, "Owned clipboard unavailable")
        }
    }
}
mod native {
    pub fn write_files(_: &[String]) -> Result<(), String> {
        Err("Files disabled".into())
    }
    pub fn sequence() -> Option<u64> {
        None
    }
}
mod std {
    pub mod fs {
        pub fn read<P: AsRef<::std::path::Path>>(_: P) -> Result<Vec<u8>, String> {
            Err("Filesystem producer disabled".into())
        }
    }
}
mod base64 {
    pub mod engine {
        pub mod general_purpose {
            pub struct Standard;
            pub static STANDARD: Standard = Standard;
            impl Standard {
                pub fn decode(&self, _: &str) -> Result<Vec<u8>, String> {
                    Err("Base64 disabled".into())
                }
                pub fn encode(&self, _: &[u8]) -> String {
                    String::new()
                }
            }
        }
    }
}
mod image {
    pub enum ImageFormat {
        Png,
    }
    pub struct Image;
    pub fn load_from_memory(_: &[u8]) -> Result<Image, String> {
        Err("Image disabled".into())
    }
    impl Image {
        pub fn write_to(
            &self,
            _: &mut ::std::io::Cursor<Vec<u8>>,
            _: ImageFormat,
        ) -> Result<(), String> {
            Err("Image disabled".into())
        }
        pub fn width(&self) -> u32 {
            0
        }
        pub fn height(&self) -> u32 {
            0
        }
    }
}
mod open {
    pub fn that_detached(value: String) -> Result<(), String> {
        assert_eq!(value, "https://social.invalid/frozen");
        Ok(())
    }
}
include!("../qa/fixtures/producer-functions.rs");

#[test]
fn actual_complete_clipboard_producer_returns_closed_ok_and_read_is_string() {
    let mut worker = Worker::default();
    let ack = worker
        .handle("clipboard:write", &[json!("Owned synthetic text")])
        .unwrap();
    assert_eq!(ack, json!({"ok":true}));
    assert!(mastodon_search_v2::core::effect_ack(&ack));
    assert_eq!(
        worker.handle("clipboard:read", &[]).unwrap(),
        json!("Owned synthetic text")
    );
    worker.fail = true;
    assert!(worker.handle("clipboard:write", &[json!("Owned")]).is_err());
}
#[tokio::test]
async fn actual_complete_open_producer_has_frozen_target_and_closed_ack() {
    let ack = open_target("https://social.invalid/frozen").await.unwrap();
    assert_eq!(ack, json!({"ok":true,"message":"Opened"}));
    assert!(mastodon_search_v2::core::effect_ack(&ack));
    assert!(open_target("").await.is_err());
    assert!(open_target("x\0y").await.is_err());
}
