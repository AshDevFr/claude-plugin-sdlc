"""Shared test scaffolding: no test may reach the network, and CLI runs go through one helper."""

import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOL_DIR = Path(__file__).resolve().parent.parent
SHIM = TOOL_DIR / "specs"
BOOTSTRAP = Path(__file__).resolve().parent / "_bootstrap.py"


class NetworkBlocked(AssertionError):
    pass


def _refuse(*_args, **_kwargs):
    raise NetworkBlocked("tests must not open network sockets")


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        _refuse()


def install_socket_guard():
    """Make any socket creation in this process raise. Used by the CLI bootstrap."""
    socket.socket = _BlockedSocket
    socket.create_connection = _refuse


class OfflineTestCase(unittest.TestCase):
    """Base class for every test: creating a socket fails the test loudly."""

    def setUp(self):
        super().setUp()
        for target, replacement in (
            ("socket.socket", _BlockedSocket),
            ("socket.create_connection", _refuse),
        ):
            patcher = mock.patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, *args, cwd=None, env=None):
        """Run the CLI in a subprocess with the socket guard and the test-only commands installed."""
        return self._run([sys.executable, str(BOOTSTRAP), *args], cwd=cwd, env=env)

    def run_shim(self, *args, cwd=None, env=None):
        """Run the real entry shim, exactly as the pipeline and the plugin do."""
        return self._run([sys.executable, str(SHIM), *args], cwd=cwd, env=env)

    @staticmethod
    def _run(argv, cwd, env):
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        return subprocess.run(argv, cwd=cwd, env=full_env, capture_output=True, text=True)
