from pathlib import Path

from dotenv import load_dotenv

# Os testes live leem ANTHROPIC_API_KEY no import; carregar antes da coleta.
load_dotenv(Path(__file__).parent.parent / ".env")
