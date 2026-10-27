#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
host=ROOT/'qa/fixtures/host/src-tauri/src/native_core'
clipboard=(host/'launcher/clipboard.rs').read_text()
worker=clipboard[clipboard.index('    fn handle(&mut self, c: &str, a: &[Value]) -> CoreResult {'):clipboard.index('\n}\n#[cfg(test)]')]
platform=(host/'platform.rs').read_text()
opened=platform[platform.index('async fn open_target('):platform.index('\nasync fn selected_text(')]
out=ROOT/'qa/fixtures/producer-functions.rs'
out.write_text('// Unmodified complete functions from host ea100cee3f69711de12485ba061950c5fc65258f.\nimpl Worker {\n'+worker+'\n}\n'+opened+'\n')
(ROOT/'qa/evidence/producer-extraction.json').write_text(json.dumps({'hostPin':'ea100cee3f69711de12485ba061950c5fc65258f','functions':{'Worker::handle':hashlib.sha256(worker.encode()).hexdigest(),'open_target':hashlib.sha256(opened.encode()).hexdigest()},'effectBoundaries':'native clipboard, image/base64, open, fs, clock and storage replaced by synthetic adapters before execution'},indent=2)+'\n')
