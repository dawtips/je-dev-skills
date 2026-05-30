import os
import tempfile
import unittest
from pathlib import Path

from advise_model import AdviceInputError, resolve_blueprint_path


def _touch(path):
    with open(path, "w", encoding="utf-8"):
        pass


class TestResolve(unittest.TestCase):
    def test_single_workflow_file_auto_discovers(self):
        with tempfile.TemporaryDirectory() as d:
            wf = os.path.join(d, "workflows")
            os.makedirs(wf)
            bp = os.path.join(wf, "a.blueprint.md")
            _touch(bp)
            self.assertEqual(resolve_blueprint_path(None, cwd=d), Path(bp))

    def test_zero_files_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(AdviceInputError) as cm:
                resolve_blueprint_path(None, cwd=d)
            self.assertIn("no ./workflows", str(cm.exception))

    def test_multiple_files_raises(self):
        with tempfile.TemporaryDirectory() as d:
            wf = os.path.join(d, "workflows")
            os.makedirs(wf)
            _touch(os.path.join(wf, "a.blueprint.md"))
            _touch(os.path.join(wf, "b.blueprint.md"))
            with self.assertRaises(AdviceInputError) as cm:
                resolve_blueprint_path(None, cwd=d)
            self.assertIn("multiple blueprint files", str(cm.exception))

    def test_wrong_suffix_explicit_path_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "notablueprint.md")
            _touch(p)
            with self.assertRaises(AdviceInputError) as cm:
                resolve_blueprint_path(p, cwd=d)
            self.assertIn("must end with .blueprint.md", str(cm.exception))

    def test_relative_explicit_path_resolves_against_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            _touch(os.path.join(d, "x.blueprint.md"))
            resolved = resolve_blueprint_path("x.blueprint.md", cwd=d)
            self.assertTrue(resolved.is_absolute())
            self.assertEqual(resolved.name, "x.blueprint.md")


if __name__ == "__main__":
    unittest.main()
