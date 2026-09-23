"""Entry point for subprocess CLI tests.

Installs the socket guard and registers test-only subcommands, then runs the real CLI, so the
shipped code carries no test hooks.
"""

import socket
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent))

from sdlc_specs import cli  # noqa: E402
from sdlc_specs.errors import CheckFailed  # noqa: E402

from tests.base import install_socket_guard  # noqa: E402


@cli.command("_test-ok", help="test only: succeed with a payload")
def _ok(args, out):
    out.print("human text for the ok command")
    return cli.Result(data={"answer": 42})


@cli.command("_test-findings", help="test only: finish with exit 1 and a payload")
def _findings(args, out):
    out.print("one finding")
    return cli.Result(exit_code=1, data={"findings": ["f1"]})


@cli.command("_test-fail", help="test only: raise CheckFailed")
def _fail(args, out):
    raise CheckFailed("the check failed")


@cli.command("_test-crash", help="test only: raise an unexpected exception")
def _crash(args, out):
    raise RuntimeError("boom")


@cli.command("_test-config", help="test only: load the repo config", needs_config=True)
def _config(args, out):
    return cli.Result(data={"tracker": args.config.tracker_system})


@cli.command("_test-net", help="test only: try to open a socket")
def _net(args, out):
    socket.create_connection(("example.com", 80))
    return cli.Result()


if __name__ == "__main__":
    install_socket_guard()
    sys.exit(cli.main(sys.argv[1:]))
