"""Audit a semantic B-roll shot map; not a substitute for rendered-video QA."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def audit(data):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return {'verdict': 'FAIL', 'errors': ['Root must be an object'], 'warnings': []}
    duration = data.get('duration')
    items = data.get('items')
    if not numeric(duration) or duration <= 0:
        errors.append('duration must be positive and finite')
    if not isinstance(items, list) or not items:
        return {'verdict': 'FAIL', 'errors': errors + ['items must contain the actual B-roll shots'], 'warnings': []}
    uses, seen, spans = defaultdict(list), set(), []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f'item {i}: expected object'); continue
        label = item.get('id')
        if not isinstance(label, str) or not label:
            label = f'item-{i}'; errors.append(f'{label}: missing id')
        if label in seen:
            errors.append(f'{label}: duplicate id')
        seen.add(label)
        start, end = item.get('timeline_in'), item.get('timeline_out')
        if not numeric(start) or not numeric(end) or start < 0 or end <= start:
            errors.append(f'{label}: invalid timeline range'); continue
        if numeric(duration) and end > duration + .001:
            errors.append(f'{label}: shot exceeds video duration')
        spans.append((start, end, label, item.get('overlap_reason')))
        anchor = item.get('spoken_anchor')
        if numeric(anchor):
            if anchor < 0 or anchor > end:
                errors.append(f'{label}: spoken anchor outside applicable video range')
            if anchor - start > .100001 and not item.get('early_entry_reason'):
                errors.append(f'{label}: enters {anchor-start:.3f}s before its word')
        elif item.get('purpose') not in ['evoke', 'reset']:
            errors.append(f'{label}: missing spoken_anchor')
        asset = item.get('asset_key')
        if not isinstance(asset, str) or not asset:
            errors.append(f'{label}: missing asset_key')
        else:
            uses[asset].append((label, item.get('reuse_reason')))
        states = item.get('state_changes', [])
        if not isinstance(states, list):
            errors.append(f'{label}: state_changes must be a list'); states = []
        hold_reason = item.get('hold_reason')
        valid_hold = isinstance(hold_reason, str) and bool(hold_reason.strip())
        if hold_reason is not None and not valid_hold:
            errors.append(f'{label}: hold_reason must be a non-empty explanation')
        if item.get('information_card') and end-start > 2.5 and len(states) < 2 and not valid_hold:
            errors.append(f'{label}: long information card needs meaningful states or a justified reading hold')
        previous = start
        for state in states:
            if not isinstance(state, dict) or not state.get('state') or not numeric(state.get('time')):
                errors.append(f'{label}: malformed state'); continue
            t = state['time']
            if t < previous or t > end:
                errors.append(f'{label}: state timing is unordered or outside shot')
            previous = t
        if item.get('source_kind') == 'generated' and item.get('purpose') == 'prove':
            errors.append(f'{label}: generated media cannot serve as factual proof')
        if item.get('source_kind') in ['primary', 'public', 'contextual', 'official']:
            if not item.get('source_url') or not item.get('rights_note'):
                warnings.append(f'{label}: add source_url and rights_note to provenance')
    for asset, rows in uses.items():
        if len(rows) > 1 and not all(reason for _, reason in rows):
            errors.append(f'{asset}: repeated asset lacks reuse_reason for every use')
    active = []
    for start, end, label, reason in sorted(spans):
        active = [row for row in active if row[1] > start + .001]
        for prev in active:
            if not reason and not prev[3]:
                errors.append(f'{prev[2]} / {label}: overlapping shots need overlap_reason')
        active.append((start, end, label, reason))
    return {'verdict': 'FAIL' if errors else 'PASS_WITH_WARNINGS' if warnings else 'PASS', 'items': len(items), 'errors': errors, 'warnings': warnings}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('shot_map', type=Path)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    try:
        result = audit(json.loads(args.shot_map.read_text(encoding='utf-8-sig')))
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    text = json.dumps(result, ensure_ascii=True, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + '\n', encoding='utf8')
    print(text)
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
