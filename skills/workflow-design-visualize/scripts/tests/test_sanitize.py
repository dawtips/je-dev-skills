import unittest

from visualize_blueprint import escape_label, sanitize_node_id


class TestSanitizeNodeId(unittest.TestCase):
    def test_passthrough_safe_id(self):
        self.assertEqual(sanitize_node_id("validate_inputs", set()), "validate_inputs")

    def test_dedupes_duplicates(self):
        used = set()
        a = sanitize_node_id("step", used)
        b = sanitize_node_id("step", used)
        c = sanitize_node_id("step", used)
        self.assertEqual((a, b, c), ("step", "step__2", "step__3"))

    def test_leading_digit_prefixed(self):
        self.assertEqual(sanitize_node_id("123abc", set()), "n_123abc")

    def test_special_chars_to_underscore(self):
        self.assertEqual(sanitize_node_id("a-b.c", set()), "a_b_c")

    def test_all_special_falls_back(self):
        self.assertEqual(sanitize_node_id("***", set()), "node")


class TestEscapeLabel(unittest.TestCase):
    def test_escapes_markup_chars(self):
        self.assertEqual(
            escape_label('a "b" <c> & [d]'),
            "a &quot;b&quot; &lt;c&gt; &amp; &#91;d&#93;",
        )

    def test_collapses_whitespace(self):
        self.assertEqual(escape_label("multi\n line\there"), "multi line here")

    def test_none_is_empty(self):
        self.assertEqual(escape_label(None), "")


if __name__ == "__main__":
    unittest.main()
