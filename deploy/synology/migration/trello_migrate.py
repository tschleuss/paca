#!/usr/bin/env python3
"""Rich, resumable Trello -> Paca migration. Planning is offline and the default.

Unlike trello_import.py, this preserves interactive checklists and creates native
comments. Avatars, profiles, subscriptions and activity noise are omitted.
The only network destination used by this script is the configured Paca origin.
"""
import argparse
from collections import Counter
import copy
import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from trello_import import all_tasks, write_json

RUNTIME = Path.home() / 'Library/Application Support/Paca-OrbStack'
HERE = Path(__file__).resolve().parent
LABEL_KEY = 'labels'
SOURCE_KEY = 'trello_url'
NUMBER_KEY = 'trello_number'
WORKFLOW = {
    'To-do': ('todo', '#eab308'),
    'Doing': ('inprogress', '#3b82f6'),
    'Agent Review': ('inprogress', '#a855f7'),
    'Human Review/Feedback': ('inprogress', '#f97316'),
    'Done 🎉': ('done', '#22c55e'),
}
# Equivalent color families; Trello's named shades are mapped to explicit hex.
PALETTE = {
    'green': ('#baf3db', '#4bce97', '#1f845a'),
    'yellow': ('#f8e6a0', '#f5cd47', '#946f00'),
    'orange': ('#fedec8', '#fea362', '#c25100'),
    'red': ('#ffd5d2', '#f87168', '#c9372c'),
    'purple': ('#dfd8fd', '#9f8fef', '#6e5dc6'),
    'blue': ('#cce0ff', '#579dff', '#0c66e4'),
    'sky': ('#c6edfb', '#6cc3e0', '#227d9b'),
    'lime': ('#d3f1a7', '#94c748', '#5b7f24'),
    'pink': ('#fdd0ec', '#e774bb', '#ae4787'),
    'black': ('#dcdfe4', '#8590a2', '#626f86'),
}


def label_name(label):
    return label.get('name') or label.get('color') or 'Unspecified'


def label_color(label):
    name = label.get('color') or 'black'
    family = name.removesuffix('_light').removesuffix('_dark')
    shade = 0 if name.endswith('_light') else 2 if name.endswith('_dark') else 1
    return PALETTE.get(family, PALETTE['black'])[shade]


def block(text, kind='paragraph', **props):
    return {'id': str(uuid.uuid4()), 'type': kind, 'props': props,
            'content': [{'type': 'text', 'text': text, 'styles': {}}], 'children': []}


def comment_marker(source_id):
    # Stable block ID survives API readback and doesn't depend on comment text.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'trello-comment:' + source_id))


def canonical(value):
    """Ignore editor-generated block IDs, preserving content, styles and state."""
    if isinstance(value, list):
        return [canonical(x) for x in value]
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items() if k != 'id'}
    return value


def compile_plan(board, extra_comments=None, converter=None):
    lists = {x['id']: x for x in board.get('lists', []) if not x.get('closed')}
    if len(lists) != len(board.get('lists', [])) or any(c.get('closed') for c in board['cards']):
        raise ValueError('Archived content requires an explicit mapping; this rich importer stops rather than dropping it')
    if len({c['id'] for c in board['cards']}) != len(board['cards']):
        raise ValueError('Duplicate source card IDs')
    for name in [x['name'] for x in lists.values()]:
        if name not in WORKFLOW:
            raise ValueError('Add an explicit WORKFLOW mapping for list: ' + name)
    # Avoid implying that unsupported files/custom values have been copied.
    if any(c.get('attachments') or c.get('customFieldItems') for c in board['cards']):
        raise ValueError('This rich importer needs an extension for attachments/custom fields; nothing was imported')
    checklist_by_id = {x['id']: x for x in board.get('checklists', [])}
    comments = {}
    for a in board.get('actions', []):
        if a.get('type') in ('commentCard', 'copyCommentCard'):
            comments[a['id']] = {
                'id': a['id'], 'card_id': a['data']['card']['id'],
                'text': a['data'].get('text', ''), 'date': a.get('date', ''),
                'author': a.get('memberCreator', {}).get('fullName', 'unknown'),
            }
    for c in extra_comments or []:
        comments[c['id']] = c
    ids = {c['id'] for c in board['cards']}
    comments = {k: v for k, v in comments.items() if v['card_id'] in ids}
    markdown = {c['id']: c.get('desc', '') for c in board['cards']}
    markdown.update({'comment:' + k: c['text'] for k, c in comments.items()})
    if converter is None:
        proc = subprocess.run(['node', str(HERE / 'markdown-to-blocknote.mjs')],
                              input=json.dumps(markdown), text=True,
                              capture_output=True, check=False)
        if proc.returncode:
            raise RuntimeError('Markdown converter failed. Run npm ci in deploy/synology/agents; no data was imported.')
        converted = json.loads(proc.stdout)
    else:
        converted = converter(markdown)
    tasks = []
    for card in sorted(board['cards'], key=lambda c: c['idShort']):
        if card['idList'] not in lists:
            raise ValueError('Card references an unknown source list')
        description = copy.deepcopy(converted[card['id']])
        for checklist_id in card.get('idChecklists', []):
            checklist = checklist_by_id[checklist_id]
            description.append(block(checklist['name'], 'heading', level=3))
            for item in sorted(checklist.get('checkItems', []), key=lambda x: x.get('pos', 0)):
                description.append(block(item['name'], 'checkListItem', checked=item['state']=='complete'))
        source_url = card.get('url') or card.get('shortUrl')
        description.append(block('Original Trello card: ' + source_url))
        task_comments = []
        for c in sorted((c for c in comments.values() if c['card_id']==card['id']),
                        key=lambda x: (x.get('date', ''), x['id'])):
            header = block('Imported from Trello · ' + c.get('author', 'unknown') +
                           ' · ' + c.get('date', '') + ' · comment ' + c['id'])
            header['id'] = comment_marker(c['id'])
            task_comments.append({'trello_id': c['id'],
                                  'content': [header] + converted['comment:' + c['id']]})
        labels = list(dict.fromkeys(label_name(x) for x in card.get('labels', [])))
        tasks.append({'trello_id': card['id'], 'number': card['idShort'],
                      'list_id': card['idList'], 'position': card.get('pos', 0),
                      'body': {'title': card['name'], 'description': description,
                               'tags': ['trello-import', 'trello-id-' + card['id']],
                               'custom_fields': {LABEL_KEY: labels, SOURCE_KEY: source_url,
                                                 NUMBER_KEY: card['idShort']},
                               'start_date': card.get('start'), 'due_date': card.get('due')},
                      'comments': task_comments})
    options = {}
    for label in board.get('labels', []):
        name = label_name(label)
        color = label_color(label)
        if name in options and options[name]['color'] != color:
            raise ValueError('Same label name has different colors; choose a disambiguation')
        options[name] = {'value': name, 'color': color}
    return {'format': 2, 'board_id': board['id'], 'board_name': board['name'],
            'lists': sorted(lists.values(), key=lambda x: x.get('pos', 0)),
            'label_options': list(options.values()), 'tasks': tasks,
            'counts': {'cards': len(tasks), 'labels': len(options),
                       'checklists': sum(len(c.get('idChecklists', [])) for c in board['cards']),
                       'check_items': sum(len(x.get('checkItems', [])) for x in checklist_by_id.values()),
                       'comments': sum(len(t['comments']) for t in tasks)}}


class API:
    def __init__(self, origin, ca=None, key=None):
        parsed = urllib.parse.urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.path not in ('', '/')
                or parsed.username or parsed.query or parsed.fragment):
            raise ValueError('Paca origin must be HTTPS without credentials or an API path')
        self.origin, self.key = origin.rstrip('/'), key
        self.jar = http.cookiejar.CookieJar()
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca)))

    def call(self, method, path, body=None):
        if not path.startswith('/api/'):
            raise ValueError('Only Paca API paths are accepted')
        headers = {'Content-Type': 'application/json'}
        if self.key:
            headers['X-API-Key'] = self.key
        req = urllib.request.Request(self.origin + path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.opener.open(req, timeout=60) as res:
                raw = res.read()
                out = json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            # Do not retry writes blindly after uncertain responses.
            raise RuntimeError(f'Paca HTTP {e.code}: {method} {path}; stopped, rerun to reconcile') from None
        if isinstance(out, dict) and 'success' in out:
            if not out['success']:
                raise RuntimeError('Paca reported failure')
            return out.get('data')
        return out

    @classmethod
    def local_admin(cls):
        env = dict(line.split('=', 1) for line in (RUNTIME / '.env').read_text().splitlines()
                   if line and not line.startswith('#') and '=' in line)
        api = cls('https://localhost:8443', str(RUNTIME / 'secrets/root.crt'))
        api.call('POST', '/api/v1/auth/login',
                 {'username': env['ADMIN_USERNAME'], 'password': env['ADMIN_PASSWORD']})
        return api


def activities(api, root):
    cursor, seen, result = None, set(), []
    while True:
        page = api.call('GET', root + '/activities?' + urllib.parse.urlencode(
            {'page_size': 100, **({'cursor': cursor} if cursor else {})}))
        result.extend(page['items'])
        cursor = page.get('next_cursor')
        if not cursor:
            return result
        if cursor in seen:
            raise RuntimeError('Repeated activity cursor')
        seen.add(cursor)


def content_of(activity):
    value = activity.get('content') or {}
    return value.get('body', value.get('content', [])) if isinstance(value, dict) else value


def prepare_project(api, project, plan):
    root = '/api/v1/projects/' + str(uuid.UUID(project))
    statuses = api.call('GET', root + '/task-statuses')['items']
    mapping = {}
    # Reuse the empty project's stock statuses; no task is deleted or moved.
    aliases = {'To-do': 'Backlog', 'Doing': 'In Progress',
               'Agent Review': 'Todo', 'Done 🎉': 'Done'}
    assigned = set()
    for position, source_list in enumerate(plan['lists'], 1):
        name = source_list['name']
        current = next((s for s in statuses if s['name']==name), None)
        if current is None:
            current = next((s for s in statuses if s['name']==aliases.get(name)
                            and s['id'] not in assigned), None)
        category, color = WORKFLOW[name]
        body = {'name': name, 'category': category, 'color': color, 'position': position}
        if current:
            if any(current.get(k) != v for k, v in body.items()):
                current = api.call('PATCH', root + '/task-statuses/' + current['id'], body)
        else:
            current = api.call('POST', root + '/task-statuses', body)
            statuses.append(current)
        mapping[source_list['id']] = current['id']
        assigned.add(current['id'])
    fields = api.call('GET', root + '/custom-fields')['items']
    for body in [
        {'field_key': LABEL_KEY, 'display_name': 'Labels', 'field_type': 'multi_select',
         'options': plan['label_options'], 'use_in_search': True},
        {'field_key': SOURCE_KEY, 'display_name': 'Trello card', 'field_type': 'url'},
        {'field_key': NUMBER_KEY, 'display_name': 'Trello number', 'field_type': 'number'},
    ]:
        found = next((f for f in fields if f['field_key']==body['field_key']), None)
        if found is None:
            api.call('POST', root + '/custom-fields', body)
        elif found['field_type'] != body['field_type'] or (
                body.get('options') and found.get('options') != body['options']):
            raise RuntimeError('Existing custom field differs; refusing to overwrite it')
    views = api.call('GET', root + '/views?context=backlog')['items']
    view = next((v for v in views if v['name']=='Stash board'), None)
    config = {'column_by': 'status', 'sort_by': 'manual',
              'fields': ['importance', LABEL_KEY], 'initial_page_size': 25, 'page_size': 25}
    if view is None:
        view = api.call('POST', root + '/views?context=backlog',
                        {'name': 'Stash board', 'view_type': 'board', 'config': config})
    return {'project_id': project, 'board_id': plan['board_id'],
            'list_status_ids': mapping, 'view_id': view['id']}


def apply_plan(api, project, plan, journal):
    project = str(uuid.UUID(project))
    root = '/api/v1/projects/' + project
    existing = all_tasks(api, project)
    if any(not any(t.startswith('trello-id-') for t in (task.get('tags') or [])) for task in existing):
        raise RuntimeError('Destination contains non-migration tasks; refusing to reconfigure it')
    records = {'project_id': project, 'board_id': plan['board_id'], 'cards': {}, 'comments': {}}
    if Path(journal).exists():
        records = json.loads(Path(journal).read_text())
        if records['project_id'] != project or records['board_id'] != plan['board_id']:
            raise ValueError('Journal belongs to another source or destination')
    source_ids = {t['trello_id'] for t in plan['tasks']}
    indexed = {}
    for task in existing:
        for marker in task.get('tags') or []:
            if marker.startswith('trello-id-'):
                cid = marker.removeprefix('trello-id-')
                if cid not in source_ids or cid in indexed:
                    raise RuntimeError('Unexpected or duplicate migration marker in destination')
                indexed[cid] = task
    for cid in records['cards']:
        if cid not in indexed:
            raise RuntimeError('A previously imported card is missing; refusing to recreate it')
    mapping = prepare_project(api, project, plan)
    records['mapping'] = mapping
    write_json(journal, records)
    for count, task in enumerate(plan['tasks'], 1):
        cid = task['trello_id']
        expected = {**task['body'], 'status_id': mapping['list_status_ids'][task['list_id']]}
        found = indexed.get(cid)
        if not found:
            found = api.call('POST', root + '/tasks', expected)
        tid = found['id']
        records['cards'][cid] = tid
        write_json(journal, records)
        check = api.call('GET', root + '/tasks/' + tid)
        for key in ('title', 'status_id', 'tags', 'custom_fields', 'description', 'start_date', 'due_date'):
            if canonical(check.get(key)) != canonical(expected.get(key)):
                raise RuntimeError('Task content differs; stopped rather than overwriting: ' + cid + ' ' + key)
        if check.get('sprint_id'):
            raise RuntimeError('Imported task unexpectedly belongs to a sprint')
        task_root = root + '/tasks/' + tid
        existing_comments = {}
        if task['comments']:
            for a in activities(api, task_root):
                if a.get('activity_type') != 'comment':
                    continue
                content = content_of(a)
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get('id'):
                            existing_comments[b['id']] = a
        for comment in task['comments']:
            mid = comment_marker(comment['trello_id'])
            found_comment = existing_comments.get(mid)
            if not found_comment:
                if comment['trello_id'] in records['comments']:
                    raise RuntimeError('Previously imported comment missing; refusing to recreate it')
                found_comment = api.call('POST', task_root + '/activities/comments',
                                         {'content': comment['content']})
            records['comments'][comment['trello_id']] = found_comment['id']
            write_json(journal, records)
            if canonical(content_of(found_comment)) != canonical(comment['content']):
                raise RuntimeError('Comment content verification failed: ' + comment['trello_id'])
        if count % 25 == 0 or count == len(plan['tasks']):
            print(f"Verified {count}/{len(plan['tasks'])} cards; {len(records['comments'])} comments", flush=True)
    # Use the REST endpoint and verify persisted positions (MCP move has a known bug).
    position_root = root + '/views/' + mapping['view_id'] + '/task-positions'
    existing_positions = {p['task_id']: p for p in api.call('GET', position_root)['items']}
    for task in plan['tasks']:
        tid = records['cards'][task['trello_id']]
        body = {'position': task['position'], 'group_key': mapping['list_status_ids'][task['list_id']]}
        current = existing_positions.get(tid, {})
        if any(current.get(k) != v for k, v in body.items()):
            api.call('PUT', position_root + '/' + tid, body)
    positions = {p['task_id']: p for p in api.call('GET', position_root)['items']}
    for task in plan['tasks']:
        p = positions[records['cards'][task['trello_id']]]
        if p['position'] != task['position'] or p['group_key'] != mapping['list_status_ids'][task['list_id']]:
            raise RuntimeError('Board order verification failed')
    totals = Counter(t['status_id'] for t in all_tasks(api, project))
    expected_totals = Counter(mapping['list_status_ids'][t['list_id']] for t in plan['tasks'])
    if totals != expected_totals:
        raise RuntimeError('Destination card/status totals differ from source')
    records['verified_counts'] = plan['counts']
    records['verified_status_totals'] = dict(totals)
    write_json(journal, records)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('--comments', type=Path, help='Supplemental comments from paginated Trello reads')
    parser.add_argument('--output', required=True, type=Path, help='Private plan JSON')
    parser.add_argument('--project-id')
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--ca', default=str(RUNTIME / 'secrets/root.crt'))
    parser.add_argument('--local-admin', action='store_true', help='Use installed OrbStack .env credentials locally')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    plan = compile_plan(json.loads(args.export.read_text()),
                        json.loads(args.comments.read_text()) if args.comments else None)
    write_json(args.output, plan)
    print(json.dumps(plan['counts']), flush=True)
    if len(json.loads(args.export.read_text()).get('actions', [])) >= 1000 and not args.comments:
        print('WARNING: Export activity may be truncated; only exported comments can be imported.')
    if args.apply:
        if not args.project_id or not args.journal:
            parser.error('--apply requires --project-id and --journal')
        api = API.local_admin() if args.local_admin else API(
            os.environ['PACA_API_URL'], args.ca, os.environ['PACA_API_KEY'])
        apply_plan(api, args.project_id, plan, args.journal)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, RuntimeError, OSError) as e:
        sys.exit('Migration stopped: ' + str(e))
