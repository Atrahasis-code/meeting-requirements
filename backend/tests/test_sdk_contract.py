"""Inspect actual Codex Responses requests against a local rejecting server only."""

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox
from app.providers import analysis_output_schema, restricted_overrides


def test_codex_uses_streaming_without_storage_or_execution_tools(tmp_path, monkeypatch):
    captured = queue.Queue()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"models":[],"data":[]}')

        def do_POST(self):
            captured.put(
                (
                    self.headers.get("Authorization"),
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                )
            )
            payload = json.dumps(
                {
                    "error": {
                        "message": "Intentional local contract probe",
                        "type": "invalid_request_error",
                        "code": "probe",
                    }
                }
            ).encode()
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setenv("ACCESS_TOKEN", "synthetic-local-contract-token")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    options = tuple(
        option.replace("https://api.openai.com/v1", f"http://127.0.0.1:{server.server_port}/v1")
        for option in restricted_overrides()
    )
    try:
        try:
            with Codex(
                CodexConfig(
                    cwd=str(tmp_path),
                    config_overrides=options,
                    client_name="Meeting Requirements AI",
                    client_title="Meeting Requirements AI",
                    client_version="0.1.0",
                )
            ) as codex:
                thread = codex.thread_start(
                    model="local-contract-probe",
                    model_provider="openai_chatgpt_plan",
                    approval_mode=ApprovalMode.deny_all,
                    sandbox=Sandbox.read_only,
                    cwd=str(tmp_path),
                    ephemeral=True,
                )
                thread.run("Synthetic local contract probe", output_schema=analysis_output_schema())
        except RuntimeError:
            pass  # The local server intentionally rejects before performing inference.
        authorization, request = captured.get(timeout=5)
        assert authorization == "Bearer synthetic-local-contract-token"
        assert request["store"] is False
        assert request["stream"] is True
        assert request["text"]["format"]["type"] == "json_schema"
        names = {tool.get("name", tool.get("type")) for tool in request["tools"]}
        assert names <= {"request_user_input", "update_plan"}, names
        assert captured.empty(), "No automatic retry is permitted"
    finally:
        server.shutdown()
        server.server_close()
