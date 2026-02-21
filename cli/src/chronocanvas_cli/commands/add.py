import typer
from rich.console import Console

from chronocanvas_cli.client import ChronoCanvasClient
from chronocanvas_cli.output import print_figure

app = typer.Typer(help="Add historical figures")
console = Console()


@app.command()
def figure(
    name: str = typer.Argument(help="Name of the historical figure"),
    birth_year: int | None = typer.Option(None, help="Birth year"),
    death_year: int | None = typer.Option(None, help="Death year"),
    nationality: str | None = typer.Option(None, help="Nationality"),
    occupation: str | None = typer.Option(None, help="Occupation"),
    description: str | None = typer.Option(None, help="Description"),
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Add a historical figure to the database."""
    client = ChronoCanvasClient(base_url)
    data = {"name": name}
    if birth_year:
        data["birth_year"] = birth_year
    if death_year:
        data["death_year"] = death_year
    if nationality:
        data["nationality"] = nationality
    if occupation:
        data["occupation"] = occupation
    if description:
        data["description"] = description

    result = client.create_figure(data)
    console.print("[green]Figure created successfully![/green]")
    print_figure(result)
