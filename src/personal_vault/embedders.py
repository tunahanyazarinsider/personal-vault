import json
import urllib.error
import urllib.request
from typing import Protocol

from personal_vault.models import PersonalVaultError


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OpenAICompatibleEmbedder:
    def __init__(
        self,
        host: str,
        model: str,
        query_prefix: str = "",
        doc_prefix: str = "",
        api_key: str | None = None,
        timeout: float = 120.0,
        batch_size: int = 32,
    ):
        base = host.rstrip("/")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        self.url = base + "/v1/embeddings"
        self.model = model
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        self.api_key = api_key
        self.timeout = timeout
        self.batch_size = batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            batch = [self.doc_prefix + text for text in texts[start:start + self.batch_size]]
            vectors.extend(self._request(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._request([self.query_prefix + text])[0]

    def _request(self, texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps({"model": self.model, "input": texts}).encode()
        request = urllib.request.Request(self.url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:300]
            if error.code == 404:
                raise PersonalVaultError(
                    f"model '{self.model}' is not available at {self.url}: {detail}\n"
                    f"With Ollama, run: ollama pull {self.model}"
                ) from error
            raise PersonalVaultError(
                f"embedding server answered {error.code} for model '{self.model}': {detail}"
            ) from error
        except urllib.error.URLError as error:
            raise PersonalVaultError(
                f"cannot reach the embedding server at {self.url} ({error.reason}).\n"
                "Start it and try again. With Ollama: open the Ollama app (install: https://ollama.com)"
            ) from error
        except (OSError, ValueError) as error:
            raise PersonalVaultError(f"embedding request to {self.url} failed: {error}") from error
        return _vectors(payload, len(texts), self.url)


def _vectors(payload: object, expected: int, url: str) -> list[list[float]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or len(data) != expected:
        raise PersonalVaultError(f"unexpected response from {url}: {str(payload)[:300]}")
    items = sorted(data, key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0)
    vectors = []
    for item in items:
        vector = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(vector, list) or not vector:
            raise PersonalVaultError(f"response from {url} has an item without an embedding")
        vectors.append(vector)
    return vectors
