#!/bin/bash

# M-FastGate ARM64 部署脚本
# 适用于 ARM64 架构的服务器

set -e

echo "🚀 M-FastGate ARM64 部署脚本"
echo "================================"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "⚠️  docker-compose 未安装，尝试安装..."
    
    # 对于ARM64架构，使用pip安装
    if command -v pip3 &> /dev/null; then
        pip3 install docker-compose
    else
        echo "❌ 请手动安装 docker-compose"
        exit 1
    fi
fi

# 创建项目目录
PROJECT_DIR="/opt/m-fastgate"
echo "📁 创建项目目录: $PROJECT_DIR"
sudo mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 创建必要的目录
echo "📁 创建必要的目录..."
sudo mkdir -p {data,logs,config}

echo ""
echo "📋 目录结构说明："
echo "宿主机路径           => 容器内路径          => 用途"
echo "./data/             => /app/data/         => 数据库文件"
echo "./logs/             => /app/logs/         => 日志文件"
echo "./config/           => /app/config/       => 配置文件"
echo "                    => /src/app/          => 源代码"
echo ""

# 创建配置文件
echo "📝 创建配置文件..."
sudo tee config/config.yaml > /dev/null <<EOF
# M-FastGate v0.2.0 统一配置文件

app:
  name: "M-FastGate"
  version: "0.2.0"
  host: "0.0.0.0"
  port: 8514
  debug: false

database:
  # 容器内路径: /app/data/fastgate.db
  # 宿主机路径: ./data/fastgate.db (通过volume挂载)
  url: "sqlite:///./data/fastgate.db"
  echo: false

security:
  admin_token: "$(openssl rand -hex 16)"
  key_prefix: "fg_"
  default_expiry_days: 365

logging:
  level: "INFO"
  format: "json"
  # 容器内路径: /app/logs/fastgate.log
  # 宿主机路径: ./logs/fastgate.log (通过volume挂载)
  file: "logs/fastgate.log"

rate_limiting:
  enabled: true
  default_requests_per_minute: 100

proxy:
  timeout: 30
  max_retries: 3
  enable_streaming: true
  
  strip_headers:
    - "host"
    - "x-api-key" 
    - "authorization"
    - "x-forwarded-for"
    - "x-real-ip"
    - "x-source-path"
    - "user-agent"
    - "content-length"
  
  async_audit: true
  audit_full_request: true
  audit_full_response: true
EOF

# 创建docker-compose.yml
echo "🐳 创建 Docker Compose 配置..."
sudo tee docker-compose.yml > /dev/null <<EOF
services:
  m-fastgate:
    image: m-fastgate:arm64-latest
    container_name: m-fastgate
    restart: unless-stopped
    ports:
      - "8514:8514"
    volumes:
      # 数据库持久化 (宿主机:容器) - 使用bind mount
      - type: bind
        source: ./data
        target: /app/data
      # 日志持久化 (宿主机:容器) - 使用bind mount
      - type: bind
        source: ./logs
        target: /app/logs
      # 配置文件挂载 (宿主机:容器) - 使用bind mount
      - type: bind
        source: ./config
        target: /app/config
        read_only: true
    environment:
      - ENVIRONMENT=production
      - PYTHONUNBUFFERED=1
    networks:
      - fastgate-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8514/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  fastgate-network:
    driver: bridge
EOF

# 设置权限
echo "🔒 设置目录权限..."
sudo chown -R $(id -u):$(id -g) data logs config
sudo chmod -R 755 data logs config

echo ""
echo "✅ 部署脚本执行完成！"
echo ""
echo "📋 接下来的步骤："
echo "1. 将镜像文件 m-fastgate-arm64-latest.tar 上传到服务器"
echo "2. 运行以下命令导入镜像："
echo "   docker load -i m-fastgate-arm64-latest.tar"
echo ""
echo "3. 启动服务："
echo "   docker compose up -d"
echo ""
echo "4. 验证挂载 (重要!)："
echo "   docker compose exec m-fastgate ls -la /app/config/"
echo "   docker compose exec m-fastgate ls -la /app/data/"
echo "   docker compose exec m-fastgate ls -la /app/logs/"
echo ""
echo "5. 查看服务状态："
echo "   docker compose ps"
echo "   docker compose logs -f"
echo ""
echo "6. 访问管理界面："
echo "   http://your-server-ip:8514/admin/ui/?token=\$(grep admin_token config/config.yaml | cut -d' ' -f4 | tr -d '\"')"
echo ""
echo "📁 数据文件位置："
echo "   数据库: ./data/fastgate.db"
echo "   日志:   ./logs/fastgate.log"
echo "   配置:   ./config/config.yaml"
echo ""
echo "🎉 M-FastGate ARM64 部署完成！" 