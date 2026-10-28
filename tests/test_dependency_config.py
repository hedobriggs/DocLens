"""Local synthetic configuration/lock safety; no real settings are read."""
import errno
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dotenv import dotenv_values, set_key, unset_key
from filelock import FileLock, Timeout


class ConfigurationDependencies(unittest.TestCase):
    def test_lock_symlink_does_not_truncate_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            victim = root / 'preserve.txt'
            victim.write_text('synthetic original must survive')
            link = root / 'unsafe.lock'
            link.symlink_to(victim)
            try:
                with FileLock(link, timeout=0):
                    pass
            except (OSError, Timeout):
                pass  # Refusal is safe; target integrity is the assertion.
            self.assertEqual(victim.read_text(), 'synthetic original must survive')

    def test_lock_excludes_another_owner_and_releases(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / 'synthetic.lock'
            with FileLock(lock, timeout=0):
                with self.assertRaises(Timeout), FileLock(lock, timeout=0):
                    pass
            with FileLock(lock, timeout=0):
                pass

    def test_configuration_literal_read_and_normal_rewrite(self):
        text = "KEY='Synthetic-$literal-$(never-execute)'\n"
        self.assertEqual(dotenv_values(stream=StringIO(text))['KEY'],
                         'Synthetic-$literal-$(never-execute)')
        with tempfile.TemporaryDirectory() as temp:
            env = Path(temp) / 'synthetic.env'
            env.write_text(text)
            set_key(env, 'SECOND', 'synthetic')
            self.assertEqual(dotenv_values(env)['SECOND'], 'synthetic')
            unset_key(env, 'SECOND')
            self.assertEqual(dotenv_values(env)['KEY'], 'Synthetic-$literal-$(never-execute)')
            self.assertNotIn('SECOND', dotenv_values(env))

    def test_cross_device_env_rewrite_does_not_overwrite_symlink_target(self):
        for operation in ('set', 'unset'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                victim = root / 'preserve.env'
                original = "KEY='synthetic-original'\n"
                victim.write_text(original)
                link = root / 'unsafe.env'
                link.symlink_to(victim)
                # Deterministically exercise shutil.move's EXDEV fallback on the
                # old library without requiring host mounts or another disk.
                with patch('dotenv.main.os.rename', side_effect=OSError(errno.EXDEV, 'synthetic cross-device')):
                    try:
                        if operation == 'set':
                            set_key(link, 'KEY', 'synthetic-change')
                        else:
                            unset_key(link, 'KEY')
                    except OSError:
                        pass
                self.assertEqual(victim.read_text(), original)


if __name__ == '__main__':
    unittest.main()
