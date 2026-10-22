"""Meaningful migration checks; synthetic data only."""
import copy
import unittest

from trello_migrate import block, canonical, comment_marker, compile_plan


def converter(markdown):
    return {key: [block(text)] if text else [] for key, text in markdown.items()}


class RichMigrationTest(unittest.TestCase):
    def board(self):
        return {'id': 'b1', 'name': 'Stash',
                'lists': [{'id': 'l1', 'name': 'To-do', 'pos': 1}],
                'labels': [{'id': 'label1', 'name': 'bug', 'color': 'red_dark'}],
                'members': [{'avatarUrl': 'SHOULD_NOT_MIGRATE'}],
                'cards': [{'id': 'c1', 'idShort': 1, 'idList': 'l1', 'name': 'Unicode ✓',
                           'desc': 'Original body', 'pos': 99, 'url': 'https://trello.com/c/abc',
                           'labels': [{'name': 'bug', 'color': 'red_dark'}], 'idChecklists': ['check1']}],
                'checklists': [{'id': 'check1', 'name': 'Card', 'checkItems': [
                    {'name': 'Unfinished', 'state': 'incomplete', 'pos': 2},
                    {'name': 'Finished', 'state': 'complete', 'pos': 1}]}],
                'actions': [{'id': 'comment1', 'type': 'commentCard', 'date': '2026-01-01T12:00:00Z',
                             'data': {'card': {'id': 'c1'}, 'text': 'Exported comment'},
                             'memberCreator': {'fullName': 'Original author', 'avatarUrl': 'SHOULD_NOT_MIGRATE'}}]}

    def test_editable_checklists_preserve_order_and_state(self):
        plan = compile_plan(self.board(), converter=converter)
        items = [b for b in plan['tasks'][0]['body']['description'] if b['type']=='checkListItem']
        self.assertEqual([b['content'][0]['text'] for b in items], ['Finished', 'Unfinished'])
        self.assertEqual([b['props']['checked'] for b in items], [True, False])
        self.assertNotIn('SHOULD_NOT_MIGRATE', str(plan))

    def test_live_comments_fill_export_gap_without_duplicates(self):
        extra = [{'id': 'comment1', 'card_id': 'c1', 'text': 'Updated comment',
                  'date': '2026-01-01T12:00:00Z', 'author': 'Original author'},
                 {'id': 'comment0', 'card_id': 'c1', 'text': 'Older missing comment',
                  'date': '2025-12-01T12:00:00Z', 'author': 'Another author'},
                 {'id': 'unrelated', 'card_id': 'other', 'text': 'Not in this board'}]
        p = compile_plan(self.board(), extra, converter)
        cs = p['tasks'][0]['comments']
        self.assertEqual(p['counts']['comments'], 2)
        self.assertEqual([c['trello_id'] for c in cs], ['comment0', 'comment1'])
        self.assertIn('Original author', str(cs[1]))
        self.assertIn('2026-01-01T12:00:00Z', str(cs[1]))
        self.assertEqual(cs[1]['content'][0]['id'], comment_marker('comment1'))
        self.assertIn('Updated comment', str(cs[1]))

    def test_labels_are_colored_options_not_duplicated_tags(self):
        p = compile_plan(self.board(), converter=converter)
        self.assertEqual(p['tasks'][0]['body']['custom_fields']['labels'], ['bug'])
        self.assertEqual(p['label_options'], [{'value': 'bug', 'color': '#c9372c'}])
        self.assertNotIn('bug', p['tasks'][0]['body']['tags'])

    def test_unsupported_source_data_fails_before_import(self):
        for change in ['archived', 'attachment', 'unknown-list', 'missing-checklist']:
            b = self.board()
            if change=='archived': b['cards'][0]['closed'] = True
            if change=='attachment': b['cards'][0]['attachments'] = [{'url': 'private'}]
            if change=='unknown-list': b['lists'][0]['name'] = 'Unknown'
            if change=='missing-checklist': b['checklists'] = []
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                compile_plan(b, converter=converter)

    def test_conflicting_label_names_are_not_silently_collapsed(self):
        b = self.board()
        b['labels'].append({'id': 'label2', 'name': 'bug', 'color': 'blue'})
        with self.assertRaises(ValueError):
            compile_plan(b, converter=converter)

    def test_verification_ignores_block_ids_but_checks_checkbox_state(self):
        a = block('Task', 'checkListItem', checked=True)
        b = copy.deepcopy(a); b['id'] = 'new-id'
        self.assertEqual(canonical(a), canonical(b))
        b['props']['checked'] = False
        self.assertNotEqual(canonical(a), canonical(b))


if __name__ == '__main__':
    unittest.main()
