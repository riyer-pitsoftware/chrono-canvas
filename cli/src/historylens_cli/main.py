import typer

from historylens_cli.commands import add, agents, batch, download, generate, list_cmd, status, validate

app = typer.Typer(
    name="historylens",
    help="HistoryLens CLI - Generate historically accurate portraits",
    no_args_is_help=True,
)

app.add_typer(add.app, name="add")
app.add_typer(generate.app, name="generate")
app.add_typer(batch.app, name="batch")
app.add_typer(status.app, name="status")
app.add_typer(download.app, name="download")
app.add_typer(list_cmd.app, name="list")
app.add_typer(validate.app, name="validate")
app.add_typer(agents.app, name="agents")


@app.command()
def health(
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Check API health."""
    from rich.console import Console

    from historylens_cli.client import HistoryLensClient

    console = Console()
    client = HistoryLensClient(base_url)
    try:
        result = client.health()
        console.print(f"[green]API is healthy: {result}[/green]")
    except Exception as e:
        console.print(f"[red]API is unreachable: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
