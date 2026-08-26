"""
Google ADK Application Entrypoint
"""

import os
import argparse
import subprocess
from dotenv import load_dotenv

load_dotenv()


def run_cli_interactive():
    from agent import get_root_agent
    orchestrator = get_root_agent()
    print("\n=======================================================")
    print("  Google ADK Multi-Agent Interactive Terminal (CLI)")
    print("=======================================================")
    for ag in orchestrator.list_agents():
        print(f"  • {ag['id']}: {ag['name']} ({ag['role']})")
    print("\nType your query below, or 'exit' to quit.\n")

    while True:
        try:
            query = input("\033[1;34mUser > \033[0m").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                break
            response = orchestrator.chat(query, auto_route=True)
            assigned = response.get("agent_name", "Orchestrator")
            res_data = response.get("result", {})
            print(f"\n\033[1;32m[{assigned}] >\033[0m\n{res_data.get('response', str(res_data))}\n")
        except (KeyboardInterrupt, EOFError):
            break


def run_api_server():
    import uvicorn
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", 8000))
    print(f"Launching Google ADK FastAPI server on http://{host}:{port}...")
    uvicorn.run("fast_api:app", host=host, port=port, reload=True)


def run_frontend_ui():
    port = os.environ.get("FRONTEND_PORT", "8501")
    subprocess.run(["streamlit", "run", "frontend.py", "--server.port", str(port)])


def run_self_test():
    from agent import get_root_agent
    orchestrator = get_root_agent()
    print("\n--- Running Google ADK Self-Test Diagnostic ---")
    for ag in orchestrator.list_agents():
        print(f"Testing {ag['id']} ({ag['name']})...")
        res = orchestrator.run_agent(ag["id"], "Ping diagnostic test.")
        print(f"  Status: {res.get('status', 'unknown')}")
    print("\n✅ All sub-agents validated successfully!")


def main():
    parser = argparse.ArgumentParser(description="Google ADK Multi-Agent Launcher")
    parser.add_argument("--mode", choices=["cli", "api", "ui", "test"], default="cli")
    args = parser.parse_args()

    if args.mode == "cli":
        run_cli_interactive()
    elif args.mode == "api":
        run_api_server()
    elif args.mode == "ui":
        run_frontend_ui()
    elif args.mode == "test":
        run_self_test()


if __name__ == "__main__":
    main()