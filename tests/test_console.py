import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ConsoleTests(unittest.TestCase):
    def test_demo_and_cli_with_legacy_output_encoding(self):
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=str(repo / "src"))
        with tempfile.TemporaryDirectory() as temp:
            demo = subprocess.run([sys.executable, str(repo / "examples/demo.py"), "--root", temp],
                                  env=env, capture_output=True)
            self.assertEqual(demo.returncode, 0, demo.stderr.decode("utf-8", errors="replace"))
            report = Path(demo.stdout.decode("utf-8").strip())
            self.assertTrue(report.is_file())
            cli = subprocess.run([sys.executable, "-m", "ud_core", "init", "--root", temp,
                                  "--title", "中文终端测试", "--goal", "校验编码"],
                                 env=env, capture_output=True)
            self.assertEqual(cli.returncode, 0, cli.stderr.decode("utf-8", errors="replace"))
            self.assertIn("中文终端测试", cli.stdout.decode("utf-8"))
