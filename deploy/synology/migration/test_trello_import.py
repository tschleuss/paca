"""Migration safeguards: run python3 -m unittest discover -s migration -v."""
import copy
import tempfile
import unittest
import uuid
from pathlib import Path

from trello_import import all_tasks, apply, plan


class MigrationTest(unittest.TestCase):
    def board(self):
        return {'id': 'board1', 'name': 'Work', 'lists': [{'id': 'todo', 'name': 'To Do'}],
                'members': [{'id': 'm1', 'fullName': 'A Person'}],
                'cards': [{'id': 'c1', 'name': 'Unicode ✓', 'idList': 'todo', 'desc': 'Details',
                           'due': '2026-10-22T17:00:00Z', 'idMembers': ['m1'],
                           'idChecklists': ['ch1'], 'attachments': [{'name': 'file.txt', 'url': 'https://example.invalid/file'}]},
                          {'id': 'c2', 'name': 'Old', 'idList': 'todo', 'closed': True}],
                'checklists': [{'id': 'ch1', 'name': 'Steps', 'checkItems': [{'name': 'Done', 'state': 'complete'}]}],
                'actions': [{'type': 'commentCard', 'date': '2026-10-01T12:00:00Z',
                             'memberCreator': {'fullName': 'Original author'},
                             'data': {'card': {'id': 'c1'}, 'text': 'Original comment'}}]}

    def test_plan_preserves_content_and_defaults_to_active(self):
        p = plan(self.board())
        self.assertEqual(len(p['tasks']), 1)
        self.assertEqual(p['skipped_archived'], 1)
        text = p['tasks'][0]['description_text']
        for expected in ('Details', '[x] Done', 'A Person', 'Original author', 'Original comment', 'file.txt'):
            self.assertIn(expected, text)
        self.assertEqual(p['tasks'][0]['due_date'], '2026-10-22T17:00:00Z')
        self.assertEqual(len(plan(self.board(), True)['tasks']), 2)

    def test_archived_list_is_skipped(self):
        b = self.board()
        b['lists'][0]['closed'] = True
        self.assertEqual(plan(b)['tasks'], [])

    def test_repeated_pagination_cursor_fails(self):
        class RepeatingAPI:
            def call(self, *args):
                return {'items': [], 'next_cursor': 'same'}
        with self.assertRaises(RuntimeError):
            all_tasks(RepeatingAPI(), str(uuid.uuid4()))

    def test_rerun_creates_no_duplicate_even_without_journal(self):
        class FakeAPI:
            def __init__(self):
                self.tasks = []
            def call(self, method, path, body=None):
                if method == 'POST':
                    task = copy.deepcopy(body)
                    task['id'] = str(uuid.uuid4())
                    self.tasks.append(task)
                    return task
                if '?' in path:
                    return {'items': copy.deepcopy(self.tasks), 'next_cursor': None}
                return copy.deepcopy(self.tasks[0])
        api = FakeAPI()
        mapping = {'project_id': str(uuid.uuid4()), 'list_status_ids': {'todo': str(uuid.uuid4())}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'journal.json'
            apply(plan(self.board()), mapping, api, path)
            path.unlink()  # emulate response received but journal lost after interruption
            apply(plan(self.board()), mapping, api, path)
            self.assertEqual(len(api.tasks), 1)
            bad = copy.deepcopy(mapping)
            bad['list_status_ids'] = {}
            with self.assertRaises(KeyError):
                apply(plan(self.board()), bad, api, path)
            self.assertEqual(len(api.tasks), 1)


if __name__ == '__main__':
    unittest.main()
