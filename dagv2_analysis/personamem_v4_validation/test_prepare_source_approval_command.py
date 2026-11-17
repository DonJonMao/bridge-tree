"""Offline command-parser probes only: no prepare, receipts, models or source edits."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    'approval_command_probe', Path(__file__).with_name('prepare_source_approval.py'))
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class FullSuiteCommandProbe(unittest.TestCase):
    ROOT = Path('/unused/unit-probe-source')

    def fake_git(self, *, dirty=False, paths=('dagbt/runner.py', 'tests/test_reader.py',
                                             'tests/nested/reader_test.py')):
        def read(root, *args):
            self.assertEqual(root, self.ROOT)
            if args == ('status', '--porcelain', '--untracked-files=normal'):
                return ' M dagbt/runner.py' if dirty else ''
            self.assertEqual(args, ('ls-tree', '-r', '--name-only', '-z', 'HEAD'))
            return '\0'.join(paths) + '\0'
        return read

    def test_original_whole_suite_command_stays_accepted(self):
        with patch.object(verifier, 'git') as git:
            for executable in ('python', 'python3', '/venv/bin/python'):
                verifier.verify_test_command(executable + ' -m pytest -q')
            git.assert_not_called()

    def test_exact_tests_whole_suite_is_checked_against_clean_commit_inventory(self):
        with patch.object(verifier, 'git', side_effect=self.fake_git()) as git:
            verifier.verify_test_command('/venv/bin/python -m pytest -q tests', self.ROOT)
            self.assertEqual(git.call_count, 2)

    def test_explicit_tests_requires_root(self):
        with self.assertRaises(verifier.ApprovalError):
            verifier.verify_test_command('python -m pytest -q tests')

    def test_dirty_checkout_is_rejected(self):
        with patch.object(verifier, 'git', side_effect=self.fake_git(dirty=True)):
            with self.assertRaises(verifier.ApprovalError):
                verifier.verify_test_command('python -m pytest -q tests', self.ROOT)

    def test_outside_tracked_tests_or_empty_inventory_are_rejected(self):
        for paths in (('tests/test_a.py', 'test_outside.py'),
                      ('tests/test_a.py', 'scripts/outside_test.py'),
                      ('tests_extra/test_a.py',), ('dagbt/runner.py',)):
            with self.subTest(paths=paths), patch.object(verifier, 'git', side_effect=self.fake_git(paths=paths)):
                with self.assertRaises(verifier.ApprovalError):
                    verifier.verify_test_command('python -m pytest -q tests', self.ROOT)

    def test_selectors_subsets_and_extra_options_are_rejected(self):
        for command in ('python -m pytest -q tests/test_reader.py',
                        'python -m pytest -q tests/nested',
                        'python -m pytest -q tests -k reader',
                        'python -m pytest -q -k reader',
                        'python -m pytest -q tests --ignore=tests/test_reader.py',
                        'python -m pytest -q tests tests/test_reader.py',
                        'python -m pytest -q .', 'pytest -q tests', ''):
            with self.subTest(command=command), patch.object(verifier, 'git') as git:
                with self.assertRaises(verifier.ApprovalError):
                    verifier.verify_test_command(command, self.ROOT)
                git.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
