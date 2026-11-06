import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const bridge = fileURLToPath(new URL('../bridge.py', import.meta.url));

export async function runBridge(request, config = {}, signal) {
  signal?.throwIfAborted();
  const timeoutMs = config.timeoutMs ?? 120000;
  const maxOutputBytes = config.maxOutputBytes ?? 1048576;
  return new Promise((resolve, reject) => {
    const child = spawn(config.python ?? 'python', ['-B', '-X', 'utf8', bridge], {
      shell: false, windowsHide: true,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONIOENCODING: 'utf-8' },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    const out = [], err = [];
    let bytes = 0, failure;
    const stop = (reason) => { failure ??= reason; child.kill(); };
    const onAbort = () => stop(signal.reason ?? new Error('Alaya cancelled'));
    signal?.addEventListener('abort', onAbort, { once: true });
    if (signal?.aborted) onAbort();
    const timer = setTimeout(() => stop(new Error(`Alaya exceeded ${timeoutMs} ms`)), timeoutMs);
    const cleanup = () => { clearTimeout(timer); signal?.removeEventListener('abort', onAbort); };
    for (const [stream, chunks] of [[child.stdout, out], [child.stderr, err]]) {
      stream.on('data', (data) => {
        bytes += data.length;
        if (bytes > maxOutputBytes) stop(new Error('Alaya output limit exceeded; narrow the query'));
        else chunks.push(data);
      });
    }
    child.on('error', (error) => { cleanup(); reject(new Error(`Cannot start Python (${config.python ?? 'python'}): ${error.message}`)); });
    child.stdin.on('error', (error) => { if (error.code !== 'EPIPE') stop(error); });
    child.on('close', (code) => {
      cleanup();
      if (failure) return reject(failure);
      const stdout = Buffer.concat(out).toString('utf8');
      const stderr = Buffer.concat(err).toString('utf8');
      try {
        const value = JSON.parse(stdout);
        if (code !== 0) return reject(new Error(value.error ?? stderr ?? 'Alaya bridge failed'));
        resolve(value);
      } catch (error) {
        reject(new Error(`Invalid Alaya bridge response: ${stderr || stdout.slice(0, 300) || error.message}`));
      }
    });
    child.stdin.end(JSON.stringify(request));
  });
}

// Upstream multi-file writers must never overlap, including separate tool calls.
export function serialExecutor() {
  let tail = Promise.resolve();
  return (task) => {
    const next = tail.then(task);
    tail = next.catch(() => {});
    return next;
  };
}
