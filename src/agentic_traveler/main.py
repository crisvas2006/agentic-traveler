import click
from agentic_traveler.travel_agent import TravelAgent

@click.command()
@click.option('--budget', prompt='What is your budget?', help='Your budget (e.g., low, medium, high)')
@click.option('--climate', prompt='Preferred climate?', help='Preferred climate (e.g., warm, cold, tropical)')
@click.option('--activity', prompt='Preferred activity?', help='Preferred activity (e.g., hiking, beach, city)')
@click.option('--duration', prompt='Duration of trip?', help='Duration (e.g., 1 week, weekend)')
def main(budget, climate, activity, duration):
    """
    Simple CLI for the Agentic Traveler.
    """
    click.echo(f"Generating travel idea for: Budget={budget}, Climate={climate}, Activity={activity}, Duration={duration}...")
    
    try:
        agent = TravelAgent()
        idea = agent.generate_travel_idea({
            "budget": budget,
            "climate": climate,
            "activity": activity,
            "duration": duration
        })
        click.echo("\n--- Travel Idea ---\n")
        click.echo(idea)
        click.echo("\n-------------------\n")
    except ValueError as e:
        click.echo(f"Error: {e}")
        click.echo("Please ensure GOOGLE_API_KEY is set in your environment or .env file.")
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    main()
