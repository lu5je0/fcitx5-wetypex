"""Check clipboard routing without reading the desktop clipboard or starting sync."""

import ast
import hashlib
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock


source = Path(__file__).resolve().parents[1] / "scripts/fcitx5-wetypex-syncd.sh.in"
functions = ast.parse(source.read_text())
functions.body = [
    node for node in functions.body
    if isinstance(node, ast.FunctionDef)
    and node.name in {"_local_clipboard_silently", "local_clipboard"}
]


class ClipboardRoutingTest(unittest.TestCase):
    def setUp(self):
        self.command = Mock()
        self.namespace = {
            "hashlib": hashlib,
            "clipboard_helper": "clipboard-helper",
            "wl_paste": "wl-paste",
            "surface_required": Mock(return_value=True),
            "_x11_environment": Mock(return_value={"QT_QPA_PLATFORM": "xcb"}),
            "clipboard_command": self.command,
        }
        exec(compile(functions, str(source), "exec"), self.namespace)

    def read(self):
        return self.namespace["local_clipboard"]({})

    def result(self, code=0, output=b""):
        return subprocess.CompletedProcess([], code, output, b"")

    def test_oversized_text_never_falls_back_to_wayland(self):
        for size in (16385, 47662, 65536):
            with self.subTest(size=size):
                self.command.reset_mock()
                self.command.side_effect = [
                    self.result(1), self.result(output=b"x" * size),
                ]
                self.assertIsNone(self.read())
                self.assertEqual(self.command.call_count, 2)

    def test_unavailable_x11_skips_poll(self):
        self.namespace["_x11_environment"].return_value = None
        self.assertIsNone(self.read())
        self.command.assert_not_called()

    def test_helper_failure_never_falls_back_to_wayland(self):
        for failed in (None, self.result(2), self.result(-6)):
            with self.subTest(result=failed):
                self.command.reset_mock()
                self.command.side_effect = [failed]
                self.assertIsNone(self.read())
                self.assertEqual(self.command.call_count, 1)

    def test_invalid_utf8_never_falls_back_to_wayland(self):
        self.command.side_effect = [self.result(1), self.result(output=b"\xff")]
        self.assertIsNone(self.read())
        self.assertEqual(self.command.call_count, 2)

    def test_small_text_still_syncs(self):
        content = "测试".encode()
        self.command.side_effect = [self.result(1), self.result(output=content)]
        self.assertEqual(self.read(), ("text", content, hashlib.sha256(content).hexdigest()))

    def test_image_still_syncs(self):
        content = b"image fixture"
        self.command.return_value = self.result(output=content)
        self.assertEqual(self.read(), ("image", content, hashlib.sha256(content).hexdigest()))
        self.command.assert_called_once()

    def test_empty_clipboard_still_has_a_baseline(self):
        self.command.return_value = self.result(1)
        self.assertEqual(self.read(), ("empty", b"", hashlib.sha256(b"").hexdigest()))

    def test_data_control_compositor_can_use_wayland(self):
        self.namespace["surface_required"].return_value = False
        self.command.side_effect = [
            self.result(output=b"text/plain\n"), self.result(output=b"text"),
        ]
        self.assertEqual(self.read()[0:2], ("text", b"text"))
        self.assertEqual(self.command.call_args_list[0].args[0], ["wl-paste", "--list-types"])


if __name__ == "__main__":
    unittest.main()
