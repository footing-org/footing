"""Main CLI"""

import argparse
import importlib
import os
import subprocess
import sys
import traceback

import footing.config
import footing.ctx


unset = object()


def style(msg, *, color=None, weight=unset, icon=True):
    weight = "bold" if weight is unset else weight

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


def pprint(msg, *, color=None, weight=unset, icon=True):
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


def add_self_parser(subparsers):
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


def add_shell_parser(subparsers):
    shell_parser = subparsers.add_parser("shell")
    shell_subparsers = shell_parser.add_subparsers(dest="subcommand", required=True)
    shell_init_parser = shell_subparsers.add_parser("init")
    shell_init_parser.add_argument("-s", "--shell")


def add_obj_parser(subparsers, obj):
    entry = obj.cli
    if not entry:
        return

    obj_parser = subparsers.add_parser(obj.name)
    obj_subparsers = obj_parser.add_subparsers(dest="subcommand", required="main" not in entry)
    for name, val in entry.items():
        obj_subparsers.add_parser(name)


def add_exe_parser(subparsers, obj, slash):
    entry = obj.cli
    if not entry or "/" not in entry:
        return

    obj_parser = subparsers.add_parser(f"{obj.name}/{slash}")
    obj_parser.add_argument("args", nargs=argparse.REMAINDER)


def add_all_parsers(subparsers):
    add_self_parser(subparsers)
    add_shell_parser(subparsers)

    for obj in footing.config.registry().values():
        add_obj_parser(subparsers, obj)


def call_obj_entry(command, subcommand, kwargs):
    """Loads objects and calls entry points"""
    entry = footing.config.obj(command).cli[subcommand]
    entry.method(**kwargs)


def get_obj(command):
    """
    Get a footing object based on the command name.

    Footing objects are only returned if they are registered
    and have entry points
    """
    try:
        if obj := footing.config.obj(command):
            if obj.cli:
                return obj
    except FileNotFoundError:
        return None


def main():
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
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Figure out which command was called and also keep track of the
    # position of the command relative to sys.argv. This is because
    # we will need to do some special parsing later for slash commands
    command = None
    command_i = 0
    for i, arg in enumerate(sys.argv[1:]):
        if not arg.startswith("-"):
            command = arg
            command_i = i + 1
            break

    # If a "/" is found after an object, this exposes a different
    # interface.
    exe = None
    slash = command is not None and "/" in command
    if slash:
        command, exe = command.split("/", 1)

    # We'll need to parse args slightly differently
    # to delegate to other executables when using slash notation
    args_to_parse = sys.argv[1:]
    if slash:
        args_to_parse = sys.argv[1 : command_i + 1]

    # Construct a proper CLI parser based on the command or footing obj
    # TODO: Don't try to load objects this early. Check for main commands
    # first before loading a config file
    obj = get_obj(command)
    match command:
        case "self":
            add_self_parser(subparsers)
        case "shell":
            add_shell_parser(subparsers)
        case command if obj and not slash:
            add_obj_parser(subparsers, obj)
        case command if obj and slash:
            add_exe_parser(subparsers, obj, exe)
        case other:
            add_all_parsers(subparsers)

    kwargs = vars(parser.parse_args(args_to_parse))
    kwargs.pop("command")
    subcommand = kwargs.pop("subcommand", "/" if slash else None) or "main"

    with footing.ctx.set(
        cache=not kwargs.pop("_footing_ctx_no_cache"), debug=kwargs.pop("_footing_ctx_debug")
    ):
        try:
            if command in ("self", "shell"):
                footing_module = importlib.import_module(f"footing.{command}")
                getattr(footing_module, subcommand)(**kwargs)
            elif slash:
                call_obj_entry(
                    command, subcommand, {"exe": exe, "args": sys.argv[command_i + 1 :]}
                )
            else:
                call_obj_entry(command, subcommand, kwargs)
        except Exception as exc:
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                msg = exc.stderr.decode("utf8").strip()
            else:
                msg = str(exc)

            msg = msg or "An unexpected error occurred"

            pprint(msg, color="red")
            if footing.ctx.get().debug:
                print(traceback.format_exc().strip())

            sys.exit(1)
