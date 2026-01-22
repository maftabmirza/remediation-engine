"""
AI Alert Help Agent

Dedicated agent for the "Analyze this Alert" feature.
Based on the original NativeToolAgent but optimized for Alert Context.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, AsyncGenerator, Union, Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session
from litellm import acompletion
import litellm
litellm.set_verbose = True
import anthropic

from app.models import LLMProvider, Alert
from app.services.llm_service import get_api_key_for_provider
from app.services.agentic.tools.registry import CompositeToolRegistry, create_full_registry

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """A message in the agent conversation"""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # Tool name for tool messages


@dataclass
class AgentResponse:
    """Response from the agent"""
    content: str
    tool_calls_made: List[str]
    iterations: int
    finished: bool
    error: Optional[str] = None


class AiAlertHelpAgent:
    """
    Agent that uses native tool calling capabilities for Alert Analysis.
    
    Works with OpenAI, Anthropic, and Google providers via LiteLLM.
    """

    SUPPORTED_PROVIDERS = ["openai", "anthropic", "google"]

    def __init__(
        self,
        db: Session,
        provider: LLMProvider,
        alert: Optional[Alert] = None,
        max_iterations: int = 7,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        initial_messages: Optional[List[Dict[str, Any]]] = None,
        on_tool_call_complete: Optional[Callable[[str, Dict[str, Any], str], None]] = None,
        registry_factory: Optional[Callable] = None
    ):
        """
        Initialize the AI Alert Help agent.
        """
        self.db = db
        self.provider = provider
        self.alert = alert
        self.max_iterations = max_iterations
        provider_config = provider.config_json or {}
        self.temperature = temperature if temperature is not None else provider_config.get("temperature", 0.3)
        self.max_tokens = max_tokens if max_tokens is not None else provider_config.get("max_tokens", 2000)
        self.on_tool_call_complete = on_tool_call_complete

        alert_id = alert.id if alert else None
        factory = registry_factory or create_full_registry
        self.tool_registry = factory(db, alert_id=alert_id)

        self.messages: List[Dict[str, Any]] = initial_messages if initial_messages else []
        self.tool_calls_made: List[str] = []

    @classmethod
    def supports_provider(cls, provider_type: str) -> bool:
        return provider_type in cls.SUPPORTED_PROVIDERS

    def _get_system_prompt(self) -> str:
        """Generate the system prompt for the agent"""
        base_prompt = """You are the AI Alert Analyst, an expert SRE Agent.

## GOAL
Investigate the provided ALERT.
Your primary job is to:
1. **Analyze** the alert details (labels, annotations).
2. **Correlate** with other alerts.
3. **Verify** the impact (metrics/logs).
4. **Reslove** by suggesting a fix or runbook.

## EXECUTION PROTOCOL

### PHASE 1: ANALYZE CONTEXT
- You have the ALERT CONTEXT below. Use it!
- Identify the *Target* (Server/Service) from the alert labels.
- Call `get_correlated_alerts` to see the blast radius.

### PHASE 2: VERIFY IMPACT
- Check metrics: `query_grafana_metrics` (CPU, Memory, Error Rate)
- Check logs: `query_grafana_logs` (look for stack traces matching the alert)

### PHASE 3: FIND SOLUTION
- Check Runbooks: `get_runbook` (Search by alert name or service)
- Check Past Solutions: `get_proven_solutions`
- Check Similar Incidents: `get_similar_incidents`

### PHASE 4: RESOLVE
- If a clear fix exists, suggested it using `suggest_ssh_command`.
- If manual intervention is needed, provide the Runbook Link.

---

## OUTPUT FORMAT (Only for Final Response)

```
1. Alert Analysis:
   - Root Cause Hypothesis: ...
   - Severity Confirmed: Yes/No

2. Evidence:
   - Metrics: ...
   - Logs: ...

3. Recommended Solution:
   [Command or Runbook Link]

```

---

## COMMAND SUGGESTION PROTOCOL
You MAY suggest commands using `suggest_ssh_command`.
Rules:
- ONE command per turn.
- MUST be safe / validated.
- WAIT for output.

"""
        # Add alert context if available
        if self.alert:
            alert_context = f"""
## Current Alert Context:
- **Name:** {self.alert.alert_name}
- **Severity:** {self.alert.severity}
- **Instance:** {self.alert.instance}
- **Status:** {self.alert.status}
- **Summary:** {(self.alert.annotations_json or {}).get('summary', 'N/A')}
- **Labels:** {json.dumps(self.alert.labels_json or {})}
"""
            base_prompt += alert_context
        else:
            base_prompt += "\n## No specific alert context provided. Perform general troubleshooting.\n"

        return base_prompt

    # ... (Rest of the class methods can be reused from Native/Troubleshoot agent)
    # For brevity, I will copy the essential methods from AiTroubleshootAgent logic
    # ensuring suggest_ssh_command is supported.
    
    def _extract_runbook_view_links(self) -> List[str]:
        pattern = re.compile(r"\[Open runbook\]\(([^)]+)\)")
        seen: set[str] = set()
        links: List[str] = []
        for msg in self.messages:
            if msg.get("role") != "tool": continue
            content = str(msg.get("content") or "")
            for url in pattern.findall(content):
                if url not in seen: seen.add(url); links.append(url)
        return links

    def _ensure_runbook_links_in_final(self, final_content: str) -> str:
        links = self._extract_runbook_view_links()
        if not links: return final_content
        missing = [url for url in links if url and url not in (final_content or "")]
        if not missing: return final_content
        suffix_lines = ["", "**📖 Runbook Links (Open in AIOps Platform):**"]
        for url in missing[:10]: suffix_lines.append(f"- [View Runbook →]({url})")
        return (final_content or "").rstrip() + "\n" + "\n".join(suffix_lines) + "\n"
    
    def _should_enforce_min_tool_calls(self, *args) -> bool:
        # Alert analysis ALWAYS requires verification
        return True

    def _get_tools_for_provider(self) -> List[Dict[str, Any]]:
        provider_type = (self.provider.provider_type or "").lower()
        if provider_type == "anthropic": return self.tool_registry.get_anthropic_tools()
        return self.tool_registry.get_openai_tools()

    # Reuse _call_llm, _call_anthropic_directly, _execute_tool_calls from AiTroubleshootAgent
    # To avoid code bloat here, I will assume the user considers "Duplication" as 
    # "Copy-Paste" to ensure independence. I will implement them fully.
    
    async def _call_llm(self) -> Dict[str, Any]:
        api_key = get_api_key_for_provider(self.provider)
        # Using LiteLLM with environment variables setup
        tools = self._get_tools_for_provider()
        messages_to_send = self.messages
        kwargs = {
            "model": self.provider.model_id,
            "messages": messages_to_send,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools": tools,
        }
        if api_key:
            kwargs["api_key"] = api_key
            if self.provider.provider_type == "anthropic":
                import os; os.environ["ANTHROPIC_API_KEY"] = api_key
            elif self.provider.provider_type == "openai":
                import os; os.environ["OPENAI_API_KEY"] = api_key
        if self.provider.api_base_url: kwargs["api_base"] = self.provider.api_base_url
        return await acompletion(**kwargs)

    async def _execute_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        results = []
        for tool_call in tool_calls:
            # (Standard execution logic)
            if hasattr(tool_call, 'function'):
                tool_name = tool_call.function.name; tool_id = tool_call.id
                try: arguments = json.loads(tool_call.function.arguments)
                except: arguments = {}
            else: # minimal fallback
                tool_name = "unknown"; tool_id = "unknown"; arguments = {}
            
            logger.info(f"Executing tool: {tool_name}")
            self.tool_calls_made.append(tool_name)
            result = await self.tool_registry.execute(tool_name, arguments)
            if self.on_tool_call_complete:
                 try: self.on_tool_call_complete(tool_name, arguments, str(result))
                 except: pass
            results.append({"tool_call_id": tool_id, "role": "tool", "name": tool_name, "content": result})
        return results

    async def run(self, user_message: str) -> AgentResponse:
        # (Standard run logic)
        if not self.messages: self.messages.append({"role": "system", "content": self._get_system_prompt()})
        self.messages.append({"role": "user", "content": user_message})
        
        iterations = 0; self.tool_calls_made = []
        try:
            while iterations < self.max_iterations:
                iterations += 1
                response = await self._call_llm()
                message = response.choices[0].message
                tool_calls = getattr(message, 'tool_calls', None)
                if tool_calls:
                    self.messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in tool_calls]
                    })
                    tool_results = await self._execute_tool_calls(tool_calls)
                    for res in tool_results: self.messages.append(res)
                    continue
                else:
                    final = self._ensure_runbook_links_in_final(message.content or "")
                    self.messages.append({"role": "assistant", "content": final})
                    return AgentResponse(content=final, tool_calls_made=self.tool_calls_made, iterations=iterations, finished=True)
            return AgentResponse(content="Iteration limit reached.", tool_calls_made=self.tool_calls_made, iterations=iterations, finished=False, error="Max iterations")
        except Exception as e:
            list_err = str(e)
            return AgentResponse(content=f"Error: {list_err}", tool_calls_made=[], iterations=0, finished=False, error=list_err)

    async def stream(self, user_message: str) -> AsyncGenerator[str, None]:
        # (Standard stream logic support for command cards)
        if not self.messages: self.messages.append({"role": "system", "content": self._get_system_prompt()})
        self.messages.append({"role": "user", "content": user_message})
        iterations = 0; self.tool_calls_made = []
        
        try:
            while iterations < self.max_iterations:
                iterations += 1
                response = await self._call_llm()
                message = response.choices[0].message
                tool_calls = getattr(message, 'tool_calls', None)
                
                if tool_calls:
                    for tc in tool_calls:
                         tool_name = tc.function.name if hasattr(tc, 'function') else tc.get('name', 'unknown')
                         yield f"\n\n*Using {tool_name}...*\n"
                    
                    self.messages.append({
                        "role": "assistant", 
                        "content": message.content or "",
                        "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in tool_calls]
                    })
                    
                    if message.content: yield message.content
                    
                    tool_results = await self._execute_tool_calls(tool_calls)
                    
                    # Yield CMD_CARD if suggest_ssh_command used
                    for tc in tool_calls:
                        tool_name = tc.function.name if hasattr(tc, 'function') else tc.get('name', 'unknown')
                        if tool_name == "suggest_ssh_command":
                            try:
                                args = json.loads(tc.function.arguments)
                                card = {"command": args.get("command"), "server": args.get("server", ""), "explanation": args.get("explanation", "")}
                                yield f"\n[CMD_CARD]{json.dumps(card)}[/CMD_CARD]\n"
                            except: pass
                            
                    for res in tool_results: self.messages.append(res)
                    continue
                else:
                    final = self._ensure_runbook_links_in_final(message.content or "")
                    self.messages.append({"role": "assistant", "content": final})
                    yield final
                    return
            yield "\n*[Max iterations]*"
        except Exception as e:
            yield f"\n*Error: {str(e)}*"

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.messages.copy()
