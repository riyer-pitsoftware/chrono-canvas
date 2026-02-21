from pathlib import Path

import typer
from rich.console import Console

from chronocanvas_cli.client import ChronoCanvasClient

app = typer.Typer(help="Download generated images")
console = Console()


@app.callback(invoke_without_command=True)
def download(
    request_id: str = typer.Argument(help="Generation request ID"),
    output: str = typer.Option(".", "--output", "-o", help="Output directory"),
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Download the generated image for a request."""
    client = ChronoCanvasClient(base_url)
    image_data = client.download_image(request_id)

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    filepath = out_dir / f"{request_id}.png"
    filepath.write_bytes(image_data)

    console.print(f"[green]Image saved to {filepath}[/green]")
