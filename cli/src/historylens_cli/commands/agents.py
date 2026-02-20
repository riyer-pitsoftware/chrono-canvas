import typer
from rich.console import Console
from rich.table import Table

from historylens_cli.client import HistoryLensClient
from historylens_cli.output import print_agents

app = typer.Typer(help="Agent operations")
console = Console()


@app.command("list")
def list_agents(
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """List all available agents."""
    client = HistoryLensClient(base_url)
    result = client.list_agents()
    print_agents(result)


@app.command("llm-status")
def llm_status(
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Check LLM provider availability."""
    client = HistoryLensClient(base_url)
    result = client.llm_status()

    table = Table(title="LLM Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Available")

    for name, available in result["providers"].items():
        status = "[green]Yes[/green]" if available else "[red]No[/red]"
        table.add_row(name, status)

    console.print(table)


@app.command("costs")
def costs(
    base_url: str = typer.Option("http://localhost:8000/api", envvar="HISTORYLENS_API_URL"),
):
    """Show LLM cost summary."""
    client = HistoryLensClient(base_url)
    result = client.cost_summary()

    console.print(f"\nTotal Cost: ${result['total_cost']:.6f}")
    console.print(f"Total Tokens: {result['total_tokens']:,}")
    console.print(f"Total Calls: {result['num_calls']}")

    if result["by_provider"]:
        table = Table(title="Cost by Provider")
        table.add_column("Provider")
        table.add_column("Cost")
        for provider, cost in result["by_provider"].items():
            table.add_row(provider, f"${cost:.6f}")
        console.print(table)
