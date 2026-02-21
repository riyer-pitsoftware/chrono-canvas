import typer
from rich.console import Console

from chronocanvas_cli.client import ChronoCanvasClient
from chronocanvas_cli.output import print_generation

app = typer.Typer(help="Check generation status")
console = Console()


@app.callback(invoke_without_command=True)
def status(
    request_id: str = typer.Argument(help="Generation request ID"),
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Check the status of a generation request."""
    client = ChronoCanvasClient(base_url)
    result = client.get_generation(request_id)
    print_generation(result)
