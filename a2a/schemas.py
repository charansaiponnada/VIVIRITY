"""
a2a/schemas.py
--------------
Google A2A (Agent-to-Agent) Protocol data models.

Implements the open protocol specification for inter-agent communication:
- JSON-RPC 2.0 message envelope
- Task lifecycle (submitted → working → input-required → completed → failed)
- Agent Card discovery (/.well-known/agent.json)
- Artifact and Part types for structured content exchange
- SSE streaming support via SendTask / StreamTask

Reference: https://google.github.io/A2A/
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
import uuid
import time


# ── Task States (A2A spec) ─────────────────────────────────────────────── #

class TaskState(str, Enum):
    SUBMITTED      = "submitted"
    WORKING        = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED      = "completed"
    FAILED         = "failed"
    CANCELED       = "canceled"


# ── Part types for multi-modal content ─────────────────────────────────── #

@dataclass
class TextPart:
    text: str
    type: str = "text"

@dataclass
class DataPart:
    data: dict
    type: str = "data"

@dataclass
class FilePart:
    file_uri: str
    mime_type: str = "application/octet-stream"
    type: str = "file"


# ── Message ────────────────────────────────────────────────────────────── #

@dataclass
class Message:
    role: str                        # "user" or "agent"
    parts: list[dict]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Artifact (output produced by an agent) ─────────────────────────────── #

@dataclass
class Artifact:
    name: str
    parts: list[dict]
    description: str = ""
    index: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Task ───────────────────────────────────────────────────────────────── #

@dataclass
class TaskStatus:
    state: TaskState
    message: Message | None = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> dict:
        d = {"state": self.state.value, "timestamp": self.timestamp}
        if self.message:
            d["message"] = self.message.to_dict()
        return d


@dataclass
class Task:
    id: str
    status: TaskStatus
    messages: list[Message] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    session_id: str = ""

    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "status": self.status.to_dict(),
            "messages": [m.to_dict() for m in self.messages],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "metadata": self.metadata,
        }


# ── Agent Card (/.well-known/agent.json) ──────────────────────────────── #

@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentCapabilities:
    streaming: bool = True
    push_notifications: bool = False
    state_transition_history: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentCard:
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    skills: list[AgentSkill] = field(default_factory=list)
    default_input_modes: list[str] = field(default_factory=lambda: ["text/plain", "application/json"])
    default_output_modes: list[str] = field(default_factory=lambda: ["text/plain", "application/json"])
    provider: dict = field(default_factory=lambda: {"organization": "DOMINIX", "url": ""})
    authentication: dict = field(default_factory=lambda: {"schemes": ["bearer"]})

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities.to_dict(),
            "skills": [s.to_dict() for s in self.skills],
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
            "provider": self.provider,
            "authentication": self.authentication,
        }
        return d


# ── JSON-RPC 2.0 Envelope ─────────────────────────────────────────────── #

@dataclass
class JSONRPCRequest:
    method: str
    params: dict
    id: str = ""
    jsonrpc: str = "2.0"

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
            "id": self.id,
        }


@dataclass
class JSONRPCResponse:
    id: str
    result: Any = None
    error: dict | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict:
        d = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d


# ── JSON-RPC Error codes (A2A spec) ───────────────────────────────────── #

class A2AError:
    TASK_NOT_FOUND     = {"code": -32001, "message": "Task not found"}
    INVALID_REQUEST    = {"code": -32600, "message": "Invalid request"}
    METHOD_NOT_FOUND   = {"code": -32601, "message": "Method not found"}
    INVALID_PARAMS     = {"code": -32602, "message": "Invalid params"}
    INTERNAL_ERROR     = {"code": -32603, "message": "Internal error"}
    TASK_NOT_CANCELABLE = {"code": -32002, "message": "Task cannot be canceled"}


# ── Helper factories ──────────────────────────────────────────────────── #

def create_task(user_message: str, metadata: dict = None) -> Task:
    """Create a new task with initial user message."""
    msg = Message(role="user", parts=[{"type": "text", "text": user_message}])
    status = TaskStatus(state=TaskState.SUBMITTED)
    return Task(
        id=str(uuid.uuid4()),
        status=status,
        messages=[msg],
        metadata=metadata or {},
    )


def create_agent_message(text: str) -> Message:
    """Create an agent response message."""
    return Message(role="agent", parts=[{"type": "text", "text": text}])


def create_data_artifact(name: str, data: dict, description: str = "") -> Artifact:
    """Create an artifact containing structured data."""
    return Artifact(
        name=name,
        parts=[{"type": "data", "data": data}],
        description=description,
    )
