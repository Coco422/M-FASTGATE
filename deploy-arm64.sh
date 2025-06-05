#!/bin/bash

# M-FastGate ARM64 部署脚本
# 此脚本需要在 ARM64 机器上运行

set -e

echo "🚀 M-FastGate ARM64 部署开始..."

# 检查架构
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ] && [ "$ARCH" != "arm64" ]; then
    echo "❌ 错误: 此脚本只能在 ARM64 架构上运行，当前架构: $ARCH"
    exit 1
fi

echo "✅ 架构检查通过: $ARCH"

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: Docker 未安装"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ 错误: Docker Compose 未安装"
    exit 1
fi

echo "✅ Docker 环境检查通过"

# 创建必要的目录
echo "📁 创建数据目录..."
mkdir -p data logs

# 停止现有容器
echo "🛑 停止现有容器..."
docker-compose down || true

# 构建镜像
echo "🔨 构建 ARM64 镜像..."
docker-compose build --no-cache

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 健康检查
echo "🔍 健康检查..."
for i in {1..30}; do
    if curl -f http://localhost:8514/health > /dev/null 2>&1; then
        echo "✅ 服务启动成功!"
        break
    fi
    echo "等待服务启动... ($i/30)"
    sleep 2
done

# 检查服务状态
if curl -f http://localhost:8514/health > /dev/null 2>&1; then
    echo ""
    echo "🎉 M-FastGate 部署成功!"
    echo "📊 服务信息:"
    echo "   - 访问地址: http://localhost:8514"
    echo "   - 健康检查: http://localhost:8514/health"
    echo "   - API 文档: http://localhost:8514/docs"
    echo "   - 管理界面: http://localhost:8514/admin/ui"
    echo ""
    echo "📋 容器状态:"
    docker-compose ps
else
    echo "❌ 服务启动失败，请检查日志:"
    echo "docker-compose logs"
    exit 1
fi 