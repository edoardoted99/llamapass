import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import httpx

from llamapass_cli.config import load


class ProxyHandler(BaseHTTPRequestHandler):
    upstream_url = ""
    api_key = ""

    def do_request(self):
        # Ollama checks HEAD / or GET / to verify server is alive
        if self.path == "/" and self.command in ("HEAD", "GET"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            if self.command == "GET":
                self.wfile.write(b"Ollama is running")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else None

        # Forward headers, inject auth
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for key, value in self.headers.items():
            if key.lower() in ("host", "authorization"):
                continue
            headers[key] = value

        target = f"{self.upstream_url}{self.path}"

        try:
            with httpx.stream(
                self.command, target,
                headers=headers, content=body, timeout=None,
            ) as resp:
                self.send_response(resp.status_code)
                for key, value in resp.headers.items():
                    if key.lower() in ("transfer-encoding", "content-encoding"):
                        continue
                    self.send_header(key, value)
                self.send_header("Connection", "close")
                self.end_headers()
                for chunk in resp.iter_bytes():
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except httpx.ConnectError:
            self.send_error(502, "Cannot connect to LlamaPass server")
        except BrokenPipeError:
            pass

    do_GET = do_request
    do_POST = do_request
    do_PUT = do_request
    do_DELETE = do_request
    do_PATCH = do_request
    do_HEAD = do_request

    def log_message(self, format, *args):
        import os
        if os.environ.get("LLAMAPASS_DEBUG"):
            import sys
            print(format % args, file=sys.stderr)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_proxy():
    cfg = load()
    url = cfg["url"].rstrip("/")
    api_key = cfg.get("api_key", "")

    if not api_key:
        return None, None

    ProxyHandler.upstream_url = f"{url}/ollama"
    ProxyHandler.api_key = api_key

    port = find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), ProxyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port
