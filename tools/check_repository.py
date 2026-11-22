"""Check the portable skill archive, using only the Python standard library."""
import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--visibility', choices=('private', 'public'),
                        help='Visibility observed on GitHub for the release check')
    args = parser.parse_args()
    errors = []
    catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8-sig'))
    if catalog.get('repository') != 'Leon-Drq/AI-VIDEO-CUT':
        errors.append('catalog must identify the Leon-Drq/AI-VIDEO-CUT repository')
    if catalog.get('visibility') not in ('private', 'public'):
        errors.append('catalog must declare repository visibility')
    elif args.visibility and catalog['visibility'] != args.visibility:
        errors.append('catalog visibility differs from the visibility observed on GitHub')
    rows = catalog.get('skills', [])
    if not rows:
        errors.append('catalog.skills must not be empty')
    names = set()
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    for item in rows:
        name = item.get('name', '')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64 or name in names:
            errors.append(f'invalid or duplicate skill name: {name}')
        names.add(name)
        if item.get('path') != f'skills/{name}' or item.get('entrypoint') != f'skills/{name}/SKILL.md':
            errors.append(f'{name}: catalog path and entrypoint must use the skill name')
            continue
        path = ROOT / item['entrypoint']
        if not path.is_file():
            errors.append(f'{name}: missing SKILL.md')
            continue
        text = path.read_text(encoding='utf-8')
        front = re.match(r'^---\n(.*?)\n---(?:\n|$)', text, re.S)
        if not front:
            errors.append(f'{name}: missing YAML frontmatter')
        else:
            fields = front.group(1)
            match = re.search(r'^name:\s*[\"\']?([^\"\'\n]+)', fields, re.M)
            if not match or match.group(1).strip() != name:
                errors.append(f'{name}: frontmatter name mismatch')
            if not re.search(r'^description:\s*\S', fields, re.M):
                errors.append(f'{name}: missing description')
        if f'({item["entrypoint"]})' not in readme:
            errors.append(f'{name}: README must link the entrypoint')
    actual = {p.parent.name for p in (ROOT / 'skills').glob('*/SKILL.md')}
    if actual != names:
        errors.append(f'catalog/directory mismatch: {sorted(actual ^ names)}')

    # Include new untracked archive content, but not intentionally ignored local caches.
    listing = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--cached', '--others',
        '--exclude-standard', '-z'], capture_output=True, check=True)
    files = sorted(set(p.decode('utf-8') for p in listing.stdout.split(b'\0') if p))
    blocked_ext = {'.pyc', '.pyo', '.mp4', '.mov', '.mkv', '.wav', '.mp3', '.onnx', '.safetensors', '.pt', '.pth'}
    for rel in files:
        path = ROOT / rel
        if not path.is_file():
            continue
        if path.suffix.lower() in blocked_ext or '__pycache__' in path.parts or path.name in {'.env', 'credentials.json'}:
            errors.append(f'non-skill runtime or private environment file: {rel}')
        if path.stat().st_size > 100 * 1024 * 1024:
            errors.append(f'oversized file requires review: {rel}')
        if path.suffix == '.py':
            try:
                ast.parse(path.read_text(encoding='utf-8-sig'), filename=rel)
            except (SyntaxError, UnicodeError) as exc:
                errors.append(f'{rel}: {type(exc).__name__}')
        if path.suffix == '.json':
            try:
                json.loads(path.read_text(encoding='utf-8-sig'))
            except (ValueError, UnicodeError):
                errors.append(f'{rel}: invalid JSON')
        if path.suffix == '.md':
            text = path.read_text(encoding='utf-8-sig')
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                    continue
                target = unquote(target.strip('<>').split('#')[0])
                if target and not (path.parent / target).exists():
                    errors.append(f'{rel}: missing relative link {target}')
    result = {'ok':not errors, 'skills':len(rows), 'files_checked':len(files), 'errors':errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
