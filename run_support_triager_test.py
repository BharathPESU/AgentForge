"""Test runner script for Customer Support Triage multi-agent system in AgentForge."""

import os
import json
import time
from backend.agents.root_agent import RootAgent
from backend.roundRobin import set_gemini_api_key_env

def run_test():
    print("=" * 70)
    print("AGENTFORGE COMPILER TEAM TEST RUNNER")
    print("Target Prompt: Build a Customer Support Triage system with specialized sub-agents for intent classification, sentiment analysis, and escalation routing.")
    print("Project Directory: generated/support_triager")
    print("=" * 70)

    user_idea = (
        "Build a Customer Support Triage system with specialized sub-agents "
        "for intent classification, sentiment analysis, and escalation routing."
    )
    project_path = "generated/support_triager"

    start_time = time.time()
    orchestrator = RootAgent()

    res = orchestrator.run_pipeline(
        user_idea=user_idea,
        project_path=project_path
    )

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 70)
    print(f"PIPELINE EXECUTION COMPLETE IN {elapsed}s")
    print(f"Status: {res.get('status')}")
    print("=" * 70)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    run_test()
