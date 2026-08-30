"""Coder Agent implementation for AgentForge using Google ADK and template baseline."""

import json
import os
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import google.adk as adk

from backend.tools.coder_tools import (
    copy_template,
    edit_file,
    inspect_generated_structure,
    list_directory,
    read_file,
    terminal_execute,
    validate_design,
    validate_plan,
    write_file,
)
from backend.tools.designer_tools import read_plan_json

from backend.roundRobin import set_gemini_api_key_env

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


PROMPT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "prompts", "coder_prompt.md"
)


def load_coder_instruction(prompt_path: Optional[str] = None) -> str:
    """Load the Coder Agent system instruction from markdown file."""
    path = prompt_path or PROMPT_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class CoderAgent:
    """Coder Agent responsible for transforming plan.json and design.json into
    working Google ADK Python application files by modifying the template.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        prompt_path: Optional[str] = None,
    ):
        self.model_name = model_name or DEFAULT_MODEL
        self.prompt_path = prompt_path
        self.instruction = load_coder_instruction(prompt_path)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> adk.Agent:
        """Instantiate Google ADK Agent with deterministic tools."""
        return adk.Agent(
            name="coder_agent",
            description="AgentForge Coder Agent for template-based code generation",
            model=self.model_name,
            instruction=self.instruction,
            tools=[
                copy_template,
                read_file,
                write_file,
                edit_file,
                list_directory,
                terminal_execute,
                validate_plan,
                validate_design,
                inspect_generated_structure,
            ],
        )

    def generate_code(
        self,
        project_path: str = "generated/project01",
        gemini_api_key: Optional[str] = None,
        override_llm_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate/update multi-agent application code based on plan.json and design.json.
        
        Args:
            project_path: Target directory path for generated project.
            gemini_api_key: Optional Gemini API key to configure in generated .env file.
            override_llm_response: Optional override string for testing.
            
        Returns:
            Dict containing handoff contract result.
        """
        # Step 1: Validate plan.json
        plan_res = read_plan_json(project_path)
        if not plan_res["valid"]:
            return {
                "status": "failed",
                "project_path": project_path,
                "reason": "missing_plan",
                "details": plan_res["errors"],
                "ready_for_testing": False,
            }

        # Step 2: Validate design.json
        design_res = validate_design(project_path)
        if not design_res["valid"]:
            return {
                "status": "failed",
                "project_path": project_path,
                "reason": "missing_design",
                "details": design_res["errors"],
                "ready_for_testing": False,
            }

        plan_data = plan_res["data"]
        design_data = design_res["data"]

        target_dir = os.path.abspath(project_path)
        files_created: List[str] = []
        files_modified: List[str] = []
        template_used = False

        # Step 3: Copy template baseline files (app.py, config.json, settings.yaml, static UI, vercel.json)
        agent_py_path = os.path.join(target_dir, "agent.py")
        copy_res = copy_template(target_dir, overwrite=False)
        if copy_res.get("status") == "success":
            template_used = True
            files_created.extend(copy_res.get("copied_files", []))

        # Step 4: Generate/update agent files for every agent in design.json
        agents = design_data.get("agents", [])
        agents_updated: List[str] = []

        for agent_spec in agents:
            agent_id = agent_spec["id"]
            agent_name = agent_spec.get("name", agent_id)
            agent_resp = agent_spec.get("responsibility", "Specialized Agent")
            sys_prompt = agent_spec.get("system_prompt", f"You are {agent_name}.")
            tools_spec = agent_spec.get("tools", [])
            model_spec = agent_spec.get("model", {})
            model_name = model_spec.get("model_name", "gemini-2.5-flash")
            temp = model_spec.get("temperature", 0.2)

            agent_dir = os.path.join(target_dir, "agents", agent_id)
            os.makedirs(agent_dir, exist_ok=True)

            # 4a. Write prompt.py
            prompt_file = os.path.join(agent_dir, "prompt.py")
            prompt_content = (
                '"""\n'
                f'System instructions and prompts for {agent_id}: {agent_name}.\n'
                '"""\n\n'
                f'AGENT_NAME = "{agent_name}"\n'
                f'AGENT_ROLE = "{agent_resp}"\n\n'
                f'SYSTEM_INSTRUCTION = """{sys_prompt}"""\n'
            )
            write_file(prompt_file, prompt_content)
            files_modified.append(os.path.relpath(prompt_file, target_dir))

            # 4b. Write tools.py
            tools_file = os.path.join(agent_dir, "tools.py")
            tools_content = self._generate_tools_code(agent_id, agent_name, tools_spec)
            write_file(tools_file, tools_content)
            files_modified.append(os.path.relpath(tools_file, target_dir))

            # 4c. Write agent.py
            class_name = "".join(x.title() for x in re.split(r"[^a-zA-Z0-9]", agent_id)) + "Agent"
            agent_file = os.path.join(agent_dir, "agent.py")
            agent_code = self._generate_agent_code(
                agent_id, agent_name, class_name, model_name, temp
            )
            write_file(agent_file, agent_code)
            files_modified.append(os.path.relpath(agent_file, target_dir))

            agents_updated.append(agent_id)

        # Step 5: Update Root Orchestrator (agent.py)
        root_agent_code = self._generate_root_orchestrator(plan_data, design_data)
        write_file(agent_py_path, root_agent_code)
        files_modified.append("agent.py")

        # Step 6: Update settings.yaml
        settings_file = os.path.join(target_dir, "settings.yaml")
        if os.path.isfile(settings_file):
            settings_code = self._generate_settings_yaml(plan_data, design_data)
            write_file(settings_file, settings_code)
            files_modified.append("settings.yaml")

        # Step 7: Update config.json with active design spec for app.py
        config_file = os.path.join(target_dir, "config.json")
        config_data = {
            "project": plan_data.get("project", design_data.get("project", {})),
            "agents": design_data.get("agents", []),
            "wiring": design_data.get("wiring", []),
        }
        write_file(config_file, json.dumps(config_data, indent=2))
        files_modified.append("config.json")

        # Step 8: Configure .env and .env.example with GEMINI_API_KEY
        api_key_val = (
            gemini_api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY", "")
        )
        env_file = os.path.join(target_dir, ".env")
        env_content = (
            "# AgentForge Generated Project Environment Configuration\n"
            f"GEMINI_API_KEY={api_key_val}\n"
            f"GOOGLE_API_KEY={api_key_val}\n"
            "GEMINI_MODEL=gemini-3.5-flash\n"
            "API_HOST=0.0.0.0\n"
            "API_PORT=8000\n"
        )
        write_file(env_file, env_content)
        files_modified.append(".env")

        env_example_file = os.path.join(target_dir, ".env.example")
        example_content = (
            env_content.replace(api_key_val, "your_gemini_api_key_here")
            if api_key_val
            else env_content
        )
        write_file(env_example_file, example_content)
        files_modified.append(".env.example")

        # Collect all actually-created/modified files for the handoff payload
        all_files_touched = sorted(list(set(files_created + files_modified)))

        return {
            "status": "success",
            "project_path": project_path,
            "template_used": template_used,
            "agents_updated": agents_updated,
            "files_created": all_files_touched,
            "files_modified": sorted(list(set(files_modified))),
            "ready_for_testing": True,
        }

    def _generate_tools_code(
        self, agent_id: str, agent_name: str, tools_spec: List[Dict[str, Any]]
    ) -> str:
        """Generate executable tools.py for an agent based on tool specifications."""
        lines = [
            '"""',
            f'Callable tools and function definitions for {agent_id}: {agent_name}.',
            '"""',
            '',
            'from typing import Dict, Any, List, Optional',
            '',
        ]

        tool_names = []
        if not tools_spec:
            lines.append('# No tools assigned for this agent')
            lines.append('TOOLS_LIST = []')
            lines.append('')
            return '\n'.join(lines)

        for tool in tools_spec:
            raw_name = tool.get("name", "custom_tool")
            from backend.tools.coder_tools import sanitize_tool_name
            t_name = sanitize_tool_name(raw_name)
            t_desc = tool.get("description", f"Tool {t_name}")
            t_purpose = tool.get("purpose", "")
            tool_names.append(t_name)

            lines.append(f'def {t_name}(query: str = "") -> Dict[str, Any]:')
            lines.append('    """')
            lines.append(f'    {t_desc}')
            if t_purpose:
                lines.append(f'    Purpose: {t_purpose}')
            lines.append('    """')
            lines.append('    return {')
            lines.append('        "status": "success",')
            lines.append(f'        "tool": "{t_name}",')
            lines.append(f'        "result": f"Executed {t_name} with query: \'{{query}}\'",')
            lines.append('    }')
            lines.append('')

        lines.append(f'TOOLS_LIST = [{", ".join(tool_names)}]')
        lines.append('')
        return '\n'.join(lines)

    def _generate_agent_code(
        self,
        agent_id: str,
        agent_name: str,
        class_name: str,
        model_name: str,
        temperature: float,
    ) -> str:
        """Generate individual agent.py implementation."""
        return f'''"""
Agent definition for {agent_id}: {agent_name}.
"""

import os
from typing import Dict, Any, List, Optional
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from .prompt import SYSTEM_INSTRUCTION, AGENT_NAME, AGENT_ROLE
from .tools import TOOLS_LIST


class {class_name}:
    """Specialized Agent implementation for {agent_name}."""

    def __init__(
        self,
        model_name: str = "{model_name}",
        temperature: float = {temperature},
        api_key: Optional[str] = None
    ):
        self.name = AGENT_NAME
        self.role = AGENT_ROLE
        self.model_name = model_name
        self.temperature = temperature
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if (self.api_key and GENAI_AVAILABLE) else None
        self.tools = TOOLS_LIST

    def get_system_instruction(self) -> str:
        return SYSTEM_INSTRUCTION

    def run(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the agent on a prompt."""
        if not self.client:
            return {{
                "agent": self.name,
                "role": self.role,
                "response": f"[MOCK {{self.name}}] Processed prompt: '{{prompt}}'",
                "status": "success"
            }}

        try:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=self.temperature,
                tools=self.tools if self.tools else None
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return {{
                "agent": self.name,
                "role": self.role,
                "response": response.text,
                "status": "success"
            }}
        except Exception as e:
            return {{
                "agent": self.name,
                "role": self.role,
                "error": str(e),
                "status": "error"
            }}


def get_agent(**kwargs) -> {class_name}:
    """Factory method to instantiate {agent_id}."""
    return {class_name}(**kwargs)
'''

    def _generate_root_orchestrator(
        self, plan_data: Dict[str, Any], design_data: Dict[str, Any]
    ) -> str:
        """Generate root agent.py orchestrator matching plan wiring."""
        agents = design_data.get("agents", [])
        root_agent = next((a for a in agents if a.get("id") == "agent1"), agents[0] if agents else {})
        root_id = root_agent.get("id", "agent1")

        imports = []
        inits = []

        for a in agents:
            aid = a["id"]
            imports.append(f"from agents.{aid}.agent import get_agent as get_{aid}")
            inits.append(f"""
        cfg_{aid} = agent_configs.get("{aid}", {{}})
        if cfg_{aid}.get("enabled", True):
            self.sub_agents["{aid}"] = get_{aid}(
                model_name=cfg_{aid}.get("model", "{a.get('model', {}).get('model_name', 'gemini-2.5-flash')}"),
                temperature=cfg_{aid}.get("temperature", {a.get('model', {}).get('temperature', 0.2)}),
                api_key=self.api_key
            )""")

        imports_str = "\n".join(imports)
        inits_str = "\n".join(inits)

        return f'''"""
Google ADK Root Orchestrator Agent
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

{imports_str}

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def load_settings() -> Dict[str, Any]:
    settings_path = Path(__file__).parent / "settings.yaml"
    if settings_path.exists():
        with open(settings_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {{}}


class RootOrchestrator:
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or load_settings()
        self.api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self.model_name = (
            self.settings.get("models", {{}}).get("default") or "gemini-2.5-flash"
        )
        self.client = genai.Client(api_key=self.api_key) if (self.api_key and GENAI_AVAILABLE) else None
        self.sub_agents: Dict[str, Any] = {{}}
        self._initialize_sub_agents()

    def _initialize_sub_agents(self):
        agent_configs = self.settings.get("agents", {{}})
{inits_str}

    def list_agents(self) -> List[Dict[str, Any]]:
        agent_list = []
        for key, agent in self.sub_agents.items():
            agent_list.append({{
                "id": key,
                "name": getattr(agent, "name", key),
                "role": getattr(agent, "role", "Specialist"),
                "model": getattr(agent, "model_name", "unknown"),
                "tools": [getattr(t, "__name__", str(t)) for t in getattr(agent, "tools", [])]
            }})
        return agent_list

    def route_query(self, user_query: str) -> str:
        return "{root_id}"

    def run_agent(self, agent_id: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if agent_id not in self.sub_agents:
            return {{
                "status": "error",
                "error": f"Agent '{{agent_id}}' is not registered or disabled.",
                "available_agents": list(self.sub_agents.keys())
            }}
        return self.sub_agents[agent_id].run(prompt, context=context)

    def run_pipeline(self, user_query: str) -> Dict[str, Any]:
        workflow_steps = []
        current_context = user_query
        last_response = ""

        for key, agent in self.sub_agents.items():
            out = agent.run(current_context)
            resp = out.get("response", "")
            last_response = resp
            current_context = f"Previous context: {{resp}}\\nOriginal query: {{user_query}}"
            workflow_steps.append({{
                "agent": key,
                "output": resp
            }})

        return {{
            "status": "success",
            "query": user_query,
            "final_response": last_response,
            "pipeline_steps": workflow_steps
        }}

    def chat(self, user_query: str, auto_route: bool = True) -> Dict[str, Any]:
        if auto_route:
            assigned_id = self.route_query(user_query)
            agent_result = self.run_agent(assigned_id, user_query)
            return {{
                "orchestrator_mode": "auto_route",
                "assigned_agent": assigned_id,
                "agent_name": getattr(self.sub_agents.get(assigned_id), "name", assigned_id),
                "result": agent_result
            }}
        return self.run_pipeline(user_query)


_root_instance: Optional[RootOrchestrator] = None


def get_root_agent() -> RootOrchestrator:
    global _root_instance
    if _root_instance is None:
        _root_instance = RootOrchestrator()
    return _root_instance
'''

    def _generate_settings_yaml(
        self, plan_data: Dict[str, Any], design_data: Dict[str, Any]
    ) -> str:
        """Generate settings.yaml configuration matching active agents."""
        proj_name = plan_data.get("project", {}).get("name", "Google ADK System")
        proj_desc = plan_data.get("project", {}).get("description", "Multi-agent system")

        lines = [
            "# Central Settings for Google ADK Multi-Agent System",
            "app:",
            f'  name: "{proj_name}"',
            '  version: "1.0.0"',
            f'  description: "{proj_desc}"',
            "",
            "models:",
            '  default: "gemini-2.5-flash"',
            '  reasoning: "gemini-2.5-pro"',
            '  creative: "gemini-2.5-flash"',
            '  fast: "gemini-2.5-flash"',
            "",
            "generation:",
            "  temperature: 0.7",
            "  top_p: 0.95",
            "  top_k: 40",
            "  max_output_tokens: 4096",
            "",
            "agents:",
        ]

        for agent in design_data.get("agents", []):
            aid = agent["id"]
            aname = agent.get("name", aid)
            arole = agent.get("responsibility", "Agent")
            amodel = agent.get("model", {}).get("model_name", "gemini-2.5-flash")
            atemp = agent.get("model", {}).get("temperature", 0.2)

            lines.extend([
                f"  {aid}:",
                f'    id: "{aid}"',
                f'    name: "{aname}"',
                f'    role: "{arole}"',
                f'    model: "{amodel}"',
                f"    temperature: {atemp}",
                "    enabled: true",
                "",
            ])

        lines.extend([
            "orchestrator:",
            '  strategy: "autonomous_routing"',
            "  max_iterations: 6",
            "  timeout_seconds: 60",
            "",
        ])

        return "\n".join(lines)
