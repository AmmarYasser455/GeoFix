"""Chainlit chat application — the user-facing entry point for GeoFix.

Run with:
    chainlit run geofix/chat/app.py
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import chainlit as cl

from geofix.chat.agent import create_agent
from geofix.chat.prompts import WELCOME_MESSAGE
from geofix.chat.tools import set_state
from geofix.audit.logger import AuditLogger
from geofix.core.cache import ResponseCache
from geofix.chat.datalayer import GeoFixDataLayer
from geofix.core.config import DEFAULT_CONFIG
from geofix.core.router import select_model
from geofix.storage.conversations import ConversationStore

logger = logging.getLogger("geofix.chat.app")

# Cache for responses to identical queries (simple in-memory)
_response_cache = ResponseCache(
    max_size=DEFAULT_CONFIG.cache.max_size,
    ttl_seconds=DEFAULT_CONFIG.cache.ttl_seconds,
)

# Initialize conversation store
# Initialize conversation store
_conv_store = ConversationStore(DEFAULT_CONFIG.conversations.db_path)

import chainlit.data as cl_data

# Initialize data layer for Chainlit sidebar history
# KEY FIX: Direct injection into chainlit.data module AND config to ensure persistence.
_dl_instance = GeoFixDataLayer(_conv_store)

# Method 1: Inject into data module (for immediate access)
cl_data._data_layer = _dl_instance
cl_data._data_layer_initialized = True

# Method 2: Inject into config (for fallback if data module resets)
from chainlit.config import config
config.code.data_layer = lambda: _dl_instance

logger.info("DEBUG: GeoFixDataLayer injected into chainlit.data and chainlit.config")
# raise Exception("VERIFICATION: app.py is running!")

# Legacy decorator (kept but likely ignored due to init order)
@cl.data_layer
def get_data_layer():
    logger.info("DEBUG: get_data_layer called (via decorator)")
    return _dl_instance


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="📊 Profile My Data",
            message="Profile my data quality — check CRS, validity, duplicates, and feature statistics.",
            icon="/public/favicon.png",
        ),
        cl.Starter(
            label="🔍 Detect Errors",
            message="Run the full quality check pipeline — detect overlaps, boundary violations, invalid geometries, and road conflicts.",
            icon="/public/favicon.png",
        ),
        cl.Starter(
            label="🔧 Auto-Fix Everything",
            message="Detect all errors and automatically fix what you can. Show me the results.",
            icon="/public/favicon.png",
        ),
        cl.Starter(
            label="💡 What Can You Do?",
            message="What are your capabilities? Give me a quick overview of what GeoFix can help with.",
            icon="/public/favicon.png",
        ),
    ]


@cl.set_chat_profiles
async def chat_profile():
    return [
        cl.ChatProfile(
            name="Auto",
            markdown_description="Automatically routes to the best model based on query complexity.",
            icon="/public/favicon.png",
            default=True,
        ),
        cl.ChatProfile(
            name="Speed",
            markdown_description="Llama 3.2 — fast responses for simple queries.",
            icon="/public/favicon.png",
        ),
        cl.ChatProfile(
            name="Deep Think",
            markdown_description="DeepSeek R1 — deep reasoning for complex analysis.",
            icon="/public/favicon.png",
        ),
    ]


@cl.on_chat_start
async def start():
    """Initialise the agent, audit logger, conversation, and temp directory."""
    # Determine model from chat profile
    profile = cl.user_session.get("chat_profile", "Auto")
    profile_model_map = {
        "Auto": None,
        "Speed": "llama3.2",
        "Deep Think": "deepseek-r1:14b",
    }
    model_name = profile_model_map.get(profile)

    agent = create_agent(model_name=model_name) if model_name else create_agent()
    cl.user_session.set("agent", agent)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("user_model_override", model_name)

    # Audit logger
    audit = AuditLogger(DEFAULT_CONFIG.audit_db_path)
    cl.user_session.set("audit_logger", audit)
    set_state("audit_logger", audit)

    # Conversation tracking
    conv_id = _conv_store.create_conversation()
    cl.user_session.set("conversation_id", conv_id)

    # Model selector in settings
    settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="Model",
                label="AI Model",
                values=["Auto", "Speed (Llama 3.2)", "Smart (Llama 3.1)", "Deep (DeepSeek R1)"],
                initial_index=0,
            )
        ]
    ).send()

    # Temp dir for uploaded files
    tmp = Path(tempfile.mkdtemp(prefix="geofix_"))
    cl.user_session.set("tmp_dir", tmp)


@cl.on_chat_resume
async def on_chat_resume(thread: cl_data.ThreadDict):
    """Restore session when loading a past conversation."""
    cl.user_session.set("conversation_id", thread["id"])

    # Rebuild LLM history
    history = []
    for step in thread["steps"]:
        if step["type"] == "user_message":
            history.append({"role": "user", "content": step["output"]})
        elif step["type"] == "assistant_message":
            history.append({"role": "assistant", "content": step["output"]})

    cl.user_session.set("chat_history", history)

    # Re-initialize standard components
    agent = create_agent()
    cl.user_session.set("agent", agent)
    cl.user_session.set("user_model_override", None)

    audit = AuditLogger(DEFAULT_CONFIG.audit_db_path)
    cl.user_session.set("audit_logger", audit)
    set_state("audit_logger", audit)

    tmp = Path(tempfile.mkdtemp(prefix="geofix_"))
    cl.user_session.set("tmp_dir", tmp)


@cl.on_settings_update
async def setup_agent(settings):
    model_map = {
        "Auto": None,
        "Speed (Llama 3.2)": "llama3.2",
        "Smart (Llama 3.1)": "llama3.1:latest",
        "Deep (DeepSeek R1)": "deepseek-r1:14b",
    }
    selected = settings["Model"]
    model_name = model_map.get(selected)

    cl.user_session.set("user_model_override", model_name)

    if model_name:
        agent = create_agent(model_name=model_name)
        cl.user_session.set("agent", agent)
        await cl.Message(content=f"Model switched to **{selected}**").send()
    else:
        agent = create_agent()
        cl.user_session.set("agent", agent)
        await cl.Message(content="Model set to **Auto** — routing by query complexity.").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages and file uploads."""
    agent = cl.user_session.get("agent")
    history = cl.user_session.get("chat_history", [])
    conv_id = cl.user_session.get("conversation_id")

    # Handle file uploads
    if message.elements:
        await _handle_file_upload(message)
        return

    user_text = message.content.strip()
    user_text_lower = user_text.lower()
    start_time = time.time()

    # Store user message
    if conv_id:
        _conv_store.add_message(conv_id, "user", user_text)

    # Check response cache first
    cached = _response_cache.get(user_text)
    if cached is not None:
        elapsed = time.time() - start_time
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": cached})
        cl.user_session.set("chat_history", history)
        if conv_id:
            _conv_store.add_message(conv_id, "assistant", cached, processing_time=elapsed)
        await cl.Message(content=cached).send()
        return

    # Keyword routing (bypasses LLM)
    direct_result = await _try_direct_command(user_text_lower)
    if direct_result is not None:
        elapsed = time.time() - start_time
        history.append({"role": "user", "content": user_text})

        if direct_result.startswith("DOWNLOAD_READY:"):
            file_path = direct_result.split(":", 1)[1]
            elements = [cl.File(name="building_qc.gpkg", path=file_path, display="inline")]
            reply = "Your corrected dataset is ready. Click the file below to download."
            history.append({"role": "assistant", "content": reply})
            cl.user_session.set("chat_history", history)
            await cl.Message(content=reply, elements=elements).send()
        else:
            _response_cache.put(user_text, direct_result)
            history.append({"role": "assistant", "content": direct_result})
            cl.user_session.set("chat_history", history)
            if conv_id:
                _conv_store.add_message(
                    conv_id, "assistant", direct_result, processing_time=elapsed
                )
            await cl.Message(content=direct_result).send()
        return

    # Auto-route model if set to Auto
    user_override = cl.user_session.get("user_model_override")
    if not user_override:
        routed_model = select_model(user_text, history_len=len(history))
        agent = create_agent(model_name=routed_model)

    # LLM agent with streaming (typing animation)
    msg = cl.Message(content="")
    await msg.send()

    try:
        for token in agent.stream(user_text, chat_history=history):
            await msg.stream_token(token)

        await msg.update()

        elapsed = time.time() - start_time
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": msg.content})
        cl.user_session.set("chat_history", history)

        # Cache the response for future identical queries
        _response_cache.put(user_text, msg.content)

        if conv_id:
            _conv_store.add_message(
                conv_id, "assistant", msg.content, processing_time=elapsed
            )

    except Exception as exc:
        logger.error("Agent error: %s", exc)
        await msg.remove()
        await cl.Message(content=f"An error occurred: {exc}\n\nPlease try again.").send()


async def _try_direct_command(text: str) -> str | None:
    """Route common commands directly to tools without LLM.

    Returns tool output string, or None if not a recognised command.
    """
    from geofix.chat.tools import (
        detect_errors,
        show_errors,
        fix_all_auto,
        get_audit_log,
        profile_data,
        download_fixed,
        consult_encyclopedia,
    )

    norm = text.replace("_", " ").replace("?", "").strip()

    # Greetings
    greetings = ["hello", "hi", "hey", "sup", "greetings", "yo", "test", "start"]
    if any(norm.startswith(g) for g in greetings):
        return (
            "Hello! I am **GeoFix**, your geospatial data correction assistant.\n\n"
            "I can help you:\n"
            "- **Fix Data** — upload a file (SHP / GeoJSON / GPKG)\n"
            "- **Explain Concepts** — ask about topology, OVC logic, or any GIS topic\n"
            "- **Chat** — ask me anything"
        )

    # Logic / how it works
    logic_keywords = [
        "how you work", "how do you work", "logic", "pipeline",
        "explain logic", "how it works", "how do you check", "your process",
    ]
    if any(kw in norm for kw in logic_keywords):
        return consult_encyclopedia.invoke({"term": "logic"})

    # Detect errors
    if any(kw in norm for kw in ["detect error", "find error", "run qc", "check error", "run check"]):
        return detect_errors.invoke({})

    # Show errors
    if any(kw in norm for kw in ["show error", "list error", "what error"]):
        return show_errors.invoke({})

    # Fix all
    if any(kw in norm for kw in ["fix all", "fix everything", "auto fix", "autofix"]):
        return fix_all_auto.invoke({})

    # Audit log
    if any(kw in norm for kw in ["audit", "get audit", "log", "history"]):
        return get_audit_log.invoke({})

    # Profile
    if any(kw in norm for kw in ["profile", "quality score", "data quality"]):
        return profile_data.invoke({})

    # Download
    if any(kw in norm for kw in ["download", "export", "save fixed", "get fixed"]):
        return download_fixed.invoke({})

    return None


async def _handle_file_upload(message: cl.Message):
    """Process uploaded geospatial files."""
    tmp_dir: Path = cl.user_session.get("tmp_dir")

    uploaded_paths = []
    for element in message.elements:
        if element.path:
            dest = tmp_dir / element.name
            shutil.copy2(element.path, dest)
            uploaded_paths.append(dest)
            await cl.Message(content=f"Received: **{element.name}**").send()

    if not uploaded_paths:
        await cl.Message(content="No valid files detected.").send()
        return

    primary = uploaded_paths[0]
    set_state("buildings_path", str(primary))

    await cl.Message(content="Profiling your data...").send()

    from geofix.integration.geoqa_bridge import GeoQABridge

    bridge = GeoQABridge()
    summary = bridge.profile(primary)
    set_state("last_profile", summary)

    lines = [
        f"## Dataset: {summary.name}\n",
        "| Metric | Value |",
        "|---|---|",
        f"| Features | {summary.feature_count} |",
        f"| Geometry | {summary.geometry_type} |",
        f"| CRS | {summary.crs} |",
        f"| Quality Score | {summary.quality_score:.0f}/100 |",
        f"| Valid Geometries | {summary.valid_pct:.1f}% |",
    ]

    if summary.warnings:
        lines.append("\n**Warnings:** " + "; ".join(summary.warnings))
    if summary.blockers:
        lines.append("\n**Blockers:** " + "; ".join(summary.blockers))

    if summary.is_ready:
        lines.append('\nData looks good. Say **"detect errors"** to run the full QC pipeline.')
    else:
        lines.append(
            "\nData has quality blockers. Please fix the issues above and re-upload."
        )

    await cl.Message(content="\n".join(lines)).send()


@cl.on_chat_end
async def end():
    """Clean up temp files and close audit logger."""
    tmp_dir = cl.user_session.get("tmp_dir")
    if tmp_dir and Path(tmp_dir).exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)

    audit = cl.user_session.get("audit_logger")
    if audit:
        audit.close()


def main():
    """CLI entry point."""
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)


if __name__ == "__main__":
    main()
