#!/usr/bin/env python3
"""Offline Trello board JSON planner + explicit, create-only Paca importer.

Python stdlib only. Does not contact Trello, fetch attachments, or delete data.
Dry-run is the default. Use one dedicated destination project per board.
"""
import argparse
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def plan(board, include_archived=False):
    lists = {x['id']: x for x in board.get('lists', [])}
    members = {x['id']: x.get('fullName') or x.get('username', x['id'])
               for x in board.get('members', [])}
    checklists = {x['id']: x for x in board.get('checklists', [])}
    comments = {}
    for action in board.get('actions', []):
        if action.get('type') == 'commentCard':
            cid = action.get('data', {}).get('card', {}).get('id')
            comments.setdefault(cid, []).append(action)
    tasks = []
    skipped = 0
    cards = sorted(board.get('cards', []), key=lambda c: (c.get('idList', ''), c.get('pos', 0)))
    seen = set()
    for card in cards:
        cid = card['id']
        if cid in seen:
            raise ValueError('Duplicate card ID in export')
        seen.add(cid)
        archived = bool(card.get('closed') or lists.get(card['idList'], {}).get('closed'))
        if archived and not include_archived:
            skipped += 1
            continue
        lines = [card.get('desc', ''), '', 'Trello migration record',
                 f"Source card: {card.get('url') or card.get('shortUrl') or cid}",
                 f"Trello ID: {cid}",
                 f"List: {lists.get(card['idList'], {}).get('name', card['idList'])}",
                 f"Archived in source: {archived}",
                 f"Due complete: {bool(card.get('dueComplete'))}",
                 'Members: ' + ', '.join(members.get(m, m) for m in card.get('idMembers', []))]
        for checklist_id in card.get('idChecklists', []):
            checklist = checklists.get(checklist_id)
            if checklist is None:
                lines.append(f'CHECKLIST MISSING FROM EXPORT: {checklist_id}')
                continue
            lines += ['', checklist.get('name', 'Checklist')]
            for item in sorted(checklist.get('checkItems', []), key=lambda i: i.get('pos', 0)):
                mark = 'x' if item.get('state') == 'complete' else ' '
                lines.append(f"[{mark}] {item.get('name', '')}")
        if card.get('attachments'):
            lines += ['', 'Attachment references (files are NOT copied):']
            lines += [f"{a.get('name', '')}: {a.get('url', '')}" for a in card['attachments']]
        for action in sorted(comments.get(cid, []), key=lambda a: a.get('date', '')):
            author = action.get('memberCreator', {})
            lines += ['', f"Imported comment — {author.get('fullName') or author.get('username', 'unknown')} — {action.get('date', '')}",
                      action.get('data', {}).get('text', '')]
        if card.get('customFieldItems'):
            lines += ['', 'Original custom field values (raw IDs; see original export for definitions):',
                      json.dumps(card['customFieldItems'], ensure_ascii=False)]
        tags = list(dict.fromkeys([x.get('name') or x.get('color', 'label') for x in card.get('labels', [])]
                                 + ['trello-import', f'trello-id-{cid}']))
        tasks.append({'trello_id': cid, 'list_id': card['idList'], 'title': card['name'],
                      'description_text': '\n'.join(lines), 'tags': tags,
                      'start_date': card.get('start'), 'due_date': card.get('due')})
    return {'format': 1, 'board_id': board['id'], 'board_name': board.get('name', ''),
            'tasks': tasks, 'skipped_archived': skipped,
            'warnings': ['Only comments/checklists present in this export are included.',
                         'Attachment URLs are references, not local file backups.',
                         'Members, custom fields, original authors/timestamps and archive state are recorded as text; permissions, automations and history are not recreated.']}


class API:
    def __init__(self, base, key, ca=None):
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.path not in ('', '/') or parsed.username or parsed.query or parsed.fragment:
            raise ValueError('PACA_API_URL must be an HTTPS origin without /api or credentials')
        self.base, self.key = base.rstrip('/'), key
        context = ssl.create_default_context(cafile=ca)
        # Never forward the API key to a redirect target.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), NoRedirect())

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={'X-API-Key': self.key, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=60) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'Paca HTTP {exc.code}; import stopped. Inspect permissions and destination before rerunning.') from None
        if isinstance(result, dict) and 'success' in result:
            if not result['success']:
                raise RuntimeError('API reported failure')
            return result['data']
        return result


def all_tasks(api, project):
    tasks, cursor, seen = [], None, set()
    while True:
        params = {'page_size': 100}
        if cursor:
            params['cursor'] = cursor
        data = api.call('GET', f'/api/v1/projects/{project}/tasks?' + urllib.parse.urlencode(params))
        if isinstance(data, list):
            tasks.extend(data)
            break
        tasks.extend(data['items'])
        cursor = data.get('next_cursor')
        if not cursor:
            break
        if cursor in seen:
            raise RuntimeError('API repeated a pagination cursor')
        seen.add(cursor)
    return tasks


def apply(import_plan, mapping, api, journal):
    project = str(uuid.UUID(mapping['project_id']))
    statuses = mapping['list_status_ids']
    for task in import_plan['tasks']:
        uuid.UUID(statuses[task['list_id']])  # validate every mapping before any mutation
    existing = {}
    for task in all_tasks(api, project):
        for tag in task.get('tags') or []:
            if tag.startswith('trello-id-'):
                if tag in existing:
                    raise RuntimeError('Duplicate migration marker in destination; resolve manually')
                existing[tag] = task
    records = {'project_id': project, 'board_id': import_plan['board_id'], 'cards': {}}
    if Path(journal).exists():
        records = json.loads(Path(journal).read_text())
        if records['project_id'] != project or records['board_id'] != import_plan['board_id']:
            raise ValueError('Journal belongs to a different board or project')
    for task in import_plan['tasks']:
        marker = 'trello-id-' + task['trello_id']
        found = existing.get(marker)
        if not found and task['trello_id'] in records['cards']:
            raise RuntimeError('Previously imported task is no longer visible; refusing to recreate it')
        if not found:
            blocks = [{'id': str(uuid.uuid4()), 'type': 'paragraph', 'props': {},
                       'content': [{'type': 'text', 'text': line, 'styles': {}}], 'children': []}
                      for line in task['description_text'].split('\n')]
            body = {'title': task['title'], 'description': blocks,
                    'status_id': statuses[task['list_id']], 'tags': task['tags']}
            for field in ('start_date', 'due_date'):
                if task.get(field):
                    body[field] = task[field]
            found = api.call('POST', f'/api/v1/projects/{project}/tasks', body)
        tid = str(uuid.UUID(found['id']))
        records['cards'][task['trello_id']] = tid
        # Persist before verification so an interruption cannot silently lose the mapping.
        write_json(journal, records)
        check = api.call('GET', f'/api/v1/projects/{project}/tasks/{tid}')
        if marker not in (check.get('tags') or []) or check['title'] != task['title'] or check['status_id'] != statuses[task['list_id']]:
            raise RuntimeError('Destination verification failed; inspect task before rerunning')
        print(f"Verified {task['trello_id']} -> {tid}")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path, help='Trello board JSON export')
    parser.add_argument('--output', type=Path, required=True, help='Private plan JSON path')
    parser.add_argument('--include-archived', action='store_true')
    parser.add_argument('--mapping', type=Path)
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--ca', help='Caddy public root certificate PEM')
    parser.add_argument('--apply', action='store_true', help='Create tasks in Paca; default is offline only')
    args = parser.parse_args()
    os.umask(0o077)
    result = plan(json.loads(args.export.read_text()), args.include_archived)
    write_json(args.output, result)
    print(f"Plan: {len(result['tasks'])} tasks; {result['skipped_archived']} archived cards skipped.")
    for warning in result['warnings']:
        print('NOTE: ' + warning)
    if args.apply:
        if not args.mapping or not args.journal:
            parser.error('--apply requires --mapping and --journal')
        api = API(os.environ['PACA_API_URL'], os.environ['PACA_API_KEY'], args.ca)
        apply(result, json.loads(args.mapping.read_text()), api, args.journal)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, RuntimeError, OSError) as exc:
        sys.exit(f'Import stopped: {exc}')
