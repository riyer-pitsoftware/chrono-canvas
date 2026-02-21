import time

import typer
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from chronocanvas_cli.client import ChronoCanvasClient
from chronocanvas_cli.output import print_generation

app = typer.Typer(help="Generate historical portraits")
console = Console()


@app.callback(invoke_without_command=True)
def generate(
    text: str = typer.Argument(help="Description of the historical figure"),
    figure_id: str | None = typer.Option(None, help="Existing figure ID"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for completion"),
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Generate a historical portrait from a text description."""
    client = ChronoCanvasClient(base_url)
    result = client.generate(text, figure_id)
    request_id = result["id"]

    console.print(f"[green]Generation started![/green] Request ID: {request_id}")

    if wait:
        with Live(Spinner("dots", text="Processing..."), console=console):
            while True:
                status = client.get_generation(request_id)
                if status["status"] in ("completed", "failed"):
                    break
                time.sleep(2)

        print_generation(status)
        if status["status"] == "completed":
            console.print("[green]Generation completed successfully![/green]")
        else:
            console.print(f"[red]Generation failed: {status.get('error_message', 'Unknown error')}[/red]")
    else:
        console.print("Use [cyan]chronocanvas status {request_id}[/cyan] to check progress")
