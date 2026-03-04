import re
import os
from google import genai
from core.pdf_parser import PageIndexParser
from utils.prompt_loader import PromptLoader
from dotenv import load_dotenv

load_dotenv()


class FinancialExtractor:
    def __init__(self, parser: PageIndexParser):
        self.parser = parser
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-2.0-flash"

    def extract_all(self) -> dict:
        return {
            "basic_info": self.extract_basic_info(),
            "financials": self.extract_financials(),
            "debt_profile": self.extract_debt_profile(),
            "gst_analysis": self.extract_gst_data(),
            "red_flags": self.extract_red_flags(),
        }

    def extract_basic_info(self) -> dict:
        pages = self.parser.query("company name directors promoter CIN")
        if not pages:
            return {}
        text = "\n".join([p["text"] for p in pages[:2]])
        prompt = PromptLoader.load("ingestor", "basic_info", {"text": text[:3000]})
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return self._parse_json_response(response.text)

    def extract_financials(self) -> dict:
        pages = self.parser.query("revenue profit EBITDA balance sheet assets")
        if not pages:
            return {}
        text = "\n".join([p["text"] for p in pages[:3]])
        tables = []
        for p in pages[:3]:
            tables.extend(p.get("tables", []))
        table_text = self._tables_to_text(tables)
        prompt = PromptLoader.load("ingestor", "financials", {
            "text": text[:2000],
            "tables": table_text[:2000],
        })
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return self._parse_json_response(response.text)

    def extract_debt_profile(self) -> dict:
        pages = self.parser.query("borrowings loans debt collateral security")
        if not pages:
            return {}
        text = "\n".join([p["text"] for p in pages[:3]])
        prompt = PromptLoader.load("ingestor", "debt_profile", {"text": text[:3000]})
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return self._parse_json_response(response.text)

    def extract_gst_data(self) -> dict:
        pages = self.parser.query("GST GSTR tax indirect")
        if not pages:
            return {"gst_found": False}
        text = "\n".join([p["text"] for p in pages[:3]])
        prompt = PromptLoader.load("ingestor", "gst_analysis", {"text": text[:3000]})
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return self._parse_json_response(response.text)

    def extract_red_flags(self) -> dict:
        pages = self.parser.query("litigation legal dispute penalty fraud audit")
        if not pages:
            return {"red_flags": []}
        text = "\n".join([p["text"] for p in pages[:3]])
        prompt = PromptLoader.load("ingestor", "red_flags", {"text": text[:3000]})
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return self._parse_json_response(response.text)

    def _tables_to_text(self, tables: list) -> str:
        result = []
        for table in tables:
            if table:
                for row in table:
                    if row:
                        cleaned = [str(cell) if cell else "" for cell in row]
                        result.append(" | ".join(cleaned))
        return "\n".join(result)

    def _parse_json_response(self, text: str) -> dict:
        import json
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            return json.loads(text)
        except Exception:
            return {"raw_response": text, "parse_error": True}