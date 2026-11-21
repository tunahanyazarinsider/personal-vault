import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from personal_vault.embedders import OpenAICompatibleEmbedder
from personal_vault.models import PersonalVaultError


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if request["model"] == "missing":
            self._send(404, {"error": {"message": 'model "missing" not found, try pulling it first'}})
            return
        items = [
            {"index": index, "embedding": [float(len(text)), 1.0]}
            for index, text in enumerate(request["input"])
        ]
        self._send(200, {"data": list(reversed(items))})

    def _send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def host():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_vectors_come_back_in_input_order_with_prefixes_applied(host):
    embedder = OpenAICompatibleEmbedder(host + "/v1", "m", query_prefix="q: ", doc_prefix="doc: ", batch_size=2)
    assert embedder.embed_documents(["a", "bbb", "cc"]) == [[6.0, 1.0], [8.0, 1.0], [7.0, 1.0]]
    assert embedder.embed_query("a") == [4.0, 1.0]


def test_missing_model_says_how_to_pull_it(host):
    embedder = OpenAICompatibleEmbedder(host, "missing")
    with pytest.raises(PersonalVaultError, match="ollama pull missing"):
        embedder.embed_query("a")


def test_unreachable_server_names_the_url():
    embedder = OpenAICompatibleEmbedder("http://127.0.0.1:1", "m", timeout=2)
    with pytest.raises(PersonalVaultError, match="cannot reach the embedding server at http://127.0.0.1:1/v1"):
        embedder.embed_query("a")
