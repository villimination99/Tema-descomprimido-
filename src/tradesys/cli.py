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


secrets_app = typer.Typer(help="Gestiona secretos en el Llavero.", no_args_is_help=True)
app.add_typer(secrets_app, name="secrets")


@secrets_app.command("set")
def secrets_set(name: str = typer.Argument(..., help="Nombre del secreto")) -> None:
    """Guarda un secreto en el Llavero (la entrada no se muestra)."""
    from tradesys.infra.secrets import ALLOWED, set_secret

    if name not in ALLOWED:
        typer.echo(f"Secreto desconocido. Permitidos: {', '.join(sorted(ALLOWED))}", err=True)
        raise typer.Exit(2)
    value = typer.prompt(f"Valor de {name}", hide_input=True)
    set_secret(name, value)
    typer.echo(f"{name} guardado en el Llavero.")


@app.command()
def doctor(offline: bool = typer.Option(False, "--offline", help="Sin consultas de red.")) -> None:
    """Comprueba que el entorno está listo."""
    from tradesys.infra.doctor import run_checks

    results = run_checks(offline=offline)
    for r in results:
        typer.echo(f"{'OK ' if r.ok else 'MAL'}  {r.name:<9} {r.detail}")
    if not all(r.ok for r in results):
        raise typer.Exit(1)


mexc_app = typer.Typer(help="Herramientas de MEXC.", no_args_is_help=True)
app.add_typer(mexc_app, name="mexc")


@mexc_app.command("probe")
def mexc_probe(
    private: bool = typer.Option(False, "--private", help="Usa tus claves (solo lectura)."),
    order: str | None = typer.Option(
        None, "--order", help="spot o swap: crea y cancela una orden mínima de prueba."
    ),
) -> None:
    """Comprueba qué permite de verdad tu cuenta de MEXC y guarda reports/mexc_capabilities.json."""
    from pathlib import Path

    from tradesys.exchange.probe import (
        make_exchange,
        probe_order,
        probe_private,
        probe_public,
        write_report,
    )

    report: dict = {}
    for market in ("spot", "swap"):
        ex = make_exchange(market, auth=private or order is not None)
        report[market] = {"public": probe_public(ex)}
        if private:
            report[market]["private"] = probe_private(ex)
        if order == market:
            symbol = "BTC/USDT" if market == "spot" else "BTC/USDT:USDT"
            typer.echo(f"Se creará y cancelará una orden mínima post-only en {symbol}.")
            confirm = typer.prompt("Escribe SI (en mayúsculas) para continuar")
            report[market]["order_test"] = probe_order(ex, symbol, confirm)
    path = Path("reports/mexc_capabilities.json")
    write_report(report, path)
    typer.echo(f"Informe guardado en {path}")
