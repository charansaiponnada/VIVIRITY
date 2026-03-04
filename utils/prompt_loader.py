from pathlib import Path


class PromptLoader:
    """
    Loads and renders prompt templates from .md files.
    Supports variable substitution using {variable} syntax.
    """

    BASE_PATH = Path("prompts")

    @classmethod
    def load(cls, agent: str, prompt_name: str, variables: dict = None) -> str:
        """
        Load a prompt template and substitute variables.
        
        Usage:
            PromptLoader.load("ingestor", "basic_info", {"text": "..."})
            PromptLoader.load("research", "company_news", {"company": "Tata"})
        """
        path = cls.BASE_PATH / agent / f"{prompt_name}.md"

        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {path}")

        template = path.read_text(encoding="utf-8")

        if variables:
            for key, value in variables.items():
                template = template.replace(f"{{{key}}}", str(value))

        return template

    @classmethod
    def list_prompts(cls, agent: str) -> list:
        """List all available prompts for an agent"""
        path = cls.BASE_PATH / agent
        if not path.exists():
            return []
        return [f.stem for f in path.glob("*.md")]