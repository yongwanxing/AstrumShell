"""HTTP 服务器核心"""
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from oss.config import get_config


class Request:
    """请求对象"""
    def __init__(self, method, path, headers, body):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body


class Response:
    """响应对象"""
    def __init__(self, status=200, headers=None, body=""):
        self.status = status
        self.headers = headers or {}
        self.body = body


class HttpServer:
    """HTTP 服务器"""

    def __init__(self, router, middleware, host=None, port=None):
        config = get_config()
        self.host = host or config.get("HOST", "0.0.0.0")
        self.port = port or config.get("HTTP_API_PORT", 8080)
        self.router = router
        self.middleware = middleware
        self._server = None
        self._thread = None

    def start(self):
        """启动服务器"""
        handler = self._create_handler()
        self._server = HTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"[http-api] 服务器启动: {self.host}:{self.port}")

    def stop(self):
        """停止服务器"""
        if self._server:
            self._server.shutdown()
            print("[http-api] 服务器已停止")

    def _create_handler(self):
        """创建请求处理器"""
        router = self.router
        middleware = self.middleware

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def do_PUT(self):
                self._handle("PUT")

            def do_DELETE(self):
                self._handle("DELETE")

            def do_OPTIONS(self):
                """处理 CORS 预检请求"""
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def _handle(self, method):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length else b""

                req = Request(
                    method=method,
                    path=self.path,
                    headers=dict(self.headers),
                    body=body.decode("utf-8")
                )

                # 执行中间件
                ctx = {"request": req, "response": None}
                result = middleware.run(ctx)
                if result:
                    self._send_response(result)
                    return

                # 路由匹配
                resp = router.handle(req)
                self._send_response(resp)

            def _send_response(self, resp: Response):
                try:
                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    if isinstance(resp.body, str):
                        self.wfile.write(resp.body.encode("utf-8"))
                    else:
                        self.wfile.write(resp.body)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    pass  # 忽略客户端断开

            def log_message(self, format, *args):
                pass

        return Handler
