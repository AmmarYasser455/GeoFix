"""LangChain agent setup for the GeoFix conversational interface.

Uses LangChain's tool-calling LLM with Ollama (local) or Google Gemini.
"""

from __future__ import annotations

import logging
import os

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from geofix.chat.prompts import SYSTEM_PROMPT
from geofix.chat.tools import ALL_TOOLS
from geofix.core.config import GeoFixConfig, DEFAULT_CONFIG

logger = logging.getLogger("geofix.chat.agent")


def _create_llm(config: GeoFixConfig):
    """Create the LLM instance based on config.llm.provider."""
    provider = config.llm.provider

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=config.llm.model,
            temperature=config.llm.temperature,
            base_url=config.llm.ollama_base_url,
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=config.llm.model,
            temperature=config.llm.temperature,
            max_output_tokens=config.llm.max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


class GeoFixAgent:
    """Tool-calling agent powered by a local or cloud LLM.

    Uses ``bind_tools`` so the LLM can invoke GeoFix tools directly.
    """

    def __init__(self, config: GeoFixConfig = DEFAULT_CONFIG):
        self.llm = _create_llm(config)
        self.llm_with_tools = self.llm.bind_tools(ALL_TOOLS)
        self.system_msg = SystemMessage(content=SYSTEM_PROMPT)

    def invoke(self, user_input: str, chat_history: list | None = None) -> str:
        """Process a user message and return the agent's response.

        Handles tool calls automatically — if the LLM calls a tool,
        the tool is executed and the result is fed back to the LLM.
        """
        # Dynamic Tool Binding:
        # If no file is uploaded, HIDE the processing tools so the LLM cannot use them.
        # This prevents hallucinations during small talk.
        from geofix.chat.tools import get_state, ALL_TOOLS, consult_encyclopedia, get_audit_log
        
        has_file = get_state("buildings_path") is not None
        
        if has_file:
            available = ALL_TOOLS
        else:
            # Only allow harmless tools
            available = [consult_encyclopedia, get_audit_log]

        # Re-bind tools for this turn
        llm_with_tools = self.llm.bind_tools(available)
        
        messages = [self.system_msg]

        # Add chat history
        if chat_history:
            for msg in chat_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))

        # Dynamic System Instruction
        if not has_file:
            messages.append(SystemMessage(content="IMPORTANT: No file is uploaded. You CANNOT use `profile_data` or `detect_errors`. If user greets you, just chat. Do NOT complain about missing files."))

        messages.append(HumanMessage(content=user_input))

        # Agentic loop — keep going until LLM stops calling tools
        for _step in range(10):
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            # Check if there are tool calls
            if not response.tool_calls:
                return response.content or "Done."

            # Execute each tool call
            from langchain_core.messages import ToolMessage

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                # Find and execute the tool
                tool_fn = next(
                    (t for t in available if t.name == tool_name), None
                )
                if tool_fn is None:
                    # If LLM tries to call a hidden tool (hallucination), steer it back to chat
                    result = "SYSTEM NOTE: The user has NOT uploaded a file yet. Do NOT use data tools. Just answer the user's question conversationally or use the encyclopedia."
                else:
                    try:
                        result = tool_fn.invoke(tool_args)
                    except Exception as exc:
                        result = f"Tool error: {exc}"

                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )
        
        return response.content or "Reached maximum steps."


def create_agent(config: GeoFixConfig = DEFAULT_CONFIG, model_name: str | None = None) -> GeoFixAgent:
    """Create a GeoFix agent instance with optional model override."""
    if model_name:
        from dataclasses import replace
        new_llm = replace(config.llm, model=model_name)
        config = replace(config, llm=new_llm)

    agent = GeoFixAgent(config)
    logger.info(
        "GeoFix agent created with %d tools (provider=%s, model=%s)",
        len(ALL_TOOLS), config.llm.provider, config.llm.model,
    )
    return agent
