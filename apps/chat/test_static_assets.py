import re
from pathlib import Path

from django.test import SimpleTestCase

CSS_PATH = Path(__file__).resolve().parent / 'static' / 'chat' / 'css' / 'style.css'


class StylesheetTests(SimpleTestCase):
    def setUp(self):
        raw = CSS_PATH.read_text(encoding='utf-8')
        self.css = re.sub(r'/\*.*?\*/', '', raw, flags=re.S)

    def test_braces_are_balanced(self):
        depth = 0
        for char in self.css:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                self.assertGreaterEqual(depth, 0, 'Лишняя закрывающая скобка }')
        self.assertEqual(depth, 0, 'Не закрыта скобка {')

    def test_layout_rules_exist(self):
        for selector in (
            '.shell', '.main', '.topbar', '.messages', '.composer-bar',
            '.rail-inner', '.chats', '.message',
        ):
            with self.subTest(selector=selector):
                self.assertRegex(self.css, r'(^|\s|\})' + re.escape(selector) + r'\s*\{')

    def test_rail_is_driven_by_a_single_class(self):
        self.assertIn('.rail-open .rail-label', self.css)
        self.assertNotIn('.rail:is(:hover', self.css)