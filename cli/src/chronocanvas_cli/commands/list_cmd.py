import typer
from rich.console import Console

from chronocanvas_cli.client import ChronoCanvasClient
from chronocanvas_cli.output import print_figures_list

app = typer.Typer(help="List resources")
console = Console()


@app.command("figures")
def list_figures(
    search: str | None = typer.Option(None, "--search", "-s", help="Search by name"),
    limit: int = typer.Option(50, "--limit", "-l"),
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """List historical figures."""
    client = ChronoCanvasClient(base_url)
    result = client.list_figures(search=search, limit=limit)
    print_figures_list(result)


@app.command("generations")
def list_generations(
    limit: int = typer.Option(20, "--limit", "-l"),
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """List generation requests."""
    from chronocanvas_cli.output import print_generation

    client = ChronoCanvasClient(base_url)
    result = client.list_generations(limit=limit)

    for gen in result["items"]:
        print_generation(gen)
        console.print()
