"""
a2a/task_manager.py
-------------------
Task lifecycle manager for the A2A protocol.

Manages task state transitions, history, and concurrent task tracking.
Implements the A2A task lifecycle:
  submitted → working → [input-required] → completed | failed | canceled
"""

from __future__ import annotations
import threading
from typing import Callable
from .schemas import (
    Task, TaskState, TaskStatus, Message, Artifact,
    JSONRPCRequest, JSONRPCResponse, A2AError,
    create_agent_message,
)


class TaskManager:
    """Thread-safe task store with A2A lifecycle management."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._history: dict[str, list[TaskStatus]] = {}

    # ── Core task operations ──────────────────────────────────────────── #

    def create_task(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.id] = task
            self._history[task.id] = [task.status]
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def update_status(self, task_id: str, state: TaskState,
                      message: Message | None = None) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            new_status = TaskStatus(state=state, message=message)
            task.status = new_status
            self._history.setdefault(task_id, []).append(new_status)
            return task

    def add_artifact(self, task_id: str, artifact: Artifact) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            artifact.index = len(task.artifacts)
            task.artifacts.append(artifact)
            return task

    def add_message(self, task_id: str, message: Message) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.messages.append(message)
            return task

    def cancel_task(self, task_id: str) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if task.status.state in (TaskState.COMPLETED, TaskState.FAILED):
                return None  # Cannot cancel terminal states
            task.status = TaskStatus(state=TaskState.CANCELED)
            self._history.setdefault(task_id, []).append(task.status)
            return task

    def get_history(self, task_id: str) -> list[dict]:
        return [s.to_dict() for s in self._history.get(task_id, [])]

    def list_tasks(self) -> list[dict]:
        return [
            {"id": t.id, "state": t.status.state.value, "session_id": t.session_id}
            for t in self._tasks.values()
        ]

    # ── JSON-RPC dispatch ────────────────────────────────────────────── #

    def handle_jsonrpc(self, request_data: dict,
                       execute_fn: Callable[[Task], Task] | None = None) -> dict:
        """
        Dispatch a JSON-RPC 2.0 request per A2A spec.

        Supported methods:
          - tasks/send     : Create and execute a task
          - tasks/get      : Get task by ID
          - tasks/cancel   : Cancel a running task
          - tasks/sendSubscribe : Create task with SSE streaming (returns initial status)
        """
        method = request_data.get("method", "")
        params = request_data.get("params", {})
        req_id = request_data.get("id", "")

        handler = {
            "tasks/send":          self._handle_send,
            "tasks/get":           self._handle_get,
            "tasks/cancel":        self._handle_cancel,
            "tasks/sendSubscribe": self._handle_send,  # Same as send, streaming handled at transport layer
        }.get(method)

        if not handler:
            return JSONRPCResponse(
                id=req_id,
                error=A2AError.METHOD_NOT_FOUND,
            ).to_dict()

        return handler(params, req_id, execute_fn)

    def _handle_send(self, params: dict, req_id: str,
                     execute_fn: Callable | None) -> dict:
        from .schemas import create_task as factory_create_task

        message_data = params.get("message", {})
        text_parts = [p.get("text", "") for p in message_data.get("parts", []) if p.get("type") == "text"]
        user_text = " ".join(text_parts) or "No input provided"

        task = factory_create_task(user_text, metadata=params.get("metadata", {}))
        self.create_task(task)

        if execute_fn:
            try:
                self.update_status(task.id, TaskState.WORKING)
                task = execute_fn(task)
                if task.status.state == TaskState.WORKING:
                    self.update_status(task.id, TaskState.COMPLETED)
            except Exception as e:
                self.update_status(
                    task.id, TaskState.FAILED,
                    message=create_agent_message(f"Error: {e}"),
                )

        task = self.get_task(task.id)
        return JSONRPCResponse(id=req_id, result=task.to_dict()).to_dict()

    def _handle_get(self, params: dict, req_id: str, _=None) -> dict:
        task_id = params.get("id", "")
        task = self.get_task(task_id)
        if not task:
            return JSONRPCResponse(id=req_id, error=A2AError.TASK_NOT_FOUND).to_dict()

        result = task.to_dict()
        result["history"] = self.get_history(task_id)
        return JSONRPCResponse(id=req_id, result=result).to_dict()

    def _handle_cancel(self, params: dict, req_id: str, _=None) -> dict:
        task_id = params.get("id", "")
        task = self.cancel_task(task_id)
        if not task:
            error = A2AError.TASK_NOT_FOUND if task_id not in self._tasks else A2AError.TASK_NOT_CANCELABLE
            return JSONRPCResponse(id=req_id, error=error).to_dict()
        return JSONRPCResponse(id=req_id, result=task.to_dict()).to_dict()
