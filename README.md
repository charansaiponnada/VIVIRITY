# Intelli-Credit

**AI-Powered Corporate Credit Appraisal Engine**

Transforming raw, unstructured financial data into high-precision, AI-backed investment reports. From onboarding to deep analysis in under 5 minutes.

---

## Award

🏆 **2nd Prize** - National Level AI/ML Hackathon by Vivriti Capital Limited at **IIT Hyderabad · YUVAAN 2026**.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Contributors](#contributors)
- [License](#license)

---

## Overview

Intelli-Credit is a hosted web application designed for Credit Analysts to seamlessly navigate from raw document ingestion to comprehensive, explainable credit recommendations. The platform implements a four-stage wizard journey that covers:

1. **Entity Onboarding** - Multi-step form capturing CIN, PAN, and specific loan terms
2. **Intelligent Ingestion** - Secure upload for 5 critical document types (ALM, Shareholding, Borrowing, Annual Reports, Portfolio)
3. **Human-in-the-Loop Review** - Automated classification with user approval and dynamic schema configuration
4. **Deep Analysis** - Web-scale research, ML-blended scoring, and AI-powered SWOT reasoning

---

## Features

### 4-Stage Wizard Journey

A dynamic wizard flow that mirrors the workflow of a Credit Analyst:

| Step | Description |
|------|-------------|
| 1 | Capture metadata (CIN, Sector, Loan Details) |
| 2 | Staged document ingestion |
| 3 | Review & Schema Mapping - Approve classifications and toggle specific data points before extraction |
| 4 | Full multi-agent orchestration and results rendering |

### VectorLess RAG

Handles 500+ page reports (e.g., Tata Motors) without traditional embedding-based RAG overhead:

- **PageIndex Heuristic** targets critical sections (Identity, Balance Sheet, P&L)
- 98% lower API overhead compared to standard RAG
- Preserves complex table structures

### Specialized Data Parsers

Custom extraction logic for complex financial structures:

- **ALM (Asset-Liability Management)**: Maturity buckets, GAP analysis, liquidity ratios
- **Borrowing Profile**: Lender-wise concentration, sanctioned vs. outstanding limits, interest rates
- **Portfolio Cuts**: NPA buckets (PAR 0-90+), collection efficiency, segment performance
- **Shareholding Pattern**: Promoter vs. Public splits, pledged share tracking

### Blended Reasoning & SWOT

- **Rule + ML Blending**: 55/45 blend of traditional Five Cs scoring and calibrated Logistic Regression model (RBI IRAC & CRISIL aligned)
- **AI SWOT Engine**: Automatically synthesizes Strengths, Weaknesses, Opportunities, and Threats from quantitative and qualitative data

### Credit-as-a-Service (Google A2A)

Intelli-Credit operates as a platform with Google Agent-to-Agent (A2A) Protocol support:

- **Discovery**: Discoverable Agent Cards at `/.well-known/agent.json`
- **API Access**: Full pipeline execution via JSON-RPC 2.0 API for core banking system integration

---

## Architecture

```
User → Streamlit Wizard (app.py)
           ↓
┌─────────────────────────────────────────────────────┐
│              MULTI-AGENT ORCHESTRATOR               │
├──────────────────┬──────────────────┬───────────────┤
│ Ingestor Agent   │ Research Agent   │ Scoring Agent │
│ (Specialized)    │ (Tavily 360°)    │ (SWOT & ML)   │
└─────────┬────────┴─────────┬────────┴───────┬───────┘
          ↓                  ↓                ↓
   Specialized Docs    MCA/News/Legal    Five Cs + ML
   (ALM, Portfolio)    Signals           Blended Score
          ↓                  ↓                ↓
          └──────────┬───────┴────────────────┘
                     ↓
              CAM GENERATOR (python-docx)
              (Word / PDF / Audit JSON)
```

### Agent Responsibilities

| Agent | Function |
|-------|----------|
| **Ingestor Agent** | Parses specialized documents (ALM, Portfolio, Borrowing) |
| **Research Agent** | Performs web-scale research using Tavily API for MCA/News/Legal signals |
| **Scoring Agent** | Applies Five Cs methodology and ML models for blended credit scoring |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Google Gemini 2.5 Flash |
| **Search** | Tavily Search API |
| **PDF Processing** | pdfplumber + fitz (PyMuPDF) |
| **Frontend** | Streamlit |
| **Backend** | Flask (A2A Server) |
| **Data** | Databricks Lakehouse (Bronze → Gold) |
| **ML Models** | Logistic Regression (Explainable Feature Contribution) |
| **Package Manager** | uv |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- `uv` package manager
- API keys for Gemini and Tavily

### Installation

```bash
# Clone the repository
git clone https://github.com/charansaiponnada/VIVIRITY
cd VIVIRITY

# Install dependencies
uv sync
```

### Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
```

### Running the Application

**Web Application:**
```bash
streamlit run app.py
```

**A2A API Server:**
```bash
python main.py a2a
```

---

## Project Structure

```
VIVIRITY/
├── app.py                     # Main 4-step wizard UI
├── main.py                    # Application entry point
├── agents/
│   ├── ingestor_agent.py      # Specialized parsers (ALM, Borrowing, Portfolio)
│   ├── research_agent.py       # Web research using Tavily
│   └── scoring_agent.py        # Five Cs, ML blend, SWOT generation
├── core/
│   └── cam_generator.py        # Automated CAM report generation
├── dashboards.py               # Visualizations including Specialized Monitor
├── a2a/                        # Google A2A protocol implementation
├── .env                        # Environment variables (not committed)
└── README.md                   # Project documentation
```

---

## API Reference

### A2A Protocol Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent.json` | GET | Agent discovery card |
| `/a2a` | POST | JSON-RPC 2.0 API endpoint |

### Sample Request

```json
{
  "jsonrpc": "2.0",
  "method": "credit.assess",
  "params": {
    "entity_id": "CIN123456",
    "documents": ["base64_encoded_content"]
  },
  "id": 1
}
```

---

## Contributors

| Name | GitHub |
|------|--------|
| charansaiponnada | [@charansaiponnada](https://github.com/charansaiponnada) |
| neelimavana | [@neelimavana](https://github.com/neelimavana) |

---

## Recognition

Developed by **Team DOMINIX** for the **Vivriti Capital National Level AI/ML Hackathon 2026** held at **IIT Hyderabad**.

---

**Built with precision. Designed for confidence.**
