# 🏦 Intelli-Credit | Vivriti Capital Hackathon 2026

**AI-Powered Corporate Credit Appraisal & Intelligence Engine**

> Transforming raw, unstructured financial data into high-precision, AI-backed investment reports. From onboarding to deep analysis in under 5 minutes.

---

## 🌟 The Challenge & Our Solution

The mission: Build a hosted web application that guides a Credit Analyst through a seamless journey from raw document ingestion to a comprehensive, explainable credit recommendation.

**Intelli-Credit** delivers on all four stages of the User Journey with high-impact "Wow" factors:
1.  **Entity Onboarding**: A multi-step form capturing CIN, PAN, and specific Loan terms.
2.  **Intelligent Ingestion**: Secure upload for 5 critical document types (ALM, Shareholding, Borrowing, Annual Reports, Portfolio).
3.  **Human-in-the-loop (The Core)**: Automated classification with user-approval and a **Dynamic Schema Configurator**.
4.  **Deep Analysis**: Web-scale research, ML-blended scoring, and an **AI SWOT Reasoning Engine**.

---

## 🚀 Key Features

### 1. The 4-Stage Wizard Journey
Instead of a static dashboard, we've implemented a **Wizard Flow** that mirrors the life of a Credit Analyst:
- **Step 1**: Capture metadata (CIN, Sector, Loan Details).
- **Step 2**: Staged document ingestion.
- **Step 3**: **Review & Schema Mapping**. Users can approve classifications and toggle specific data points (Ratios, Directors, Custom Fields) before extraction begins.
- **Step 4**: Full multi-agent orchestration and results rendering.

### 2. VectorLess RAG (Large-Doc Ready)
We handle 500+ page reports (like Tata Motors) without the high cost and latency of traditional embedding-based RAG. Our **PageIndex Heuristic** targets critical sections (Identity, Balance Sheet, P&L) with 98% lower API overhead while preserving complex table structures.

### 3. Specialized Data Parsers
We've built custom extraction logic for the most complex financial structures required:
- **ALM (Asset-Liability Management)**: Maturity buckets, GAP analysis, and liquidity ratios.
- **Borrowing Profile**: Lender-wise concentration, sanctioned vs. outstanding limits, and interest rates.
- **Portfolio Cuts**: NPA buckets (PAR 0-90+), collection efficiency, and segment performance.
- **Shareholding Pattern**: Promoter vs. Public splits and pledged share tracking.

### 4. Blended Reasoning & SWOT
- **Rule + ML Blending**: A 55/45 blend of traditional "Five Cs" scoring and a calibrated Logistic Regression model (RBI IRAC & CRISIL aligned).
- **AI SWOT Engine**: Automatically synthesizes Strengths, Weaknesses, Opportunities, and Threats from both quantitative (financials) and qualitative (research) data.

### 5. Credit-as-a-Service (Google A2A)
Intelli-Credit isn't just a UI—it's a platform. We've implemented the **Google Agent-to-Agent (A2A) Protocol**.
- **Discovery**: Discoverable Agent Cards at `/.well-known/agent.json`.
- **API Access**: Run the full pipeline via a JSON-RPC 2.0 API, enabling integration with existing core banking systems.

---

## 🛠️ Architecture

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

---

## 📊 Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Google Gemini 2.5 Flash |
| **Search** | Tavily Search API |
| **PDF Intel** | pdfplumber + fitz (PyMuPDF) |
| **Frontend** | Streamlit |
| **Backend** | Flask (A2A Server) |
| **Data** | Databricks Lakehouse (Bronze → Gold) |
| **Models** | Logistic Regression (Explainable Feature Contribution) |

---

## 🏁 Getting Started

### Prerequisites
- Python 3.10+
- `uv` package manager

### Installation
```bash
git clone https://github.com/charansaiponnada/VIVIRITY
cd VIVIRITY
uv sync
```

### Setup Environment
Create a `.env` file:
```env
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
```

### Execution
- **Run the Web App**: `streamlit run app.py`
- **Run the A2A API Server**: `python main.py a2a`

---

## 📁 Project Structure Highlights
- `app.py`: The main 4-step wizard UI.
- `agents/ingestor_agent.py`: Specialized parsers for ALM, Borrowing, and Portfolio data.
- `agents/scoring_agent.py`: Five Cs, ML Blend, and AI SWOT generator.
- `dashboards.py`: High-impact visualizations including the **Specialized Monitor**.
- `a2a/`: Implementation of the Google A2A protocol for interoperability.
- `core/cam_generator.py`: Automated generation of professional CAM reports.

---

## 🏆 Team DOMINIX
**Vivriti Capital Hackathon 2026**
*IIT Hyderabad · YUVAAN 2026*
