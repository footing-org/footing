"""Main CLI"""

import argparse
import importlib


def main():
    """Main entrypoint for the CLI"""
    parser = argparse.ArgumentParser(
        prog="footing",
        description="Package anything, install it anywhere",
    )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser('install')

    self_parser = subparsers.add_parser('self')
    self_subparsers = self_parser.add_subparsers(dest="subcommand", required=True)
    self_init_parser = self_subparsers.add_parser('init')
    self_init_parser.add_argument("--system", action=argparse.BooleanOptionalAction)

    kwargs = vars(parser.parse_args())
    command = kwargs.pop("command")
    subcommand = kwargs.pop("subcommand", "main")

    footing_module = importlib.import_module(f"footing.{command}")
    getattr(footing_module, subcommand)(**kwargs)
