import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, readdir, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { runBridge, serialExecutor } from '../lib/runner.js';
import { apply } from '../index.js';

// Use isolated temporary assets, never the user's knowledge base.
const data = path.join(tmpdir(), 'dsh-alaya-test');
await mkdir(data, { recursive: true });
const base = await mkdtemp(path.join(data, '集成-'));
const kbRoot = path.join(base, '知识库 with spaces');
const call = (request, config, signal) => runBridge({ kbRoot, ...request }, config, signal);

test('guide is available before knowledge-base initialization', async () => {
  assert.match(await call({ action: 'guide', topic: 'retrieval' }), /检索/);
});

test('initialize, inspect personas, preserve settings on reinitialization', async () => {
  const result = await call({ action: 'init', examples: true });
  assert.equal(result.ok, true, result.stderr);
  const config = JSON.parse(await readFile(path.join(kbRoot, 'alaya/config.json'), 'utf8'));
  assert.equal(config.memory.semantic_memory_enabled, false);
  const personas = await call({ action: 'run', command: 'personas', argsJson: '["list"]' });
  assert.equal(personas.ok, true, personas.stderr);
  assert.match(personas.stdout, /feynman/);
  await call({ action: 'init', semanticMemory: true });
  assert.equal(JSON.parse(await readFile(path.join(kbRoot, 'alaya/config.json'), 'utf8')).memory.semantic_memory_enabled, false);
});

test('read and search example knowledge with honest bounds', async () => {
  const result = await call({ action: 'read', path: 'wiki/index.md', limit: 10 });
  assert.equal(result.text.length, 10);
  assert.equal(result.truncated, true);
  const search = await call({ action: 'search', query: 'Transformer' });
  assert.ok(search.matches.some((m) => m.path.includes('Transformer')));
});

test('reject path traversal, package data roots and root overrides', async () => {
  await assert.rejects(call({ action: 'read', path: '../../package.json' }), /escapes/);
  await assert.rejects(runBridge({ action: 'init', kbRoot: path.resolve('vendor') }), /separate/);
  await assert.rejects(call({ action: 'run', command: 'health', argsJson: '["--kb-root=other"]' }), /kb_root/);
  await assert.rejects(call({ action: 'run', command: 'health', argsJson: '["--kb=other"]' }), /kb_root/);
  await assert.rejects(call({ action: 'run', command: 'personas', argsJson: '["purge","x"]' }), /purge/);
});

test('import preview writes nothing, commit imports, rebuild indexes', async () => {
  const source = path.join(base, 'source');
  await mkdir(source);
  await writeFile(path.join(source, '测试资料.md'), '# Integration test\n\nAn adapter import about 光合作用 and energy.\n');
  const args = [source, '--category', 'integration', '--copy-raw', 'no'];
  const preview = await call({ action: 'run', command: 'import', argsJson: JSON.stringify([...args, '--dry-run']) });
  assert.equal(preview.ok, true, preview.stderr);
  await assert.rejects(readdir(path.join(kbRoot, 'wiki/integration')), /ENOENT/);
  const result = await call({ action: 'run', command: 'import', argsJson: JSON.stringify(args) });
  assert.equal(result.ok, true, result.stderr);
  assert.ok((await readdir(path.join(kbRoot, 'wiki/integration'))).some((f) => f.endsWith('.md')));
  const index = await call({ action: 'run', command: 'index', argsJson: '["--full"]' });
  assert.equal(index.ok, true, index.stderr);
});

test('profile memory stdin transport, show and forget round-trip', async () => {
  const update = await call({ action: 'run', command: 'memory',
    argsJson: '["set","--payload-file","-"]',
    stdin: JSON.stringify({ fields: { language: { value: '简体中文', source: 'user_confirmed' } } }) });
  assert.equal(update.ok, true, update.stderr);
  const show = await call({ action: 'run', command: 'memory', argsJson: '["show"]' });
  assert.equal(show.ok, true, show.stderr);
  assert.match(show.stdout, /简体中文/);
  const forget = await call({ action: 'run', command: 'memory', argsJson: '["forget","language"]' });
  assert.equal(forget.ok, true, forget.stderr);
  assert.ok(!(await readdir(path.join(kbRoot, 'alaya'))).some((name) => name.startsWith('.dsh-payload-')));
});

test('health and links report diagnostics without transport failure', async () => {
  for (const command of ['health', 'links']) {
    const result = await call({ action: 'run', command });
    assert.equal(typeof result.exitCode, 'number');
    assert.ok(result.stdout.length + result.stderr.length > 0);
  }
});

test('invalid script options stay errors and never invoke a shell', async () => {
  const result = await call({ action: 'run', command: 'health', argsJson: '["; echo unexpected"]' });
  assert.equal(result.ok, false);
  assert.notEqual(result.exitCode, 0);
});

test('process output bounds, missing Python and pre-aborted execution', async () => {
  await assert.rejects(call({ action: 'guide', topic: 'overview' }, { maxOutputBytes: 100 }), /output limit/);
  await assert.rejects(call({ action: 'guide' }, { python: 'nonexistent-alaya-python-9484' }), /Cannot start Python/);
  const abort = new AbortController();
  abort.abort(new Error('cancel test'));
  await assert.rejects(call({ action: 'guide' }, {}, abort.signal), /cancel test/);
});

test('failed serialized operation does not poison the queue', async () => {
  const serial = serialExecutor();
  const events = [];
  const first = serial(async () => { events.push(1); throw new Error('expected'); });
  const second = serial(async () => { events.push(2); return 'ok'; });
  await assert.rejects(first, /expected/);
  assert.equal(await second, 'ok');
  assert.deepEqual(events, [1, 2]);
});

test('adapter registers five actual defineTool definitions and responds', async () => {
  const tools = [];
  let onDispose;
  apply({ tools: { register: (tool) => tools.push(tool) }, on: (event, fn) => { assert.equal(event, 'dispose'); onDispose = fn; } }, { kbRoot });
  assert.equal(tools.length, 5);
  const guide = tools.find((tool) => tool.name === 'alaya_guide');
  const result = await guide.execute({ topic: 'router' }, { signal: new AbortController().signal });
  assert.match(result, /Alaya/);
  onDispose();
  await assert.rejects(guide.execute({}, { signal: new AbortController().signal }), /unloaded/);
});
