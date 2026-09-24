"""Command line entry point: subcommand registry, global flags, exit code mapping."""

import argparse
import functools
import importlib
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import load_config
from .errors import EXIT_OK, EXIT_USAGE, SpecsError, UsageError
from .output import Output

VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"

# Modules that register subcommands when imported.
_BUILTIN_COMMAND_MODULES: tuple[str, ...] = (
    "sdlc_specs.lint",
    "sdlc_specs.new",
    "sdlc_specs.intent",
    "sdlc_specs.coverage",
    "sdlc_specs.status",
    "sdlc_specs.init",
)


@dataclass
class Result:
    """What a subcommand hands back. `data` becomes the JSON document alongside `ok`."""

    exit_code: int = EXIT_OK
    data: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[argparse.Namespace, Output], "Result | None"]


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    handler: Handler
    configure: Callable[[argparse.ArgumentParser], None] | None = None
    needs_config: bool = False


COMMANDS: dict[str, Command] = {}


def command(
    name: str,
    help: str,
    configure: Callable[[argparse.ArgumentParser], None] | None = None,
    needs_config: bool = False,
):
    """Register a subcommand.

    `configure` adds its arguments to the subparser. With `needs_config`, the repo config is
    loaded before the handler runs and set as `args.config`, with the repo root as `args.repo_root`.
    """

    def register(handler: Handler) -> Handler:
        COMMANDS[name] = Command(name, help, handler, configure, needs_config)
        return handler

    return register


class _Parser(argparse.ArgumentParser):
    """argparse that raises instead of exiting, so JSON mode can still emit its document."""

    def __init__(self, *args, json_mode: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._json_mode = json_mode

    def error(self, message: str):
        raise UsageError(message, usage=self.format_usage())

    def print_help(self, file=None):
        super().print_help(sys.stderr if self._json_mode else file)


def _global_flags(parser: argparse.ArgumentParser, default: Any) -> None:
    parser.add_argument(
        "--json", action="store_true", default=default, help="print one JSON document on stdout"
    )
    parser.add_argument(
        "--verbose", action="store_true", default=default, help="show tracebacks on internal errors"
    )


def _build_parser(json_mode: bool) -> _Parser:
    parser = _Parser(prog="specs", description="Spec checks for the sdlc workflow.", json_mode=json_mode)
    parser.add_argument("--version", action="store_true", help="print the tool version and exit")
    _global_flags(parser, default=False)

    # The flags are accepted after the subcommand too; SUPPRESS keeps a subparser from
    # overwriting a value given before the subcommand name.
    common = argparse.ArgumentParser(add_help=False)
    _global_flags(common, default=argparse.SUPPRESS)

    sub = parser.add_subparsers(
        dest="command",
        metavar="<command>",
        parser_class=functools.partial(_Parser, json_mode=json_mode),
    )
    for cmd in sorted(COMMANDS.values(), key=lambda c: c.name):
        sp = sub.add_parser(cmd.name, help=cmd.help, parents=[common])
        if cmd.configure:
            cmd.configure(sp)
    return parser


def _load_builtin_commands() -> None:
    for module in _BUILTIN_COMMAND_MODULES:
        importlib.import_module(module)


def _flag_given(argv: list[str], flag: str) -> bool:
    # Decided before parsing, because a parse failure still has to honour --json.
    options = argv[: argv.index("--")] if "--" in argv else argv
    return flag in options


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Output(json_mode=_flag_given(argv, "--json"))
    verbose = _flag_given(argv, "--verbose")

    try:
        _load_builtin_commands()
        parser = _build_parser(out.json_mode)
        args = parser.parse_args(argv)

        if args.version:
            version = read_version()
            if out.json_mode:
                out.emit_document({"ok": True, "version": version})
            else:
                out.print(version)
            return EXIT_OK
        if args.command is None:
            raise UsageError("a subcommand is required", usage=parser.format_usage())

        cmd = COMMANDS[args.command]
        if cmd.needs_config:
            args.repo_root, args.config = load_config(Path.cwd())
        result = cmd.handler(args, out) or Result()
        out.emit_document({"ok": result.exit_code == EXIT_OK, **result.data})
        return result.exit_code

    except SystemExit as exc:
        # Only --help reaches here: the parser raises UsageError for every usage mistake.
        code = exc.code if isinstance(exc.code, int) else EXIT_OK
        if code == EXIT_OK:
            out.emit_document({"ok": True})
        return code

    except SpecsError as exc:
        if isinstance(exc, UsageError) and exc.usage:
            out.warn(exc.usage.rstrip())
        out.warn(f"specs: error: {exc.message}")
        out.emit_error(exc.exit_code, exc.message)
        return exc.exit_code

    except Exception as exc:
        if verbose:
            out.warn(traceback.format_exc().rstrip())
        message = f"{type(exc).__name__}: {exc}"
        out.warn(f"specs: internal error: {message}")
        out.emit_error(EXIT_USAGE, message)
        return EXIT_USAGE
