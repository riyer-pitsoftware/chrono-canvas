import json

import typer
from rich.console import Console

from chronocanvas_cli.client import ChronoCanvasClient

app = typer.Typer(help="Batch generation operations")
console = Console()


@app.callback(invoke_without_command=True)
def batch(
    file: str = typer.Argument(help="JSON file with generation items"),
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Run batch generation from a JSON file."""
    with open(file) as f:
        items = json.load(f)

    if not isinstance(items, list):
        items = [items]

    client = ChronoCanvasClient(base_url)
    result = client.batch_generate([{"input_text": item} if isinstance(item, str) else item for item in items])

    console.print(f"[green]Batch started![/green] {result['total']} requests created")
    for rid in result["request_ids"]:
        console.print(f"  - {rid}")
