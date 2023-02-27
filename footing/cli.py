"""Main CLI"""

import argparse
import importlib
import os
import subprocess
import sys
import traceback

import footing.config as footing_config
import footing.ctx as footing_ctx


UNSET = object()
CORE_CMDS = ["shell", "self"]


def style(msg, *, color=None, weight=UNSET, icon=True):
    weight = "bold" if weight is UNSET else weight

    match color:
        case "green":
            msg = f"\u001b[32m{msg}\u001b[0m"
        case "red":
            msg = f"\u001b[31m{msg}\u001b[0m"
        case other if other is not None:
            raise ValueError(f"Invalid color - {other}")

    match weight:
        case "bold":
            msg = f"\033[1m{msg}\033[0m"
        case other if other is not None:
            raise ValueError(f"Invalid weight - {other}")

    if icon:
        msg = "🐐 " + msg

    return msg


def pprint(msg, *, color=None, weight=UNSET, icon=True):
    msg = style(msg, color=color, weight=weight, icon=icon)

    print(msg)


def confirm_prompt(question: str, default: str = None, color: str = None) -> bool:
    if color:
        question = style(question, color=color)

    if default is None:
        choices = "[y/n]"
    elif default == "y":
        choices = "[Y/n]"
    elif default == "n":
        choices = "[y/N]"
    else:
        raise ValueError("Invalid default value")

    reply = None
    while reply not in ("y", "n"):
        reply = input(f"{question} {choices}: ").casefold() or default

    return reply == "y"


def add_self_parser(parser, subparsers=None):
    subparsers = subparsers or parser.add_subparsers(dest="command", required=True)

    self_parser = subparsers.add_parser("self")
    self_subparsers = self_parser.add_subparsers(dest="subcommand", required=True)
    self_init_parser = self_subparsers.add_parser("init")
    self_init_parser.add_argument(
        "--no-system", default="FOOTING_SELF_INIT_NO_SYSTEM" in os.environ, action="store_true"
    )
    self_init_parser.add_argument(
        "--no-shell-integration",
        default="FOOTING_SELF_INIT_NO_SHELL_INTEGRATION" in os.environ,
        action="store_true",
    )
    self_init_parser.add_argument(
        "--no-prompt", default="FOOTING_SELF_INIT_NO_PROMPT" in os.environ, action="store_true"
    )


def add_shell_parser(parser, subparsers=None):
    subparsers = subparsers or parser.add_subparsers(dest="command", required=True)

    shell_parser = subparsers.add_parser("shell")
    shell_subparsers = shell_parser.add_subparsers(dest="subcommand", required=True)
    shell_init_parser = shell_subparsers.add_parser("init")
    shell_init_parser.add_argument("-s", "--shell")


def add_core_parser(command, parser):
    match command:
        case "self":
            add_self_parser(parser)
        case "shell":
            add_shell_parser(parser)
        case _:
            raise AssertionError


def add_op_parser(name, parser, subparsers=None):
    subparsers = subparsers or parser.add_subparsers(dest="command", required=True)

    obj_parser = subparsers.add_parser(name)
    obj_parser.add_subparsers(dest="subcommand", required=False)


def add_all_parsers(parser, subparsers=None):
    subparsers = subparsers or parser.add_subparsers(dest="command", required=True)

    add_self_parser(parser, subparsers)
    add_shell_parser(parser, subparsers)

    for name in footing_config.get().get("op", {}):
        add_op_parser(name, parser, subparsers)


def cli():
    """Main entrypoint for the CLI"""
    parser = argparse.ArgumentParser(
        prog="footing",
        description="Package anything, install it anywhere",
    )

    parser = argparse.ArgumentParser()
    # TODO: All footing arguments need to be prefixed with _footing
    # in order to not collide with other dynamic commands
    parser.add_argument("-d", "--debug", action="store_true", dest="_footing_ctx_debug")
    parser.add_argument("-f", "--no-cache", action="store_true", dest="_footing_ctx_no_cache")

    # Parse the main expression, which might be objects or a subcommand
    command = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            command = arg
            break

    # Construct a proper CLI parser based on the command or footing obj
    match command:
        case core if core in CORE_CMDS:
            add_core_parser(command, parser)
        case None:
            add_all_parsers(parser)
        case _:
            add_op_parser(command, parser)

    kwargs = vars(parser.parse_args())
    command = kwargs.pop("command")
    subcommand = kwargs.pop("subcommand", [])

    with footing_ctx.set(
        cache=not kwargs.pop("_footing_ctx_no_cache"),
        debug=kwargs.pop("_footing_ctx_debug"),
    ):
        try:
            if command in CORE_CMDS:
                footing_module = importlib.import_module(f"footing.{command}")
                getattr(footing_module, subcommand)(**kwargs)
            else:
                import footing.core  # We do this nested to make CLI invocations faster

                op = footing.core.Op.from_config(command)
                op.graph()
        except Exception as exc:
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                msg = exc.stderr.decode("utf8").strip()
            else:
                msg = str(exc)

            msg = msg or "An unexpected error occurred"

            pprint(msg, color="red")
            if footing_ctx.get().debug:
                print(traceback.format_exc().strip())

            sys.exit(1)
