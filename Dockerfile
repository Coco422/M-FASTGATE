# 使用多阶段构建优化镜像大小
FROM python:3.12-slim as builder

# 设置工作目录
WORKDIR /build

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖到临时目录
RUN pip install --no-cache-dir --target /app-packages -r requirements.txt

# 最终阶段
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/src:/app-packages
ENV ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1

# 安装系统依赖（包括curl用于健康检查）
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从builder阶段复制已安装的Python包
COPY --from=builder /app-packages /app-packages

# 复制整个应用代码到源代码目录（包括templates、static等）
COPY app/ /src/app/

# 创建必要的目录 (config目录将通过volume挂载)
RUN mkdir -p /app/logs /app/data /app/config

# 创建符号链接，让app/templates和app/static指向正确位置
RUN ln -s /src/app /app/app

# 暴露端口
EXPOSE 8514

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8514/health || exit 1

# 启动命令 - 直接用root启动
CMD ["python", "-m", "app.main"] 