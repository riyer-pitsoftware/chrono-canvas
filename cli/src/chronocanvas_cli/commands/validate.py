import typer
from rich.console import Console
from rich.table import Table

from chronocanvas_cli.client import ChronoCanvasClient

app = typer.Typer(help="Validation operations")
console = Console()


@app.callback(invoke_without_command=True)
def validate(
    request_id: str = typer.Argument(help="Generation request ID"),
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Show validation results for a generation request."""
    client = ChronoCanvasClient(base_url)
    result = client.get_validation(request_id)

    console.print(f"\nOverall Score: [{'green' if result['passed'] else 'red'}]{result['overall_score']:.1f}[/]")
    console.print(f"Passed: {'Yes' if result['passed'] else 'No'}\n")

    if result["results"]:
        table = Table(title="Validation Results")
        table.add_column("Category")
        table.add_column("Rule")
        table.add_column("Score")
        table.add_column("Passed")
        table.add_column("Details")

        for r in result["results"]:
            table.add_row(
                r["category"],
                r["rule_name"],
                f"{r['score']:.1f}",
                "Yes" if r["passed"] else "No",
                r.get("details", "")[:60],
            )

        console.print(table)
