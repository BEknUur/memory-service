from memory_service.config import get_settings


class EmbeddingService:
    def __init__(self, client=None, model: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.openai_embed_model
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.client = client

    async def embed(self, text: str) -> list[float] | None:
        if not text.strip():
            return None

        if not self.api_key and self.client is None:
            return None

        client = self.client or self._build_client()
        try:
            response = await client.embeddings.create(model=self.model, input=text)
        except Exception:
            return None

        try:
            return list(response.data[0].embedding)
        except (AttributeError, IndexError, TypeError):
            return None

    def memory_text(self, key: str, value: str, evidence_quote: str | None = None) -> str:
        if evidence_quote:
            return f"{key}: {value}\nevidence: {evidence_quote}"
        return f"{key}: {value}"

    def _build_client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.api_key)
