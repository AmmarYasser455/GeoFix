"""Chainlit chat application — the user-facing entry point for GeoFix.

Run with:
    chainlit run geofix/chat/app.py
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import chainlit as cl

from geofix.chat.agent import create_agent
from geofix.chat.prompts import WELCOME_MESSAGE
from geofix.chat.tools import set_state
from geofix.audit.logger import AuditLogger
from geofix.core.config import DEFAULT_CONFIG

logger = logging.getLogger("geofix.chat.app")


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Profile Data",
            message="profile",
            ),
        cl.Starter(
            label="Detect Errors",
            message="detect errors",
            ),
        cl.Starter(
            label="Fix All",
            message="fix all",
            ),
        cl.Starter(
            label="Download",
            message="download",
            ),
    ]


@cl.on_chat_start
async def start():
    """Initialise the agent, audit logger, and temp directory."""
    agent = create_agent()
    cl.user_session.set("agent", agent)
    cl.user_session.set("chat_history", [])

    # Set up audit logger
    audit = AuditLogger(DEFAULT_CONFIG.audit_db_path)
    cl.user_session.set("audit_logger", audit)
    set_state("audit_logger", audit)

    # Settings
    settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="Model",
                label="AI Model Strategy",
                values=["Speed (Llama 3.2)", "Smart (Llama 3.1 8B)", "Genius (DeepSeek R1)"],
                initial_index=0,
            )
        ]
    ).send()

    # Temp dir for uploaded files
    tmp = Path(tempfile.mkdtemp(prefix="geofix_"))
    cl.user_session.set("tmp_dir", tmp)

    # await cl.Message(content=WELCOME_MESSAGE).send()


@cl.on_settings_update
async def setup_agent(settings):
    model_map = {
        "Speed (Llama 3.2)": "llama3.2",
        "Smart (Llama 3.1 8B)": "llama3.1:8b",
        "Genius (DeepSeek R1)": "deepseek-r1:14b",
    }
    selected = settings["Model"]
    model_name = model_map.get(selected, "llama3.2")
    
    # Re-create agent
    agent = create_agent(model_name=model_name)
    cl.user_session.set("agent", agent)
    await cl.Message(content=f"🧠 **Brain Switched!** Now using: `{selected}`").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages and file uploads."""
    agent = cl.user_session.get("agent")
    history = cl.user_session.get("chat_history", [])

    # Handle file uploads
    if message.elements:
        await _handle_file_upload(message)
        return

    user_text = message.content.strip().lower()

    # ── Keyword routing (bypasses LLM → saves API quota) ──
    direct_result = await _try_direct_command(user_text)
    if direct_result is not None:
        history.append({"role": "user", "content": message.content})

        # Handle download — send file as Chainlit element
        if direct_result.startswith("DOWNLOAD_READY:"):
            file_path = direct_result.split(":", 1)[1]
            elements = [cl.File(name="building_qc.gpkg", path=file_path, display="inline")]
            reply = "📥 **Your corrected dataset is ready!** Click the file below to download."
            history.append({"role": "assistant", "content": reply})
            cl.user_session.set("chat_history", history)
            await cl.Message(content=reply, elements=elements).send()
        else:
            history.append({"role": "assistant", "content": direct_result})
            cl.user_session.set("chat_history", history)
            await cl.Message(content=direct_result).send()
        return

    # ── LLM agent (with retry for rate limits) ──
    import time

    msg = cl.Message(content="")
    await msg.send()

    # Construct messages list for LangGraph
    # We convert history dicts to format expected by the model/graph
    messages = []
    for h in history:
        messages.append(h)
    messages.append({"role": "user", "content": message.content})

    try:
        # Stream events (v2) to get tokens as they are generated
        async for event in agent.astream_events(
            {"messages": messages},
            version="v2"
        ):
            kind = event["event"]
            
            # Stream tokens from the model
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    await msg.stream_token(chunk.content)
            
            # Optional: Log tool usage to UI (as steps) if needed
            # But for now, just text streaming satisfies the "working in background" need
            
        await msg.update()

        # Update history
        history.append({"role": "user", "content": message.content})
        history.append({"role": "assistant", "content": msg.content})
        cl.user_session.set("chat_history", history)
        return

    except Exception as exc:
        err_str = str(exc)
        logger.error("Agent error: %s", exc)
        await cl.Message(
            content=f"❌ An error occurred: {exc}\n\nPlease try again."
        ).send()
        return


async def _try_direct_command(text: str) -> str | None:
    """Route common commands directly to tools without LLM.

    Returns tool output string, or None if not a recognised command.
    """
    from geofix.chat.tools import (
        detect_errors, show_errors, fix_all_auto,
        get_audit_log, profile_data, download_fixed, _state,
        consult_encyclopedia,
    )

    # Normalise: replace underscores with spaces for matching
    norm = text.replace("_", " ").replace("?", "").strip()

    # ── Greeting Bypass (Prevent Hallucinations) ──
    # Llama 3.2 tends to hallucinate "file errors" on greetings.
    # We intercept common greetings and return a static response.
    # Match any message that STARTS with a greeting
    greetings = ["hello", "hi", "hey", "sup", "greetings", "yo", "test", "start"]
    if any(norm.startswith(g) for g in greetings):
        return (
            "👋 **Hello!** I am GeoFix.\n\n"
            "I can help you:\n"
            "- **Fix Data**: Upload a file (SHP/GeoJSON/GPKG) 📎.\n"
            "- **Explain Concepts**: Ask about \"topology\" or \"OVC logic\".\n"
            "- **Chat**: Ask me anything!"
        )

    # logic / how it works
    # Match various phrasings: "how you work", "how you works", "your logic", "how do you work"
    logic_keywords = ["how you work", "how do you work", "logic", "pipeline", "explain logic", "how it works", "how you works", "how do you check", "your process"]
    if any(kw in norm for kw in logic_keywords):
        return consult_encyclopedia.invoke({"term": "logic"})

    # detect errors
    if any(kw in norm for kw in ["detect error", "find error", "run qc", "check error", "run check"]):
        return detect_errors.invoke({})

    # show errors
    if any(kw in norm for kw in ["show error", "list error", "what error"]):
        return show_errors.invoke({})

    # fix all
    if any(kw in norm for kw in ["fix all", "fix everything", "auto fix", "autofix"]):
        return fix_all_auto.invoke({})

    # audit log
    if any(kw in norm for kw in ["audit", "get audit", "log", "history"]):
        return get_audit_log.invoke({})

    # profile
    if any(kw in norm for kw in ["profile", "quality score", "data quality"]):
        return profile_data.invoke({})

    # download
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
            await cl.Message(
                content=f"📁 Received: **{element.name}**"
            ).send()

    if not uploaded_paths:
        await cl.Message(content="No valid files detected.").send()
        return

    # Store the primary file path
    primary = uploaded_paths[0]
    set_state("buildings_path", str(primary))

    # Auto-profile
    await cl.Message(content="🔍 Profiling your data...").send()

    from geofix.integration.geoqa_bridge import GeoQABridge

    bridge = GeoQABridge()
    summary = bridge.profile(primary)
    set_state("last_profile", summary)

    lines = [
        f"## Dataset: {summary.name}\n",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Features | {summary.feature_count} |",
        f"| Geometry | {summary.geometry_type} |",
        f"| CRS | {summary.crs} |",
        f"| Quality Score | {summary.quality_score:.0f}/100 |",
        f"| Valid Geometries | {summary.valid_pct:.1f}% |",
    ]

    if summary.warnings:
        lines.append(f"\n⚠️ **Warnings:** " + "; ".join(summary.warnings))
    if summary.blockers:
        lines.append(f"\n🚫 **Blockers:** " + "; ".join(summary.blockers))

    if summary.is_ready:
        lines.append(
            "\n✅ Data looks good! "
            'Say **"detect errors"** to run the full QC pipeline.'
        )
    else:
        lines.append(
            "\n❌ Data has quality blockers. "
            "Please fix the issues above and re-upload."
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
    """CLI entry point — used by 'geofix' console script."""
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)


if __name__ == "__main__":
    main()
