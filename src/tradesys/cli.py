"""Punto de entrada de la línea de comandos `tradesys`."""

import typer

from tradesys import __version__

app = typer.Typer(help="Sistema de trading MEXC + TradingView.", no_args_is_help=True)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"tradesys {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version, is_eager=True, help="Muestra la versión."
    ),
) -> None:
    """Sistema de trading MEXC + TradingView."""
