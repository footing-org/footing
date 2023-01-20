"""Main CLI"""

import argparse
import importlib
import os
import sys

import footing.config


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
    obj_parser = subparsers.add_parser(obj.name)
    obj_subparsers = obj_parser.add_subparsers(dest="subcommand", required=True)
    obj_subparsers.add_parser("build")
    obj_subparsers.add_parser("run")


def add_all_parsers(subparsers):
    add_self_parser(subparsers)
    add_shell_parser(subparsers)

    for obj in footing.config.registry().values():
        add_obj_parser(subparsers, obj)


def main():
    """Main entrypoint for the CLI"""
    parser = argparse.ArgumentParser(
        prog="footing",
        description="Package anything, install it anywhere",
    )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    command = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            command = arg
            break

    match command:
        case "self":
            add_self_parser(subparsers)
        case "shell":
            add_shell_parser(subparsers)
        case command if command in footing.config.registry():
            add_obj_parser(subparsers, footing.config.obj(command))
        case other:
            add_all_parsers(subparsers)

    kwargs = vars(parser.parse_args())
    command = kwargs.pop("command")
    subcommand = kwargs.pop("subcommand", "main")

    if command in ("self", "shell"):
        footing_module = importlib.import_module(f"footing.{command}")
        getattr(footing_module, subcommand)(**kwargs)
    else:
        getattr(footing.config.obj(command), subcommand)()
