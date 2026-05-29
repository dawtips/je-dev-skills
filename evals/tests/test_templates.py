import unittest

from evals.evaluator.templates import render


class TestRender(unittest.TestCase):
    def test_basic_substitution(self):
        self.assertEqual(render("Hi {name}", name="Ada"), "Hi Ada")

    def test_multiple_and_repeated(self):
        out = render("{a}-{b}-{a}", a="1", b="2")
        self.assertEqual(out, "1-2-1")

    def test_literal_braces_escaped(self):
        # {{ }} must survive as literal braces around a JSON example.
        out = render('{{"k": {v}}}', v="3")
        self.assertEqual(out, '{"k": 3}')

    def test_unknown_placeholder_raises(self):
        with self.assertRaises(KeyError):
            render("Hello {missing}")

    def test_extra_values_ignored(self):
        self.assertEqual(render("{a}", a="x", unused="y"), "x")

    def test_non_placeholder_braces_left_alone(self):
        # A stray brace that is not a valid {identifier} is not touched.
        self.assertEqual(render("100% {a}", a="done"), "100% done")


if __name__ == "__main__":
    unittest.main()
