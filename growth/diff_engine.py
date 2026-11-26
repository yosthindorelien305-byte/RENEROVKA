"""Inert text Diff Engine for AI Growth proposals (PR 4.2, zero code/SQL/shell execution)."""

import difflib

SEO_FIELD_GUIDANCE = {
    'title': {'min': 30, 'max': 60, 'label': 'HTML Title (30–60 символов)'},
    'meta_description': {'min': 120, 'max': 160, 'label': 'Meta Description (120–160 символов)'},
    'og_title': {'min': 20, 'max': 65, 'label': 'OG Title (20–65 символов)'},
    'og_description': {'min': 60, 'max': 160, 'label': 'OG Description (60–160 символов)'},
    'h1': {'min': 10, 'max': 70, 'label': 'Заголовок H1 (10–70 символов)'},
}


def compute_text_diff(original_text, proposed_text, *, field_name='content', target_object=''):
    """Compute line-level, unified, and side-by-side diff for plain text values."""
    orig = '' if original_text is None else str(original_text)
    prop = '' if proposed_text is None else str(proposed_text)

    orig_lines = orig.splitlines()
    prop_lines = prop.splitlines()

    matcher = difflib.SequenceMatcher(None, orig_lines, prop_lines)
    added_lines = []
    removed_lines = []
    side_by_side = []
    unchanged_count = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for offset in range(i2 - i1):
                line = orig_lines[i1 + offset]
                unchanged_count += 1
                side_by_side.append({
                    'type': 'equal',
                    'oldLineNum': i1 + offset + 1,
                    'newLineNum': j1 + offset + 1,
                    'oldText': line,
                    'newText': line,
                })
        elif tag == 'delete':
            for offset in range(i2 - i1):
                line = orig_lines[i1 + offset]
                removed_lines.append(line)
                side_by_side.append({
                    'type': 'delete',
                    'oldLineNum': i1 + offset + 1,
                    'newLineNum': None,
                    'oldText': line,
                    'newText': '',
                })
        elif tag == 'insert':
            for offset in range(j2 - j1):
                line = prop_lines[j1 + offset]
                added_lines.append(line)
                side_by_side.append({
                    'type': 'insert',
                    'oldLineNum': None,
                    'newLineNum': j1 + offset + 1,
                    'oldText': '',
                    'newText': line,
                })
        elif tag == 'replace':
            max_len = max(i2 - i1, j2 - j1)
            for offset in range(max_len):
                has_old = (i1 + offset) < i2
                has_new = (j1 + offset) < j2
                o_txt = orig_lines[i1 + offset] if has_old else ''
                n_txt = prop_lines[j1 + offset] if has_new else ''
                if has_old:
                    removed_lines.append(o_txt)
                if has_new:
                    added_lines.append(n_txt)
                side_by_side.append({
                    'type': 'replace',
                    'oldLineNum': (i1 + offset + 1) if has_old else None,
                    'newLineNum': (j1 + offset + 1) if has_new else None,
                    'oldText': o_txt,
                    'newText': n_txt,
                })

    unified = list(
        difflib.unified_diff(
            orig_lines,
            prop_lines,
            fromfile=f'current:{target_object or field_name}',
            tofile=f'proposed:{target_object or field_name}',
            lineterm='',
        )
    )

    guidance = SEO_FIELD_GUIDANCE.get(str(field_name or '').strip().lower())
    return {
        'fieldName': str(field_name or 'content'),
        'targetObject': str(target_object or ''),
        'original': orig,
        'proposed': prop,
        'hasChanges': orig != prop,
        'addedLines': added_lines,
        'removedLines': removed_lines,
        'unifiedDiff': '\n'.join(unified),
        'sideBySideLines': side_by_side,
        'stats': {
            'addedCount': len(added_lines),
            'removedCount': len(removed_lines),
            'unchangedCount': unchanged_count,
            'originalLength': len(orig),
            'proposedLength': len(prop),
            'lengthDelta': len(prop) - len(orig),
        },
        'seoFieldGuidance': guidance,
    }
