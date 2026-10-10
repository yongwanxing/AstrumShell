"""静态文件处理器"""
import os
import mimetypes
from pathlib import Path
from typing import Optional, Any

from oss.plugin.types import Response


class StaticFileHandler:
    """静态文件处理器"""

    def __init__(self, root: str = "./static"):
        self.root = root
        self._ensure_root()

    def _ensure_root(self):
        """确保静态目录存在"""
        Path(self.root).mkdir(parents=True, exist_ok=True)

    def set_root(self, path: str):
        """设置静态文件根目录"""
        self.root = path
        self._ensure_root()

    def serve(self, filename: str) -> Optional[Response]:
        """提供静态文件"""
        file_path = Path(self.root) / filename

        # 安全检查：防止目录遍历
        try:
            file_path.resolve().relative_to(Path(self.root).resolve())
        except ValueError:
            return Response(status=403, body="Forbidden")

        if not file_path.exists() or not file_path.is_file():
            return Response(status=404, body="File not found")

        # 检测 MIME 类型
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"

        # 读取文件内容
        try:
            if content_type.startswith("text/") or content_type in (
                "application/json", "application/javascript", "application/xml"
            ):
                content = file_path.read_text(encoding="utf-8")
            else:
                content = file_path.read_bytes()

            return Response(
                status=200,
                headers={
                    "Content-Type": content_type,
                    "Cache-Control": "public, max-age=3600",
                },
                body=content,
            )
        except Exception as e:
            return Response(status=500, body=f"Error reading file: {e}")

    def list_files(self) -> list[str]:
        """列出静态文件"""
        root_path = Path(self.root)
        if not root_path.exists():
            return []
        return [f.name for f in root_path.iterdir() if f.is_file()]
