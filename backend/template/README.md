# Google ADK Multi-Agent Boilerplate & Starter Kit

A production-ready, modular multi-agent starter kit built with the **Google Agent Development Kit (ADK)** and the official `google-genai` SDK.

---

## 🏛️ System Architecture

```text
my-adk-agent/
│
├── agents/                      # Specialized Sub-Agents (each in its own module)
│   ├── agent1/                  # Research Specialist (Search & Knowledge Retrieval)
│   │   ├── agent.py             # Agent definition & Gemini configuration
│   │   ├── prompt.py            # System instructions & persona prompt
│   │   └── tools.py             # Domain-specific tool functions
│   ├── agent2/                  # Code Analyst & Engineer (Sandbox & Syntax)
│   ├── agent3/                  # Data & Math Analyst (Calculations & Metrics)
│   ├── agent4/                  # Synthesis & Writer (Markdown Reports & Summaries)
│   └── agent5/                  # Critic & Verifier (Quality Assurance & Fact-Check)
│
├── agent.py                     # ROOT ORCHESTRATOR: Dynamic routing & multi-agent pipeline
├── settings.yaml                # Global config: Models, temperatures, agent toggles
├── requirements.txt             # Python dependencies
├── fast_api.py                  # FastAPI REST server (/chat, /run, /agents)
├── frontend.py                  # Streamlit Web UI for interactive exploration
├── app.py                       # CLI & Unified runner (--mode cli|api|ui|test)
├── .env.example                 # Environment variable template
├── .gitignore                   # Standard Python gitignore
└── README.md                    # Documentation & Customization Guide
```

---

## 🚀 Quick Start in 3 Steps

### Step 1: Clone & Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
cp .env.example .env
# Add GOOGLE_API_KEY="your_key"
```

### Step 3: Run the Application
- **CLI Chat**: `python app.py --mode cli`
- **Streamlit Web UI**: `python app.py --mode ui`
- **FastAPI REST Server**: `python app.py --mode api`
- **Self-Test Diagnostics**: `python app.py --mode test`

---

## 🛠️ How to Add a Custom Agent in 3 Steps
1. Create folder: `mkdir -p agents/agent6 && touch agents/agent6/{prompt.py,tools.py,agent.py}`
2. Define instructions in `prompt.py`, tools in `tools.py`, and class in `agent.py`.
3. Register in `settings.yaml` and import into `agent.py`.