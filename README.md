# 🏦 Intelli-Credit

**AI-Powered Corporate Credit Appraisal Engine**

> Automates the end-to-end preparation of a Credit Appraisal Memo (CAM) — a process that takes credit managers weeks, completed in minutes.

---

## Problem

In the Indian corporate lending landscape, credit managers face a **Data Paradox** — more information than ever, yet weeks to process a single loan application. A typical credit appraisal involves:

- Parsing 300–600 page annual reports and financial statements
- Cross-checking GST filings against bank statements for fraud signals
- Researching promoter background, litigation history, and regulatory actions
- Synthesizing qualitative field observations with quantitative data
- Producing a structured Credit Appraisal Memo for approval committees

Each step is manual, slow, and prone to human bias. Early warning signals buried in unstructured text get missed.

---

## Solution

Intelli-Credit is a **multi-agent AI system** that ingests heterogeneous financial documents, performs automated web-scale secondary research, and synthesizes everything into an explainable credit decision — with a professionally formatted CAM output.

### Architecture

```
Multiple Documents Uploaded
           ↓
┌─────────────────────────────┐
│    DOCUMENT CLASSIFIER      │
│  Annual Report / GST /      │
│  Bank Statement / Legal /   │
│  Sanction Letter / Rating   │
└─────────────────────────────┘
           ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   FINANCIAL  │  │     GST      │  │     BANK     │
│   EXTRACTOR  │  │    AGENT     │  │  STATEMENT   │
│              │  │              │  │    AGENT     │
│ VectorLess   │  │ GSTR-1 vs 3B │  │ Credit vs    │
│ RAG on PDFs  │  │ GSTR-2A vs   │  │ GST revenue  │
│ PageIndex    │  │ 3B mismatch  │  │ reconcile    │
└──────────────┘  └──────────────┘  └──────────────┘
           ↓              ↓                ↓
┌─────────────────────────────────────────────────────┐
│              CROSS-REFERENCE ENGINE                 │
│  GST revenue vs Bank credits reconciliation         │
│  Annual Report revenue vs GST outward supplies      │
│  Circular trading pattern detection                 │
│  Related party transaction anomaly flags            │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│              RESEARCH AGENT                         │
│  Tavily web search: news, litigation, promoters     │
│  MCA filing signals, e-Courts lookup                │
│  RBI/SEBI regulatory action detection               │
│  Sector headwind analysis                           │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│              SCORING AGENT                          │
│  Five Cs of Credit: Character, Capacity,            │
│  Capital, Collateral, Conditions                    │
│  Weighted scoring with penalty system               │
│  Real-time re-scoring from field notes              │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│              CAM GENERATOR                          │
│  Professional Word document output                  │
│  Approve / Conditional Approve / Reject             │
│  Recommended amount, interest rate, tenure          │
│  Fully explainable with cited evidence              │
└─────────────────────────────────────────────────────┘
```

---

## Key Technical Decisions

### VectorLess RAG (PageIndex Approach)

Traditional RAG pipelines chunk documents into embeddings and perform cosine similarity search. This approach has two problems for financial documents:

1. **Table destruction** — chunking breaks row/column relationships in Balance Sheets and P&L statements
2. **Cost** — embedding 600 pages via an API adds latency and token cost per query

Our approach uses the **natural structure of financial PDFs** as the index. Each page is classified by its financial section (Balance Sheet, P&L, Directors Report, GST Schedule, etc.) using keyword pattern matching. Queries then retrieve the top-N structurally relevant pages rather than semantically similar chunks.

This means:
- Zero embedding API calls
- Preserved table structure for accurate financial extraction
- Section-aware retrieval (Balance Sheet query → Balance Sheet pages, not random chunks)
- Deterministic, auditable retrieval logic

### Document-Aware Multi-Agent Design

Each uploaded document is classified before processing. An Annual Report is routed to the financial extractor. A GST filing activates the GST reconciliation agent. A bank statement triggers the bank-GST cross-reference pipeline.

This means the system's intelligence **scales with the documents provided** — uploading just an annual report gives a standard analysis, while uploading an annual report + GST filing + bank statement activates cross-document fraud detection that a single-document system cannot perform.

### Cross-Document Intelligence

The most significant fraud signals in Indian corporate lending are found not within a single document, but in **inconsistencies across documents**:

- **GSTR-1 vs Bank Credits**: A company may report ₹500 Cr in GST outward supplies but show only ₹300 Cr in bank credits — a potential revenue inflation signal
- **Annual Report vs GST Revenue**: Discrepancies between reported turnover and GST filing data
- **Sanction Letter vs Balance Sheet Debt**: Undisclosed borrowings not reflected in the balance sheet

These cross-document checks are automated by the Cross-Reference Agent and fed directly into the scoring pipeline as penalty adjustments.

### Indian Context Sensitivity

The system is specifically calibrated for Indian corporate lending:

- **GSTR-2A vs GSTR-3B mismatch** detection (fake Input Tax Credit claims)
- **Circular trading** pattern identification
- **MCA21 signals**: Director disqualification, charge satisfaction defaults
- **DRT/NCLT proceedings** detection via web research
- **Wilful defaulter** automatic rejection (per RBI prudential norms)
- **Five Cs weighting** calibrated to Indian NBFC lending practices (Capacity 30%, Character 25%, Capital 20%, Collateral 15%, Conditions 10%)
- **Risk premium** mapped to Indian base rates (10.5% base + risk spread by rating)

### Cost Optimisation

| Component | Naive Approach | Our Approach | Saving |
|-----------|---------------|--------------|--------|
| PDF extraction | 1 API call per page (600 calls) | 1 call for top 8 targeted pages | ~98% |
| Embeddings | Vector DB + embedding API | Zero — structural page index | 100% |
| Research synthesis | 7 separate Gemini calls | 1 consolidated call | ~85% |
| Financial extraction | 5 separate Gemini calls | 1 structured JSON call | ~80% |
| Research caching | Re-queries same company | Session cache, no repeat calls | 100% on repeat |

**Total API calls per full analysis: 4 Gemini calls + 5 Tavily searches**

For a production deployment processing 1,000 loan applications per month, this architecture reduces LLM API costs by approximately 90% compared to a naive implementation — directly relevant to Vivriti Capital's operational cost structure.

---

## Three Pillars — Problem Statement Mapping

### Pillar 1: Data Ingestor

| Requirement | Implementation |
|-------------|----------------|
| Unstructured PDF parsing | pdfplumber + PyMuPDF with section-aware page classification |
| Scanned Indian PDFs | PyMuPDF OCR fallback for image-heavy pages |
| GST cross-leverage against bank statements | Cross-Reference Agent with GSTR-1/3B/2A reconciliation |
| Circular trading detection | Pattern matching + LLM analysis across GST and bank data |

### Pillar 2: Research Agent

| Requirement | Implementation |
|-------------|----------------|
| Web-scale secondary research | Tavily API with targeted Indian-context queries |
| Promoter background | Dedicated promoter research module with wilful defaulter check |
| Sector headwinds | RBI regulation and sector-specific news search |
| Litigation history | NCLT, DRT, e-Courts targeted search |
| Primary insight integration | Credit Officer portal with real-time score adjustment |

### Pillar 3: Recommendation Engine

| Requirement | Implementation |
|-------------|----------------|
| CAM generation | Professional Word document with 7 structured sections |
| Five Cs of Credit | Weighted scoring with individual rationale per C |
| Loan amount suggestion | Derived from score, rating, and manual note adjustments |
| Interest rate | Base rate (10.5%) + risk premium by rating band |
| Explainability | Every decision cites specific data points and evidence |

---

## Project Structure

```
intelli_credit/
├── app.py                          # Streamlit UI — full pipeline orchestration
├── agents/
│   ├── document_classifier.py      # Classifies PDFs by type before routing
│   ├── cross_reference_agent.py    # Cross-document fraud detection
│   ├── research_agent.py           # Web research + synthesis
│   └── scoring_agent.py            # Five Cs scoring + penalty engine
├── core/
│   ├── pdf_parser.py               # VectorLess RAG / PageIndex implementation
│   ├── financial_extractor.py      # Section-aware financial data extraction
│   └── cam_generator.py            # Professional Word CAM generation
├── prompts/
│   ├── ingestor/                   # Extraction prompts per document section
│   ├── research/                   # Research synthesis prompts
│   ├── scoring/                    # Five Cs and risk score prompts
│   └── cam/                        # CAM template prompt
├── utils/
│   ├── prompt_loader.py            # Loads and renders .md prompt templates
│   └── indian_context.py           # Indian lending context utilities
└── outputs/                        # Generated CAM documents
```

---

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
git clone https://github.com/charansaiponnada/VIVIRITY
cd VIVIRITY
uv sync
```

### API Keys

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
```

Get keys:
- Gemini: [aistudio.google.com](https://aistudio.google.com) (free tier available)
- Tavily: [tavily.com](https://tavily.com) (free tier: 1000 searches/month)

### Run

```bash
uv run streamlit run app.py
```

Open `http://localhost:8501`

---

## Usage

1. **Upload documents** — Annual report, GST filings, bank statements (multiple files enable cross-referencing)
2. **Enter company details** — Name, promoters, sector, loan amount and purpose
3. **Add field notes** — Qualitative observations from site visits or management interviews
4. **Run analysis** — All 6 agents execute sequentially, status visible in sidebar
5. **Review results** — Five Cs scores, cross-reference findings, research intelligence, decision rationale
6. **Download CAM** — Professional Word document ready for approval committee

---

## Example Output

For **Tata Motors Limited** with a ₹500 Cr working capital request:

- **Decision**: CONDITIONAL_APPROVE
- **Credit Score**: 53.5/100
- **Rating**: B
- **Recommended Amount**: ₹250 Cr (reduced due to JLR cyberattack impact)
- **Interest Rate**: 15.0% p.a. (Base 10.5% + Risk Premium 4.5%)
- **Tenure**: 24 months
- **Key Condition**: Detailed cyberattack recovery plan required within 30 days

The system identified the JLR cyberattack risk from web research, automatically penalised the score, and reduced the recommended loan amount — demonstrating real-time synthesis of external intelligence into credit decisions.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 2.5 Flash |
| Agent Framework | Google ADK pattern |
| PDF Intelligence | pdfplumber + PyMuPDF (VectorLess RAG) |
| Web Research | Tavily API |
| CAM Output | python-docx |
| UI | Streamlit |
| Prompt Management | Markdown prompt templates with variable substitution |

---

## Team

**DOMINIX**
Vivriti Capital Hackathon 2026 · IIT Hyderabad · YUVAAN 2026
