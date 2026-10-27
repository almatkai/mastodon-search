// Unmodified complete functions from host ea100cee3f69711de12485ba061950c5fc65258f.
impl Worker {
    fn handle(&mut self, c: &str, a: &[Value]) -> CoreResult {
        match c {
            "clipboard:read" => {
                return match self.native()?.get_text() {
                    Ok(text) => Ok(json!(text)),
                    Err(arboard::Error::ContentNotAvailable) => Ok(json!("")),
                    Err(e) => Err(e.to_string()),
                };
            }
            "clipboard:write" => {
                self.write_text(text_arg(a, 0)?.into())?;
                return Ok(json!({"ok":true}));
            }
            "clipboard:write-png" => {
                let raw = text_arg(a, 0)?;
                let result = (|| {
                    let data = raw
                        .strip_prefix("data:image/png;base64,")
                        .ok_or("Invalid PNG data URL")?;
                    let bytes = base64::engine::general_purpose::STANDARD
                        .decode(data)
                        .map_err(|e| e.to_string())?;
                    self.write_image(&bytes)
                })();
                return Ok(match result {
                    Ok(()) => json!({"ok":true}),
                    Err(error) => json!({"ok":false,"error":error}),
                });
            }
            "core:clipboard:cleanup" => return self.cleanup(false),
            "storage:clear-clipboard-images" => return self.cleanup(true),
            _ => {}
        }
        self.load()?;
        if c == "core:clipboard:capture-text" {
            let text = text_arg(a, 0)?;
            if let Some(entry) = text_entry(text, now_ms()) {
                self.insert(entry)?;
            }
            return Ok(Value::Null);
        }
        if c == "clipboard:list" {
            return Ok(json!(self.items()));
        }
        if c == "clipboard:clear" {
            let old = self.items().clone();
            self.save_items(vec![])?;
            for i in old {
                self.remove_image(&i)
            }
            return Ok(Value::Null);
        }
        let id = text_arg(a, 0)?;
        let Some(entry) = self.items().iter().find(|i| i["id"] == id).cloned() else {
            return Ok(if c == "clipboard:image" {
                Value::Null
            } else {
                json!(false)
            });
        };
        match c {
            "clipboard:delete" => {
                let next = self
                    .items()
                    .iter()
                    .filter(|i| i["id"] != id)
                    .cloned()
                    .collect();
                self.save_items(next)?;
                if !self
                    .items()
                    .iter()
                    .any(|i| i["imagePath"] == entry["imagePath"])
                {
                    self.remove_image(&entry)
                }
                Ok(json!(true))
            }
            "clipboard:toggle-pin" => {
                let mut items = self.items().clone();
                for i in &mut items {
                    if i["id"] == id {
                        i["pinned"] = json!(i["pinned"] != true)
                    }
                }
                items.sort_by_key(|i| i["pinned"] != true);
                self.save_items(items)?;
                Ok(json!(true))
            }
            "clipboard:restore" => {
                match entry["kind"].as_str() {
                    Some("text") => self.write_text(entry["text"].as_str().unwrap_or("").into())?,
                    Some("image") => {
                        let p = entry["imagePath"].as_str().ok_or("Image path missing")?;
                        let bytes = std::fs::read(p).map_err(|e| e.to_string())?;
                        self.write_image(&bytes)?
                    }
                    Some("file") => {
                        let paths: Vec<_> = entry["paths"]
                            .as_array()
                            .unwrap()
                            .iter()
                            .filter_map(|p| p.as_str().map(str::to_owned))
                            .collect();
                        native::write_files(&paths)?
                    }
                    _ => return Err("Unsupported clipboard format".into()),
                }
                self.last_sequence = native::sequence();
                self.last_id = id.into();
                self.ctx.emit("clipboard:changed", json!({}));
                Ok(json!(true))
            }
            "clipboard:image" => {
                let path = entry["imagePath"]
                    .as_str()
                    .or_else(|| entry["paths"][0].as_str());
                let Some(path) = path else {
                    return Ok(Value::Null);
                };
                let bytes = match std::fs::read(path) {
                    Ok(bytes) => bytes,
                    Err(_) => return Ok(Value::Null),
                };
                if entry["kind"] == "image" {
                    return Ok(
                        json!({"dataUrl":format!("data:image/png;base64,{}",base64::engine::general_purpose::STANDARD.encode(&bytes)),"width":entry["width"],"height":entry["height"],"byteSize":bytes.len()}),
                    );
                }
                let image = match image::load_from_memory(&bytes) {
                    Ok(image) => image,
                    Err(_) => return Ok(Value::Null),
                };
                let mut png = Cursor::new(vec![]);
                image
                    .write_to(&mut png, image::ImageFormat::Png)
                    .map_err(|e| e.to_string())?;
                let png = png.into_inner();
                Ok(
                    json!({"dataUrl":format!("data:image/png;base64,{}",base64::engine::general_purpose::STANDARD.encode(&png)),"width":image.width(),"height":image.height(),"byteSize":png.len()}),
                )
            }
            _ => Err(format!("Unknown clipboard channel {c}")),
        }
    }
}
async fn open_target(target: &str) -> CoreResult {
    if target.trim().is_empty() || target.contains('\0') {
        return Err("An open target is required".into());
    }
    let target = target.to_string();
    tokio::task::spawn_blocking(move || open::that_detached(target).map_err(|e| e.to_string()))
        .await
        .map_err(|e| e.to_string())??;
    Ok(json!({"ok":true,"message":"Opened"}))
}

