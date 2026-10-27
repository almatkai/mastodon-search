const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const Ajv=require('ajv/dist/2020').default,formats=require('ajv-formats');
const root=path.resolve(__dirname,'../..');
const schema=JSON.parse(fs.readFileSync(path.join(root,'qa/fixtures/host/schemas/extension-v3.schema.json'),'utf8'));
const manifest=JSON.parse(fs.readFileSync(path.join(root,'extension.json'),'utf8'));
const ajv=new Ajv({strict:false,allErrors:true,validateFormats:true});formats(ajv);const valid=ajv.compile(schema);
assert.ok(valid(manifest),JSON.stringify(valid.errors));let count=1;
for(const mutate of [m=>m.schemaVersion=2,m=>m.id='com.tezbar.mastodon-search',m=>m.runtime='javascript',m=>m.execution='bun',m=>m.protocolVersion=2,m=>delete m.repository,m=>m.repository='bad uri',m=>m.capabilities=['clipboard.all'],m=>m.commands=[],m=>m.commands[0].timeoutMs=300001,m=>m.commands[0].refreshMs=1,m=>m.preferences={},m=>m.unknown=true,m=>m.verification[0].state='pass',m=>m.artifacts={'x86_64-pc-windows-gnu':{}},m=>m.artifacts={'aarch64-apple-darwin':{url:'file:///tmp/a',sha256:'x',executable:'../x',executableSha256:'x'}},m=>m.files={'../escape':'0'.repeat(64)},m=>m.files={'bin\\escape':'0'.repeat(64)}]){const m=structuredClone(manifest);mutate(m);assert.equal(valid(m),false,JSON.stringify(m));count++;}
const m=structuredClone(manifest);m.files={'bin/mastodon-search':'0'.repeat(64)};m.artifacts={'aarch64-apple-darwin':{url:'https://example.invalid/owned.zip',sha256:'0'.repeat(64),executable:'bin/mastodon-search',executableSha256:'0'.repeat(64)}};assert.ok(valid(m));count++;
fs.writeFileSync(path.join(root,'qa/evidence/schema.json'),JSON.stringify({count,schemaPin:'ea100cee3f69711de12485ba061950c5fc65258f',validator:'ajv 8.17.1 draft2020 full schema + formats',sourceArtifactsEmpty:Object.keys(manifest.artifacts).length===0},null,2)+'\n');console.log(`${count} complete schema-3 positive/negative checks`);
