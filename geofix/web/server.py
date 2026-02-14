"""FastAPI backend for GeoFix custom web UI.

Provides:
  - WebSocket /ws/chat  — real-time streaming via GeoFixAgent
  - REST API            — conversation CRUD, file upload, model listing
  - Static files        — serves the HTML/CSS/JS frontend
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from geofix.audit.logger import AuditLogger
from geofix.chat.agent import create_agent
from geofix.chat.tools import set_state
from geofix.core.cache import ResponseCache
from geofix.core.config import DEFAULT_CONFIG
from geofix.core.router import select_model
from geofix.storage.conversations import ConversationStore
from geofix.web import auth

logger = logging.getLogger("geofix.web.server")

# ── Shared State ───────────────────────────────────────────────

_conv_store = ConversationStore(DEFAULT_CONFIG.conversations.db_path)
_response_cache = ResponseCache(
    max_size=DEFAULT_CONFIG.cache.max_size,
    ttl_seconds=DEFAULT_CONFIG.cache.ttl_seconds,
)

# Per-session state (keyed by session_id)
_sessions: dict[str, dict] = {}

STATIC_DIR = Path(__file__).parent / "static"

# ── FastAPI App ────────────────────────────────────────────────

app = FastAPI(title="GeoFix", version="2.1.0")
app.include_router(auth.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_session(session_id: str) -> dict:
    """Get or create a session."""
    if session_id not in _sessions:
        agent = create_agent()
        audit = AuditLogger(DEFAULT_CONFIG.audit_db_path)
        tmp = Path(tempfile.mkdtemp(prefix="geofix_"))
        _sessions[session_id] = {
            "agent": agent,
            "audit": audit,
            "tmp_dir": tmp,
            "history": [],
            "model_override": None,
        }
    return _sessions[session_id]


# ── REST API ───────────────────────────────────────────────────

@app.get("/api/conversations")
async def list_conversations():
    """List all conversations, newest first."""
    convs = _conv_store.list_conversations(limit=50)
    return convs


@app.get("/api/conversations/{conv_id}/messages")
async def get_messages(conv_id: str):
    """Get all messages for a conversation."""
    msgs = _conv_store.get_messages(conv_id)
    return msgs


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Delete a conversation."""
    _conv_store.delete_conversation(conv_id)
    return {"ok": True}


class RenameBody(BaseModel):
    title: str


@app.patch("/api/conversations/{conv_id}")
async def rename_conversation(conv_id: str, body: RenameBody):
    """Rename a conversation."""
    _conv_store.update_title(conv_id, body.title)
    return {"ok": True}


@app.post("/api/conversations")
async def create_conversation():
    """Create a new conversation and return its id."""
    conv_id = _conv_store.create_conversation()
    return {"id": conv_id}


@app.get("/api/models")
async def list_models():
    """List available models."""
    return [
        {"id": "auto", "name": "Auto", "description": "Routes by query complexity"},
        {"id": "llama3.2", "name": "Speed (Llama 3.2)", "description": "Fast responses"},
        {"id": "llama3.1:latest", "name": "Smart (Llama 3.1)", "description": "Balanced"},
        {"id": "deepseek-r1:14b", "name": "Deep Think (DeepSeek R1)", "description": "Deep reasoning"},
    ]


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), session_id: str = "default"):
    """Handle geospatial file uploads."""
    session = _get_session(session_id)
    tmp_dir = session["tmp_dir"]

    dest = tmp_dir / file.filename
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    set_state("buildings_path", str(dest))

    # Profile the data
    try:
        from geofix.integration.geoqa_bridge import GeoQABridge

        bridge = GeoQABridge()
        summary = bridge.profile(dest)
        set_state("last_profile", summary)

        profile_text = (
            f"## Dataset: {summary.name}\n\n"
            f"| Metric | Value |\n|---|---|\n"
            f"| Features | {summary.feature_count} |\n"
            f"| Geometry | {summary.geometry_type} |\n"
            f"| CRS | {summary.crs} |\n"
            f"| Quality Score | {summary.quality_score:.0f}/100 |\n"
            f"| Valid Geometries | {summary.valid_pct:.1f}% |\n"
        )

        if summary.warnings:
            profile_text += "\n**Warnings:** " + "; ".join(summary.warnings)
        if summary.blockers:
            profile_text += "\n**Blockers:** " + "; ".join(summary.blockers)

        if summary.is_ready:
            profile_text += '\n\nData looks good. Say **"detect errors"** to run the full QC pipeline.'
        else:
            profile_text += "\n\nData has quality blockers. Please fix the issues above and re-upload."

        return {"filename": file.filename, "profile": profile_text}
    except Exception as e:
        logger.error("Profile error: %s", e)
        return {"filename": file.filename, "profile": f"File received: **{file.filename}**\n\n(Profiling unavailable: {e})"}


# ── WebSocket Chat ─────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """Stream chat responses over WebSocket.

    Protocol:
      Client sends JSON: { "message": "...", "conversation_id": "...", "session_id": "...", "model": "auto" }
      Server sends JSON chunks:
        { "type": "token", "content": "..." }
        { "type": "done", "conversation_id": "..." }
        { "type": "error", "content": "..." }
    """
    await ws.accept()
    logger.info("WebSocket connected")

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            message = data.get("message", "").strip()
            conv_id = data.get("conversation_id")
            session_id = data.get("session_id", "default")
            model_id = data.get("model", "auto")
            api_key = data.get("api_key")

            if not message:
                continue

            session = _get_session(session_id)
            history = session["history"]

            # Create conversation if needed
            if not conv_id:
                conv_id = _conv_store.create_conversation(title=message[:80])
                await ws.send_json({"type": "conversation_created", "conversation_id": conv_id, "title": message[:80]})

            # Store user message
            _conv_store.add_message(conv_id, "user", message)

            # Check cache
            cached = _response_cache.get(message)
            if cached is not None:
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": cached})
                _conv_store.add_message(conv_id, "assistant", cached)
                await ws.send_json({"type": "token", "content": cached})
                await ws.send_json({"type": "done", "conversation_id": conv_id})
                continue

            # Try direct commands
            direct = _try_direct_command(message.lower())
            if direct is not None:
                history.append({"role": "user", "content": message})

                if direct.startswith("DOWNLOAD_READY:"):
                    file_path = direct.split(":", 1)[1]
                    reply = f"Your corrected dataset is ready: [Download]({file_path})"
                    history.append({"role": "assistant", "content": reply})
                    _conv_store.add_message(conv_id, "assistant", reply)
                    await ws.send_json({"type": "token", "content": reply})
                else:
                    _response_cache.put(message, direct)
                    history.append({"role": "assistant", "content": direct})
                    _conv_store.add_message(conv_id, "assistant", direct)
                    await ws.send_json({"type": "token", "content": direct})

                await ws.send_json({"type": "done", "conversation_id": conv_id})
                continue

            # Select model
            if model_id == "auto" or not model_id:
                routed = select_model(message, history_len=len(history))
                agent = create_agent(model_name=routed, api_key=api_key)
            else:
                agent = create_agent(model_name=model_id, api_key=api_key)

            # Stream LLM response
            start_time = time.time()
            full_response = []

            try:
                for token in agent.stream(message, chat_history=history):
                    full_response.append(token)
                    await ws.send_json({"type": "token", "content": token})

                response_text = "".join(full_response)
                elapsed = time.time() - start_time

                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": response_text})
                session["history"] = history

                _response_cache.put(message, response_text)
                _conv_store.add_message(conv_id, "assistant", response_text, processing_time=elapsed)

                await ws.send_json({"type": "done", "conversation_id": conv_id})

            except Exception as e:
                logger.error("Stream error: %s", e)
                await ws.send_json({"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)


def _try_direct_command(text: str) -> str | None:
    """Route common commands directly to tools without LLM."""
    from geofix.chat.tools import (
        consult_encyclopedia,
        detect_errors,
        download_fixed,
        fix_all_auto,
        get_audit_log,
        profile_data,
        show_errors,
    )

    norm = text.replace("_", " ").replace("?", "").strip()

    greetings = ["hello", "hi", "hey", "sup", "greetings", "yo", "test", "start"]
    if any(norm.startswith(g) for g in greetings):
        return (
            "Hello! I am **GeoFix**, your geospatial data correction assistant.\n\n"
            "I can help you:\n"
            "- **Fix Data** — upload a file (SHP / GeoJSON / GPKG)\n"
            "- **Explain Concepts** — ask about topology, OVC logic, or any GIS topic\n"
            "- **Chat** — ask me anything"
        )

    logic_keywords = [
        "how you work", "how do you work", "logic", "pipeline",
        "explain logic", "how it works", "how do you check", "your process",
    ]
    if any(kw in norm for kw in logic_keywords):
        return consult_encyclopedia.invoke({"term": "logic"})

    if any(kw in norm for kw in ["detect error", "find error", "run qc", "check error", "run check"]):
        return detect_errors.invoke({})

    if any(kw in norm for kw in ["show error", "list error", "what error"]):
        return show_errors.invoke({})

    if any(kw in norm for kw in ["fix all", "fix everything", "auto fix", "autofix"]):
        return fix_all_auto.invoke({})

    if any(kw in norm for kw in ["audit", "get audit", "log", "history"]):
        return get_audit_log.invoke({})

    if any(kw in norm for kw in ["profile", "quality score", "data quality"]):
        return profile_data.invoke({})

    if any(kw in norm for kw in ["download", "export", "save fixed", "get fixed"]):
        return download_fixed.invoke({})

    return None


# ── Static Files & Entry ───────────────────────────────────────

# Serve logo/avatar from public dir (fallback)
PUBLIC_DIR = Path(__file__).parent.parent.parent / "public"


@app.get("/")
async def landing():
    return FileResponse(STATIC_DIR / "intro.html")


@app.get("/chat")
async def chat(request: Request):
    user = auth._get_current_user(request)
    if not user:
        return RedirectResponse("/")
    return FileResponse(STATIC_DIR / "index.html")


# Mount static after explicit routes
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if PUBLIC_DIR.exists():
    app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")


def run():
    """CLI entry point."""
    import uvicorn

    uvicorn.run(
        "geofix.web.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    run()
