from rich.console import Console
from rich.table import Table

console = Console()


def print_figure(figure: dict) -> None:
    table = Table(title=f"Figure: {figure['name']}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    for key in ["id", "name", "birth_year", "death_year", "nationality", "occupation", "description"]:
        val = figure.get(key)
        if val is not None:
            table.add_row(key, str(val))

    console.print(table)


def print_figures_list(data: dict) -> None:
    table = Table(title=f"Figures ({data['total']} total)")
    table.add_column("Name", style="cyan")
    table.add_column("Period")
    table.add_column("Nationality")
    table.add_column("Occupation")

    for f in data["items"]:
        table.add_row(
            f["name"],
            f"{f.get('birth_year', '?')}-{f.get('death_year', '?')}",
            f.get("nationality", ""),
            f.get("occupation", ""),
        )

    console.print(table)


def print_generation(gen: dict) -> None:
    table = Table(title="Generation Request")
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("ID", gen["id"])
    table.add_row("Status", gen["status"])
    table.add_row("Input", gen["input_text"][:80])
    if gen.get("current_agent"):
        table.add_row("Current Agent", gen["current_agent"])
    if gen.get("generated_prompt"):
        table.add_row("Prompt", gen["generated_prompt"][:100] + "...")
    if gen.get("error_message"):
        table.add_row("Error", gen["error_message"])

    console.print(table)


def print_agents(data: dict) -> None:
    table = Table(title="Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Status", style="green")

    for agent in data["agents"]:
        table.add_row(agent["name"], agent["description"], agent["status"])

    console.print(table)
