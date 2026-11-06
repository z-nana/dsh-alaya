"""DSH JSON transport for the unmodified, vendored Alaya scripts."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile

BASE = Path(__file__).resolve().parent
UPSTREAM = BASE / 'vendor' / 'alaya'
SCRIPTS = {
    'health': 'health_check.py', 'index': 'build_index.py',
    'links': 'fix_links.py', 'personas': 'persona_manager.py',
    'memory': 'memory_manager.py', 'commit': 'perfume.py',
    'observe': 'bi_observer.py', 'import': 'batch_import.py',
    'paper': 'import_paper.py', 'card': 'post_process.py',
    'quality': 'import_quality_review.py',
}
GUIDES = {'overview': 'README.md', 'router': 'SKILL.md',
          **{key: 'skills/alaya-%s/SKILL.md' % key for key in
             ('persona', 'retrieval', 'import', 'memory', 'maintenance')}}


def within(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def root_of(request):
    raw = request.get('kbRoot', '')
    if not raw or not Path(raw).is_absolute():
        raise ValueError('Provide an absolute kb_root or configure kbRoot in the plugin settings.')
    root = Path(raw).resolve()
    if within(root, BASE) or within(BASE, root):
        raise ValueError('Knowledge base must be separate from the plugin installation directory.')
    return root


def execute_script(script, args, root, stdin=''):
    # Never consult or overwrite the user's global ~/.alaya_path pointer.
    os.environ['ALAYA_PATH_FILE'] = str(root / 'alaya' / '.dsh_path')
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.path.insert(0, str(UPSTREAM / 'scripts'))
    sys.argv = [str(UPSTREAM / 'scripts' / script), '--kb-root', str(root), *args]
    sys.stdin = io.StringIO(stdin)
    output = io.StringIO()
    error = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
        try:
            runpy.run_path(sys.argv[0], run_name='__main__')
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return {'ok': code == 0, 'exitCode': code, 'stdout': output.getvalue(), 'stderr': error.getvalue()}


def handle(request):
    action = request['action']
    if action == 'guide':
        key = request.get('topic', 'router')
        if key not in GUIDES:
            raise ValueError('Unknown guide topic: ' + str(key))
        return (UPSTREAM / GUIDES[key]).read_text(encoding='utf-8-sig')
    root = root_of(request)
    if action == 'init':
        # Default memory opt-out; enable explicitly when the user requests it.
        args = ['--non-interactive', '--with-personas',
                '--with-semantic-memory' if request.get('semanticMemory') else '--no-semantic-memory']
        if request.get('examples'):
            args.append('--with-examples')
        if root.exists() and any(root.iterdir()) and not (root / 'alaya/config.json').is_file():
            raise ValueError('Initialization requires an empty directory or an existing Alaya knowledge base.')
        return execute_script('setup_wizard.py', args, root)
    if not (root / 'alaya/config.json').is_file():
        raise ValueError('Knowledge base is not initialized. Use alaya_init first.')
    if action == 'read':
        relative = request['path']
        if Path(relative).is_absolute():
            raise ValueError('path must be relative to the knowledge base')
        path = (root / relative).resolve()
        if not within(path, root):
            raise ValueError('Path escapes the knowledge base')
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('File exceeds the 2 MiB read limit')
        text = path.read_text(encoding='utf-8-sig')
        offset = request.get('offset', 0)
        limit = request.get('limit', 16000)
        if not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or not 1 <= limit <= 64000:
            raise ValueError('offset must be nonnegative; limit must be 1..64000 characters')
        return {'path': relative, 'text': text[offset:offset+limit], 'totalChars': len(text),
                'truncated': offset+limit < len(text)}
    if action == 'search':
        query = request['query'].strip().casefold()
        if not query:
            raise ValueError('query must not be empty')
        hits, scanned, truncated = [], 0, False
        for path in sorted((root / 'wiki').rglob('*.md')):
            if not within(path.resolve(), root) or path.stat().st_size > 2 * 1024 * 1024:
                continue
            if scanned >= 2000 or len(hits) >= 50:
                truncated = True
                break
            scanned += 1
            text = path.read_text(encoding='utf-8-sig')
            pos = text.casefold().find(query)
            if pos >= 0:
                hits.append({'path': path.relative_to(root).as_posix(),
                             'excerpt': text[max(0, pos-100):pos+400]})
        return {'matches': hits, 'scanned': scanned, 'truncated': truncated,
                'method': 'literal case-insensitive search; use indexes for semantic retrieval'}
    if action == 'run':
        command = request['command']
        if command not in SCRIPTS:
            raise ValueError('Unknown Alaya command')
        args = json.loads(request.get('argsJson', '[]'))
        if not isinstance(args, list) or len(args) > 40 or any(not isinstance(x, str) or '\x00' in x for x in args):
            raise ValueError('args_json must be a JSON array of at most 40 strings')
        if any(x.startswith('--') and '--kb-root'.startswith(x.split('=', 1)[0]) for x in args):
            raise ValueError('Set kb_root through the tool parameter, not args_json')
        if command == 'personas' and args and args[0] == 'purge':
            raise ValueError('Permanent purge is not exposed by this adapter; use recoverable delete instead')
        stdin = request.get('stdin', '')
        if command == 'memory' and '--payload-file' in args:
            index = args.index('--payload-file') + 1
            if index < len(args) and args[index] == '-':
                # The upstream profile writer expects a file, whereas perfume
                # already accepts stdin. Keep the compatibility file local and
                # remove it on success and failure without changing upstream.
                with tempfile.TemporaryDirectory(prefix='.dsh-payload-', dir=str(root / 'alaya')) as temp:
                    payload = Path(temp) / 'payload.json'
                    payload.write_text(stdin, encoding='utf-8')
                    args[index] = str(payload)
                    return execute_script(SCRIPTS[command], args, root)
        return execute_script(SCRIPTS[command], args, root, stdin)
    raise ValueError('Unknown action')


if __name__ == '__main__':
    try:
        result = handle(json.load(sys.stdin))
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        sys.exit(1)
