"""
a2a/server.py
-------------
A2A Protocol HTTP server using Flask.

Exposes JSON-RPC 2.0 endpoints per the Google A2A specification:
- POST /a2a                          → Orchestrator (full pipeline)
- POST /a2a/{agent_name}             → Individual agent
- GET  /.well-known/agent.json       → Orchestrator Agent Card
- GET  /a2a/{agent_name}/agent.json  → Individual Agent Card

Supports SSE streaming for long-running tasks via tasks/sendSubscribe.
"""

from __future__ import annotations
import os
import json
import time
import queue
import tempfile
import threading
from flask import Flask, request, jsonify, Response

from .schemas import (
    Task, TaskState, TaskStatus, Message, Artifact,
    JSONRPCResponse, A2AError,
    create_task, create_agent_message, create_data_artifact,
)
from .task_manager import TaskManager
from .agent_cards import AGENT_CARDS, get_orchestrator_card


app = Flask(__name__)
task_manager = TaskManager()


# ── Agent Card Endpoints ──────────────────────────────────────────────── #

@app.route("/.well-known/agent.json", methods=["GET"])
def orchestrator_agent_card():
    return jsonify(get_orchestrator_card().to_dict())


@app.route("/a2a/<agent_name>/agent.json", methods=["GET"])
def agent_card(agent_name: str):
    card = AGENT_CARDS.get(agent_name)
    if not card:
        return jsonify({"error": f"Agent '{agent_name}' not found"}), 404
    return jsonify(card.to_dict())


# ── JSON-RPC Endpoint (Orchestrator) ──────────────────────────────────── #

@app.route("/a2a", methods=["POST"])
def orchestrator_endpoint():
    """Handle A2A JSON-RPC requests for the orchestrator (full pipeline)."""
    data = request.get_json()
    if not data:
        return jsonify(JSONRPCResponse(
            id="", error=A2AError.INVALID_REQUEST
        ).to_dict()), 400

    method = data.get("method", "")

    # SSE streaming for sendSubscribe
    if method == "tasks/sendSubscribe":
        return _handle_sse_stream(data, _execute_orchestrator)

    result = task_manager.handle_jsonrpc(data, execute_fn=_execute_orchestrator)
    return jsonify(result)


# ── JSON-RPC Endpoint (Individual Agents) ─────────────────────────────── #

@app.route("/a2a/<agent_name>", methods=["POST"])
def agent_endpoint(agent_name: str):
    """Handle A2A JSON-RPC requests for individual agents."""
    if agent_name not in AGENT_CARDS:
        return jsonify(JSONRPCResponse(
            id=request.get_json().get("id", ""),
            error={"code": -32001, "message": f"Agent '{agent_name}' not found"},
        ).to_dict()), 404

    data = request.get_json()
    if not data:
        return jsonify(JSONRPCResponse(
            id="", error=A2AError.INVALID_REQUEST
        ).to_dict()), 400

    executor = _get_agent_executor(agent_name)
    result = task_manager.handle_jsonrpc(data, execute_fn=executor)
    return jsonify(result)


# ── SSE Streaming ─────────────────────────────────────────────────────── #

def _handle_sse_stream(data: dict, execute_fn) -> Response:
    """Stream task status updates via Server-Sent Events."""
    event_queue: queue.Queue = queue.Queue()
    req_id = data.get("id", "")
    params = data.get("params", {})
    message_data = params.get("message", {})
    text_parts = [p.get("text", "") for p in message_data.get("parts", []) if p.get("type") == "text"]
    user_text = " ".join(text_parts) or "Run credit analysis"

    task = create_task(user_text, metadata=params.get("metadata", {}))
    task_manager.create_task(task)

    def _run():
        try:
            task_manager.update_status(task.id, TaskState.WORKING,
                message=create_agent_message("Starting analysis pipeline..."))
            event_queue.put(("status", task_manager.get_task(task.id)))

            result_task = execute_fn(task)

            if result_task.status.state == TaskState.WORKING:
                task_manager.update_status(task.id, TaskState.COMPLETED,
                    message=create_agent_message("Analysis complete."))

            event_queue.put(("status", task_manager.get_task(task.id)))
            event_queue.put(("done", None))
        except Exception as e:
            task_manager.update_status(task.id, TaskState.FAILED,
                message=create_agent_message(f"Pipeline error: {e}"))
            event_queue.put(("status", task_manager.get_task(task.id)))
            event_queue.put(("done", None))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    def generate():
        while True:
            try:
                event_type, payload = event_queue.get(timeout=300)
                if event_type == "done":
                    yield f"event: close\ndata: {{}}\n\n"
                    break
                if payload:
                    yield f"event: status\ndata: {json.dumps(payload.to_dict())}\n\n"
            except queue.Empty:
                yield f"event: ping\ndata: {{}}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Agent Executors ───────────────────────────────────────────────────── #

def _get_user_text(task: Task) -> str:
    """Extract user text from task messages."""
    for msg in task.messages:
        if msg.role == "user":
            for part in msg.parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    return part.get("text", "")
    return ""


def _get_task_metadata(task: Task) -> dict:
    """Extract metadata from task."""
    return task.metadata or {}


def _execute_orchestrator(task: Task) -> Task:
    """Execute the full credit analysis pipeline as an A2A task."""
    metadata = _get_task_metadata(task)
    company_name = metadata.get("company_name", _get_user_text(task))
    file_paths = metadata.get("file_paths", [])
    sector = metadata.get("sector", "Manufacturing")
    promoters = metadata.get("promoters", "")
    manual_notes = metadata.get("manual_notes", "")
    loan_amount = metadata.get("loan_amount", "")
    loan_purpose = metadata.get("loan_purpose", "")

    results = {}
    try:
        from utils.indian_context import detect_entity_type
        pre_entity_type = detect_entity_type(company_name=company_name, cin="", sector_input=sector)
    except Exception:
        pre_entity_type = "corporate"

    # Step 1: Ingest documents
    task_manager.update_status(task.id, TaskState.WORKING,
        message=create_agent_message("Ingesting documents..."))
    if file_paths:
        try:
            from agents.ingestor_agent import IngestorAgent
            financials = IngestorAgent(file_paths=file_paths, entity_type=pre_entity_type).run()
            results["financials"] = financials
            task_manager.add_artifact(task.id, create_data_artifact(
                "financials", financials, "Extracted financial data"))
        except Exception as e:
            results["financials"] = {}
            task_manager.add_message(task.id, create_agent_message(f"Ingestor error: {e}"))
    else:
        results["financials"] = {}

    primary_fin = results["financials"].get("annual_report") or \
                  (results["financials"].get(list(results["financials"].keys())[0])
                   if results["financials"] else {})
    try:
        from utils.indian_context import detect_entity_type
        entity_type = detect_entity_type(
            company_name=company_name,
            cin=primary_fin.get("cin", "") if isinstance(primary_fin, dict) else "",
            sector_input=sector,
        )
        if isinstance(primary_fin, dict):
            primary_fin["_entity_type"] = entity_type
    except Exception:
        entity_type = "corporate"

    # Step 2: Cross-reference
    task_manager.update_status(task.id, TaskState.WORKING,
        message=create_agent_message("Cross-referencing documents..."))
    try:
        from agents.cross_reference_agent import CrossReferenceAgent
        if len(results["financials"]) >= 2:
            cross_ref = CrossReferenceAgent(documents=results["financials"]).run()
        else:
            cross_ref = {"cross_reference_performed": False, "reason": "Single document", "flags": []}
        results["cross_ref"] = cross_ref
        task_manager.add_artifact(task.id, create_data_artifact(
            "cross_reference", cross_ref, "Cross-reference fraud detection results"))
    except Exception as e:
        results["cross_ref"] = {"cross_reference_performed": False, "reason": str(e), "flags": []}

    # Step 3: Research
    task_manager.update_status(task.id, TaskState.WORKING,
        message=create_agent_message(f"Researching {company_name}..."))
    try:
        from agents.research_agent import ResearchAgent
        research = ResearchAgent(company_name=company_name, sector=sector, promoters=promoters).run()
        results["research"] = research
        task_manager.add_artifact(task.id, create_data_artifact(
            "research", research, "External intelligence"))
    except Exception as e:
        results["research"] = {}

    # Step 4: Scoring
    task_manager.update_status(task.id, TaskState.WORKING,
        message=create_agent_message("Computing credit score..."))
    try:
        from agents.scoring_agent import ScoringAgent
        sa = ScoringAgent(
            company_name=company_name,
            financials=primary_fin,
            research=results["research"],
            manual_notes=manual_notes,
            loan_purpose=loan_purpose,
            entity_type=entity_type,
        )
        scoring = sa.run()

        # ML blend
        try:
            from core.ml_credit_model import MLCreditModel
            ml_results = MLCreditModel().predict(primary_fin, results["research"], manual_notes)
            blend_rec = sa.generate_recommendation(scoring["five_cs"], scoring["risk_score"], ml_results=ml_results)
            scoring["recommendation"] = blend_rec
            scoring["ml_results"] = ml_results
        except Exception:
            pass

        results["scoring"] = scoring
        task_manager.add_artifact(task.id, create_data_artifact(
            "scoring", scoring, "Credit score and recommendation"))
    except Exception as e:
        results["scoring"] = {}

    # Step 5: CAM
    task_manager.update_status(task.id, TaskState.WORKING,
        message=create_agent_message("Generating Credit Appraisal Memo..."))
    try:
        from agents.cam_agent import CAMAgent
        cam_agent = CAMAgent(
            company_name=company_name, financials=primary_fin,
            research=results.get("research", {}),
            scoring=results.get("scoring", {}),
            cross_ref=results.get("cross_ref", {}),
            manual_notes=manual_notes,
            loan_amount=loan_amount, loan_purpose=loan_purpose,
            output_dir="outputs",
        )
        cam_path = cam_agent.run()
        results["cam_path"] = cam_path
        task_manager.add_artifact(task.id, Artifact(
            name="cam_document",
            parts=[{"type": "file", "file_uri": cam_path, "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}],
            description="Credit Appraisal Memorandum",
        ))
        if cam_agent.pdf_path:
            task_manager.add_artifact(task.id, Artifact(
                name="cam_document_pdf",
                parts=[{"type": "file", "file_uri": cam_agent.pdf_path, "mime_type": "application/pdf"}],
                description="Credit Appraisal Memorandum (PDF)",
            ))
    except Exception as e:
        results["cam_path"] = ""

    # Final summary
    rec = results.get("scoring", {}).get("recommendation", {})
    summary = (
        f"Analysis complete for {company_name}. "
        f"Decision: {rec.get('decision', 'N/A')} | "
        f"Score: {rec.get('final_score', 'N/A')}/100 | "
        f"Rating: {rec.get('rating', 'N/A')}"
    )
    task_manager.add_message(task.id, create_agent_message(summary))
    task_manager.update_status(task.id, TaskState.COMPLETED,
        message=create_agent_message(summary))

    return task_manager.get_task(task.id)


def _get_agent_executor(agent_name: str):
    """Return an executor function for a specific agent."""
    executors = {
        "ingestor": _execute_ingestor,
        "cross_reference": _execute_cross_reference,
        "research": _execute_research,
        "scoring": _execute_scoring,
        "cam_generator": _execute_cam,
        "document_classifier": _execute_classifier,
    }
    return executors.get(agent_name)


def _execute_ingestor(task: Task) -> Task:
    metadata = _get_task_metadata(task)
    file_paths = metadata.get("file_paths", [])
    if not file_paths:
        task_manager.update_status(task.id, TaskState.FAILED,
            message=create_agent_message("No file_paths provided in metadata."))
        return task_manager.get_task(task.id)

    from agents.ingestor_agent import IngestorAgent
    try:
        from utils.indian_context import detect_entity_type
        pre_entity_type = detect_entity_type(
            company_name=metadata.get("company_name", ""),
            cin="",
            sector_input=metadata.get("sector", ""),
        )
    except Exception:
        pre_entity_type = "corporate"

    result = IngestorAgent(file_paths=file_paths, entity_type=pre_entity_type).run()
    task_manager.add_artifact(task.id, create_data_artifact("financials", result))
    task_manager.update_status(task.id, TaskState.COMPLETED,
        message=create_agent_message(f"Ingested {len(result)} document type(s)."))
    return task_manager.get_task(task.id)


def _execute_cross_reference(task: Task) -> Task:
    metadata = _get_task_metadata(task)
    documents = metadata.get("documents", {})
    from agents.cross_reference_agent import CrossReferenceAgent
    result = CrossReferenceAgent(documents=documents).run()
    task_manager.add_artifact(task.id, create_data_artifact("cross_reference", result))
    task_manager.update_status(task.id, TaskState.COMPLETED)
    return task_manager.get_task(task.id)


def _execute_research(task: Task) -> Task:
    metadata = _get_task_metadata(task)
    company_name = metadata.get("company_name", _get_user_text(task))
    from agents.research_agent import ResearchAgent
    result = ResearchAgent(
        company_name=company_name,
        sector=metadata.get("sector", ""),
        promoters=metadata.get("promoters", ""),
    ).run()
    task_manager.add_artifact(task.id, create_data_artifact("research", result))
    task_manager.update_status(task.id, TaskState.COMPLETED,
        message=create_agent_message(f"Research complete for {company_name}."))
    return task_manager.get_task(task.id)


def _execute_scoring(task: Task) -> Task:
    metadata = _get_task_metadata(task)
    financials = metadata.get("financials", {})
    try:
        from utils.indian_context import detect_entity_type
        entity_type = detect_entity_type(
            company_name=metadata.get("company_name", ""),
            cin=financials.get("cin", "") if isinstance(financials, dict) else "",
            sector_input=metadata.get("sector", ""),
        )
        if isinstance(financials, dict):
            financials["_entity_type"] = entity_type
    except Exception:
        entity_type = "corporate"

    from agents.scoring_agent import ScoringAgent
    sa = ScoringAgent(
        company_name=metadata.get("company_name", ""),
        financials=financials,
        research=metadata.get("research", {}),
        manual_notes=metadata.get("manual_notes", ""),
        loan_purpose=metadata.get("loan_purpose", ""),
        entity_type=entity_type,
    )
    result = sa.run()
    task_manager.add_artifact(task.id, create_data_artifact("scoring", result))
    rec = result.get("recommendation", {})
    task_manager.update_status(task.id, TaskState.COMPLETED,
        message=create_agent_message(
            f"Score: {rec.get('final_score', 0)}/100 | Decision: {rec.get('decision', 'N/A')}"))
    return task_manager.get_task(task.id)


def _execute_cam(task: Task) -> Task:
    metadata = _get_task_metadata(task)
    from agents.cam_agent import CAMAgent
    cam_agent = CAMAgent(
        company_name=metadata.get("company_name", ""),
        financials=metadata.get("financials", {}),
        research=metadata.get("research", {}),
        scoring=metadata.get("scoring", {}),
        cross_ref=metadata.get("cross_ref", {}),
        manual_notes=metadata.get("manual_notes", ""),
        loan_amount=metadata.get("loan_amount", ""),
        loan_purpose=metadata.get("loan_purpose", ""),
        output_dir="outputs",
    )
    cam_path = cam_agent.run()
    task_manager.add_artifact(task.id, Artifact(
        name="cam_document",
        parts=[{"type": "file", "file_uri": cam_path}],
        description="Credit Appraisal Memorandum",
    ))
    if cam_agent.pdf_path:
        task_manager.add_artifact(task.id, Artifact(
            name="cam_document_pdf",
            parts=[{"type": "file", "file_uri": cam_agent.pdf_path, "mime_type": "application/pdf"}],
            description="Credit Appraisal Memorandum (PDF)",
        ))
    task_manager.update_status(task.id, TaskState.COMPLETED,
        message=create_agent_message(f"CAM generated: {cam_path}"))
    return task_manager.get_task(task.id)


def _execute_classifier(task: Task) -> Task:
    metadata = _get_task_metadata(task)
    file_path = metadata.get("file_path", "")
    if not file_path:
        task_manager.update_status(task.id, TaskState.FAILED,
            message=create_agent_message("No file_path provided."))
        return task_manager.get_task(task.id)

    import pdfplumber
    from agents.document_classifier import DocumentClassifier
    with pdfplumber.open(file_path) as pdf:
        doc_type = DocumentClassifier(pdf).classify()
    task_manager.add_artifact(task.id, create_data_artifact(
        "classification", {"document_type": doc_type}))
    task_manager.update_status(task.id, TaskState.COMPLETED,
        message=create_agent_message(f"Classified as: {doc_type}"))
    return task_manager.get_task(task.id)


# ── Entry point ───────────────────────────────────────────────────────── #

def run_a2a_server(host: str = "0.0.0.0", port: int = 5000):
    """Start the A2A protocol server."""
    print(f"[A2A] Starting server on {host}:{port}")
    print(f"[A2A] Agent Card: http://{host}:{port}/.well-known/agent.json")
    print(f"[A2A] Orchestrator: POST http://{host}:{port}/a2a")
    for name in AGENT_CARDS:
        print(f"[A2A]   Agent: POST http://{host}:{port}/a2a/{name}")
    app.run(host=host, port=port, debug=False)
