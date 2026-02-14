"""GeoFix CLI — command-line interface for geospatial data quality.

Usage::

    geofix analyze data.shp
    geofix analyze data.shp --auto-fix --output fixed.gpkg
    geofix chat
    geofix --version
"""

from __future__ import annotations

import sys

import click


@click.group(invoke_without_command=True)
@click.version_option(package_name="geofix")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """GeoFix — AI-powered geospatial data quality assistant."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--auto-fix", is_flag=True, help="Automatically fix invalid geometries.")
@click.option("-o", "--output", type=click.Path(), help="Save result to this file.")
@click.option(
    "--report",
    type=click.Choice(["md", "html"], case_sensitive=False),
    help="Generate a quality report.",
)
def analyze(file_path: str, auto_fix: bool, output: str | None, report: str | None) -> None:
    """Analyse a geospatial file for quality issues."""
    from geofix.api import analyze as _analyze

    click.echo(f"📊 Analysing {file_path}...")

    try:
        result = _analyze(file_path, auto_fix=auto_fix, output=output, report=report)
    except Exception as exc:
        click.secho(f"❌ Error: {exc}", fg="red")
        sys.exit(1)

    click.echo()
    click.echo(result.summary())

    if output:
        click.echo(f"\n💾 Saved to {output}")

    if report:
        click.echo("📄 Report generated")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def validate(file_path: str) -> None:
    """Validate a geospatial file (no fixing)."""
    from geofix.api import validate as _validate

    click.echo(f"🔍 Validating {file_path}...")
    result = _validate(file_path)
    click.echo()
    click.echo(result.summary())


@cli.command(name="fix")
@click.argument("file_path", type=click.Path(exists=True))
@click.argument("output", type=click.Path())
def fix_cmd(file_path: str, output: str) -> None:
    """Auto-fix and save corrected file."""
    from geofix.api import fix as _fix

    click.echo(f"🔧 Fixing {file_path}...")
    result = _fix(file_path, output)
    click.echo()
    click.echo(result.summary())
    click.echo(f"\n💾 Saved to {output}")


@cli.command()
def chat() -> None:
    """Launch the GeoFix chat interface."""
    import subprocess

    click.echo("🚀 Launching GeoFix chat...")
    subprocess.run(
        [sys.executable, "-m", "chainlit", "run", "geofix/chat/app.py"],
        check=True,
    )


if __name__ == "__main__":
    cli()
