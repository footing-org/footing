"""Main CLI"""

import argparse
import importlib
import os


def main():
    """Main entrypoint for the CLI"""
    parser = argparse.ArgumentParser(
        prog="footing",
        description="Package anything, install it anywhere",
    )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Footing install
    install_parser = subparsers.add_parser("install")

    # Footing self
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

    # Footing shell
    shell_parser = subparsers.add_parser("shell")
    shell_subparsers = shell_parser.add_subparsers(dest="subcommand", required=True)
    shell_init_parser = shell_subparsers.add_parser("init")
    shell_init_parser.add_argument("-s", "--shell")

    kwargs = vars(parser.parse_args())
    command = kwargs.pop("command")
    subcommand = kwargs.pop("subcommand", "main")

    footing_module = importlib.import_module(f"footing.{command}")
    getattr(footing_module, subcommand)(**kwargs)
