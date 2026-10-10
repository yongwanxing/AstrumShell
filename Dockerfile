FROM python:3.12-slim AS builder

WORKDIR /app

# 安装阶段：只需要依赖声明与包源码
COPY pyproject.toml requirements.txt ./
COPY oss/ ./oss/
COPY README.md ./

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    pip install --no-cache-dir --prefix=/install --no-deps .

# ─────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="yongwanxing <https://github.com/yongwanxing>"
LABEL description="AstrumShell — 插件化运行时框架（一切皆插件）"

WORKDIR /app

# 复制已安装的依赖与包
COPY --from=builder /install /usr/local

# 运行所需文件（data/ 是运行期目录，由镜像内创建，不从仓库复制）
COPY oss/ ./oss/
COPY store/ ./store/
COPY main.py ./
COPY oss.config.json ./
COPY start.sh ./start.sh
COPY pyproject.toml ./
COPY README.md ./

# 创建运行期目录
RUN mkdir -p /app/data/html-render /app/data/web-toolkit /app/data/plugin-storage \
    /app/data/DCIM /app/data/pkg /app/logs \
    /app/data/signature-verifier/keys/private /app/data/signature-verifier/keys/public

# 暴露端口：8080 HTTP API + WebUI，8081 WebSocket，8082 HTTP over TCP
EXPOSE 8080 8081 8082

# 健康检查（用 Python 实现，slim 镜像里没有 curl）
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).status == 200 else 1)"

CMD ["python", "-m", "oss.cli", "serve"]

