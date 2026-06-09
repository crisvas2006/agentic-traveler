import logging
from dotenv import load_dotenv
from agentic_traveler.orchestrator.planner_agent import PlannerAgent
from agentic_traveler.orchestrator.client_factory import get_client

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

def run_test():
    client = get_client()
    agent = PlannerAgent(client)
    res = agent.process_request(
        user_doc={"user_name": "Test"},
        message="are there any events this weekend in Campulung, Arges ?",
        conversation_context="",
        current_time="2026-06-09T10:00:00Z"
    )
    print("RESULT:", res)

if __name__ == "__main__":
    run_test()
