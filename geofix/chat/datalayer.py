import json
from typing import Any, Dict, List, Optional

import chainlit.data as cl_data
from chainlit.element import ElementDict
from chainlit.step import StepDict
from chainlit.types import PaginatedResponse, Pagination, ThreadDict, ThreadFilter

from geofix.storage.conversations import ConversationStore


class GeoFixDataLayer(cl_data.BaseDataLayer):
    def __init__(self, store: ConversationStore):
        print("DEBUG: GeoFixDataLayer initialized")
        self.store = store

    async def get_user(self, identifier: str):
        return None

    async def create_user(self, user: Any):
        return None

    async def list_threads(
        self, pagination: Pagination, filter: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        limit = pagination.first or 20
        # Simple pagination relying on limit for now. Real cursor/offset requires schema change or advanced query
        conversations = self.store.list_conversations(limit=limit)

        threads: List[ThreadDict] = []
        for conv in conversations:
            threads.append({
                "id": conv["id"],
                "createdAt": conv["created_at"],
                "name": conv["title"],
                "userId": None,
                "user": None,
                "tags": [],
                "metadata": json.loads(conv["metadata"]) if conv["metadata"] else {},
                "steps": [],
                "elements": [],
            })

        return PaginatedResponse(
            data=threads,
            pageInfo={"hasNextPage": False, "endCursor": None}
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        # We need to fetch the conversation and its messages
        # But ConversationStore.get_messages returns dicts, we need to map to StepDict
        conv = self.store.conn.execute("SELECT * FROM conversations WHERE id = ?", (thread_id,)).fetchone()
        if not conv:
            return None

        conv_dict = dict(conv)
        messages = self.store.get_messages(thread_id)

        steps: List[StepDict] = []
        for msg in messages:
            steps.append({
                "id": msg["id"],
                "name": "User" if msg["role"] == "user" else "GeoFix",
                "type": "user_message" if msg["role"] == "user" else "assistant_message",
                "threadId": thread_id,
                "parentId": None,
                "isError": False,
                "waitForAnswer": False,
                "content": msg["content"],
                "metadata": {},
                "createdAt": msg["timestamp"],
                "start": msg["timestamp"],
                "end": msg["timestamp"],
                "output": msg["content"],
                "feedback": None,
                "generation": None,
                "input": msg["content"] if msg["role"] == "user" else None,
            })

        return {
            "id": conv_dict["id"],
            "createdAt": conv_dict["created_at"],
            "name": conv_dict["title"],
            "userId": None,
            "user": None,
            "tags": [],
            "metadata": json.loads(conv_dict["metadata"]) if conv_dict["metadata"] else {},
            "steps": steps,
            "elements": [],
        }

    async def update_thread(self, thread_id: str, name: Optional[str] = None, user_id: Optional[str] = None, metadata: Optional[Dict] = None, tags: Optional[List[str]] = None):
        if name:
            self.store.conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (name, thread_id))
        self.store.conn.commit()

    async def delete_thread(self, thread_id: str):
        self.store.delete_conversation(thread_id)

    async def create_step(self, step_dict: StepDict):
        pass

    async def update_step(self, step_dict: StepDict):
        pass

    async def delete_step(self, step_id: str):
        pass

    # Missing abstract methods implementation

    async def get_thread_author(self, thread_id: str) -> str:
        return "GeoFix User"

    async def delete_feedback(self, feedback_id: str) -> bool:
        return True

    async def upsert_feedback(self, feedback: Any) -> str:
        return "feedback_id"

    async def create_element(self, element: Any):
        pass

    async def get_element(self, thread_id: str, element_id: str) -> Optional[ElementDict]:
        return None

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        pass

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        return []

    async def build_debug_url(self) -> str:
        return ""

    async def close(self):
        self.store.close()


