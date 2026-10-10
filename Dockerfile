FROM python:3.12-slim AS builder

WORKDIR /app

# 构建依赖
COPY pyproject.toml ./
COPY README.md ./

# 安装 Python 依赖
RUN pip install --no-cache-dir --prefix=/install . 2>/dev/null || \
    pip install --no-cache-dir --prefix=/install --break-system-packages . 2>/dev/null || true

# 兜底核心依赖
RUN pip install --no-cache-dir --prefix=/install click pyyaml websockets 2>/dev/null || true

# ─────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="Upstream <https://gitee.com/yongwanxing>"
LABEL description="AstrumShell — 一切皆为插件的开发者工具运行时框架"

WORKDIR /app

# 复制依赖
COPY --from=builder /install /usr/local

# 复制项目文件
COPY oss/ ./oss/
COPY store/ ./store/
COPY data/ ./data/
COPY start.sh ./start.sh
COPY pyproject.toml ./pyproject.toml
COPY README.md ./README.md

# 创建必要目录
RUN mkdir -p /app/data/html-render /app/data/web-toolkit /app/data/plugin-storage /app/data/DCIM /app/logs

# 暴露端口
EXPOSE 8080 8081 8082

# 健康检查
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 启动
CMD ["python", "-m", "oss.cli", "serve"]
