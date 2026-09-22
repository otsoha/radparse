import typer

from radparse.parser import parse_and_write


def main_cli():
    """Main entry point for the command-line interface."""
    typer.run(parse_and_write)
