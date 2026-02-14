"""LangChain agent setup for the GeoFix conversational interface.

Uses LangChain's tool-calling LLM with Ollama (local) or Google Gemini.
Supports per-invocation model switching and context window management.
"""

from __future__ import annotations

import logging
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from geofix.chat.prompts import SYSTEM_PROMPT
from geofix.chat.tools import ALL_TOOLS
from geofix.core.config import GeoFixConfig, DEFAULT_CONFIG

logger = logging.getLogger("geofix.chat.agent")

MAX_HISTORY_MESSAGES = 40
MAX_AGENT_STEPS = 10


def _create_llm(
    config: GeoFixConfig,
    model_override: str | None = None,
    api_key: str | None = None,
):
    """Create the LLM instance based on config.llm.provider."""
    provider = config.llm.provider
    model = model_override or config.llm.model

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            temperature=config.llm.temperature,
            base_url=config.llm.ollama_base_url,
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=config.llm.temperature,
            google_api_key=api_key or config.llm.api_key,
            convert_system_message_to_human=True,
            max_output_tokens=config.llm.max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def _trim_history(messages: list, max_messages: int = MAX_HISTORY_MESSAGES) -> list:
    """Keep only the most recent messages to respect context window limits.

    Always preserves the system message at index 0.
    """
    if len(messages) <= max_messages + 1:
        return messages

    system = [m for m in messages if isinstance(m, SystemMessage)]
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]

    trimmed = non_system[-(max_messages):]
    return system + trimmed


class GeoFixAgent:
    """Tool-calling agent powered by a local or cloud LLM.

    Uses ``bind_tools`` so the LLM can invoke GeoFix tools directly.
    """

    def __init__(
        self,
        config: GeoFixConfig = DEFAULT_CONFIG,
        model_name: str | None = None,
        api_key: str | None = None,
    ):
        self.config = config
        self.model_name = model_name or config.llm.model
        self.api_key = api_key
        self.llm = _create_llm(config, self.model_name, self.api_key)
        self.llm_with_tools = self.llm.bind_tools(ALL_TOOLS)
        self.system_msg = SystemMessage(content=SYSTEM_PROMPT)

    def invoke(self, user_input: str, chat_history: list | None = None) -> str:
        """Process a user message and return the agent's response.

        Handles tool calls automatically — if the LLM calls a tool,
        the tool is executed and the result is fed back to the LLM.
        """
        result_parts = []
        for token in self.stream(user_input, chat_history):
            result_parts.append(token)
        return "".join(result_parts) or "Done."

    def stream(self, user_input: str, chat_history: list | None = None):
        """Stream tokens from the LLM one-by-one.

        Yields individual text chunks as they are generated.
        Handles tool calls internally (tool output is not streamed).
        """
        from geofix.chat.tools import get_state, ALL_TOOLS, consult_encyclopedia, get_audit_log

        has_file = get_state("buildings_path") is not None

        available = ALL_TOOLS if has_file else [consult_encyclopedia, get_audit_log]
        llm_with_tools = self.llm.bind_tools(available)

        messages = [self.system_msg]

        if chat_history:
            for msg in chat_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))

        if not has_file:
            messages.append(
                SystemMessage(
                    content="No file is uploaded. You cannot use data processing tools. "
                    "Respond conversationally or use the encyclopedia for GIS terms."
                )
            )

        messages.append(HumanMessage(content=user_input))
        messages = _trim_history(messages)

        for _step in range(MAX_AGENT_STEPS):
            # Stream the response and collect it simultaneously
            collected_chunks = []
            full_response = None

            for chunk in llm_with_tools.stream(messages):
                collected_chunks.append(chunk)
                if chunk.content:
                    yield chunk.content

            # Merge chunks into a single AIMessage to check for tool calls
            if collected_chunks:
                full_response = collected_chunks[0]
                for c in collected_chunks[1:]:
                    full_response = full_response + c

            if full_response is None:
                return

            messages.append(full_response)

            # If no tool calls, we're done (content already streamed)
            if not full_response.tool_calls:
                return

            # Execute tool calls and loop back for the next LLM response
            for tool_call in full_response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                tool_fn = next((t for t in available if t.name == tool_name), None)
                if tool_fn is None:
                    result = (
                        "Tool unavailable. No file has been uploaded yet. "
                        "Answer the user's question conversationally."
                    )
                else:
                    try:
                        result = tool_fn.invoke(tool_args)
                    except Exception as exc:
                        result = f"Tool error: {exc}"

                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )


def create_agent(
    config: GeoFixConfig = DEFAULT_CONFIG,
    model_name: str | None = None,
) -> GeoFixAgent:
    """Create a GeoFix agent instance with optional model override."""
    if model_name:
        from dataclasses import replace

        new_llm = replace(config.llm, model=model_name)
        config = replace(config, llm=new_llm)

    agent = GeoFixAgent(config)
    logger.info(
        "Agent created: %d tools, provider=%s, model=%s",
        len(ALL_TOOLS),
        config.llm.provider,
        config.llm.model,
    )
    return agent
