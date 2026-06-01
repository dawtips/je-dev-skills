import contextlib
import io
import os
import shutil
import tempfile
import unittest

from visualize_blueprint import (blueprint_name, default_out_path, load_blueprint,
                                 main, render_document)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MINIMAL = os.path.join(FIXTURES, "minimal.blueprint.md")


class TestPaths(unittest.TestCase):
    def test_default_out_path_blueprint(self):
        self.assertEqual(default_out_path("a/b/foo.blueprint.md"), "a/b/foo.diagram.md")

    def test_default_out_path_plain_md(self):
        self.assertEqual(default_out_path("a/bar.md"), "a/bar.diagram.md")

    def test_blueprint_name(self):
        self.assertEqual(blueprint_name("a/b/foo.blueprint.md"), "foo")


class TestCli(unittest.TestCase):
    def test_stdout_matches_render_document(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([MINIMAL, "--stdout"])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), render_document(load_blueprint(MINIMAL), "minimal"))

    def test_writes_sibling_by_default(self):
        tmp = tempfile.mkdtemp()
        try:
            dst = os.path.join(tmp, "wf.blueprint.md")
            shutil.copyfile(MINIMAL, dst)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main([dst])
            out_path = os.path.join(tmp, "wf.diagram.md")
            self.assertEqual(rc, 0)
            self.assertIn("Wrote " + out_path, buf.getvalue())
            self.assertTrue(os.path.isfile(out_path))
            with open(out_path, encoding="utf-8") as f:
                self.assertEqual(f.read(), render_document(load_blueprint(dst), "wf"))
        finally:
            shutil.rmtree(tmp)

    def test_out_flag(self):
        tmp = tempfile.mkdtemp()
        try:
            out_path = os.path.join(tmp, "custom.md")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main([MINIMAL, "--out", out_path])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(out_path))
        finally:
            shutil.rmtree(tmp)

    def test_bad_input_exits_2(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([os.path.join(FIXTURES, "broken_no_yaml.blueprint.md")])
        self.assertEqual(rc, 2)
        self.assertIn("ERROR", buf.getvalue())

    def test_missing_file_exits_2(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([os.path.join(FIXTURES, "does_not_exist.blueprint.md")])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
