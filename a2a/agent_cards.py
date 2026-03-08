"""
a2a/agent_cards.py
------------------
Agent Card definitions for all Intelli-Credit agents.

Each agent exposes a /.well-known/agent.json card describing its capabilities,
input/output modes, and skills — per the Google A2A open protocol.
"""

from .schemas import AgentCard, AgentSkill, AgentCapabilities


def _card(name: str, description: str, skills: list[AgentSkill],
          url_path: str, streaming: bool = True) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        url=f"http://localhost:5000/a2a/{url_path}",
        capabilities=AgentCapabilities(streaming=streaming),
        skills=skills,
    )


# ── Individual Agent Cards ─────────────────────────────────────────────── #

AGENT_CARDS: dict[str, AgentCard] = {
    "document_classifier": _card(
        name="Document Classifier Agent",
        description="Classifies uploaded financial documents (annual reports, GST filings, bank statements, CIBIL reports, rating reports, legal notices).",
        url_path="document_classifier",
        streaming=False,
        skills=[AgentSkill(
            id="classify_document",
            name="Classify Financial Document",
            description="Determines document type from PDF/JSON/CSV content using keyword matching.",
            tags=["classification", "pdf", "financial"],
            examples=["Classify this annual report PDF", "What type of document is this?"],
        )],
    ),
    "ingestor": _card(
        name="Data Ingestor Agent",
        description="Extracts structured financial data from documents using VectorLess RAG and Gemini AI. Handles PDFs (with OCR fallback), JSON (GST/CIBIL), and CSV (bank statements).",
        url_path="ingestor",
        skills=[AgentSkill(
            id="ingest_documents",
            name="Ingest Financial Documents",
            description="Parses and extracts financial metrics, ratios, red flags from multi-format documents.",
            tags=["extraction", "financial", "ocr", "rag"],
            examples=["Extract financials from this annual report", "Parse this GST filing"],
        )],
    ),
    "cross_reference": _card(
        name="Cross-Reference Agent",
        description="Detects fraud and inconsistencies by cross-referencing multiple financial documents (annual report vs GST vs bank statement).",
        url_path="cross_reference",
        streaming=False,
        skills=[AgentSkill(
            id="cross_reference_documents",
            name="Cross-Reference Documents",
            description="Compares revenue, ITC, and cash flows across documents to detect circular trading, revenue inflation, and fake ITC claims.",
            tags=["fraud", "cross-reference", "gst", "banking"],
            examples=["Check for revenue mismatches between AR and GST"],
        )],
    ),
    "research": _card(
        name="Research Agent",
        description="Gathers external intelligence via web search: company news, promoter background, MCA filings, litigation, regulatory actions, credit ratings.",
        url_path="research",
        skills=[AgentSkill(
            id="research_company",
            name="Research Company Intelligence",
            description="Searches 5 intelligence domains (news, promoter, MCA, litigation, regulatory) and synthesises findings via Gemini.",
            tags=["research", "news", "litigation", "mca", "regulatory"],
            examples=["Research Tata Motors for credit appraisal"],
        )],
    ),
    "scoring": _card(
        name="Scoring Agent",
        description="Computes credit score using Five Cs framework, penalty engine, ML model blending, and generates lending recommendation with loan sizing.",
        url_path="scoring",
        skills=[
            AgentSkill(
                id="score_five_cs",
                name="Score Five Cs of Credit",
                description="Evaluates Character, Capacity, Capital, Collateral, Conditions using Gemini with ratio-anchored floors.",
                tags=["scoring", "five-cs", "credit"],
            ),
            AgentSkill(
                id="generate_recommendation",
                name="Generate Lending Recommendation",
                description="Produces APPROVE/CONDITIONAL/REJECT decision with calibrated loan amount, interest rate, and dynamic tenure.",
                tags=["recommendation", "lending", "decision"],
            ),
        ],
    ),
    "cam_generator": _card(
        name="CAM Generator Agent",
        description="Generates professional Credit Appraisal Memorandum as Word document with all analysis sections.",
        url_path="cam_generator",
        streaming=False,
        skills=[AgentSkill(
            id="generate_cam",
            name="Generate Credit Appraisal Memo",
            description="Creates formatted .docx CAM with executive summary, financials, Five Cs, research, cross-reference, and recommendation.",
            tags=["document", "cam", "word", "report"],
            examples=["Generate CAM for the scored company"],
        )],
    ),
}


def get_orchestrator_card() -> AgentCard:
    """Return the top-level orchestrator agent card."""
    child_skills = []
    for card in AGENT_CARDS.values():
        child_skills.extend(card.skills)

    return AgentCard(
        name="Intelli-Credit Orchestrator",
        description=(
            "AI-powered corporate credit appraisal engine. Orchestrates 6 specialised agents "
            "to analyse financial documents, research public intelligence, score creditworthiness, "
            "and generate Credit Appraisal Memos for Indian NBFC lending decisions."
        ),
        url="http://localhost:5000/a2a",
        capabilities=AgentCapabilities(streaming=True, state_transition_history=True),
        skills=child_skills,
        provider={"organization": "DOMINIX", "url": ""},
    )
