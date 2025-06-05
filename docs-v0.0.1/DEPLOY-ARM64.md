# M-FastGate ARM64 部署指南

## 📋 概述

此项目专门为 ARM64 架构优化，包含完整的容器化部署方案。

## 🏗️ 架构要求

- **目标平台**: ARM64 (aarch64)
- **开发平台**: AMD64 (仅开发，不用于部署)
- **容器引擎**: Docker + Docker Compose

## 📦 文件说明

```
.
├── Dockerfile                # ARM64 专用容器镜像
├── docker-compose.yml       # 容器编排配置
├── deploy-arm64.sh          # 自动部署脚本
├── config/production.yaml   # 生产环境配置
└── .dockerignore            # 容器构建排除文件
```

## 🚀 部署步骤

### 方式一：自动部署（推荐）

1. **将项目传输到 ARM64 机器**
   ```bash
   # 打包项目
   tar -czf m-fastgate.tar.gz --exclude='.git' --exclude='data' --exclude='logs' .
   
   # 传输到 ARM64 机器
   scp m-fastgate.tar.gz user@arm64-server:/path/to/deploy/
   
   # 在 ARM64 机器上解压
   tar -xzf m-fastgate.tar.gz
   ```

2. **运行部署脚本**
   ```bash
   chmod +x deploy-arm64.sh
   ./deploy-arm64.sh
   ```

### 方式二：手动部署

1. **环境检查**
   ```bash
   # 检查架构
   uname -m  # 应该显示 aarch64 或 arm64
   
   # 检查 Docker
   docker --version
   docker-compose --version
   ```

2. **创建目录**
   ```bash
   mkdir -p data logs
   ```

3. **构建和启动**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

4. **验证部署**
   ```bash
   curl http://localhost:8514/health
   ```

## 🔧 配置说明

### 生产环境配置

编辑 `config/production.yaml` 文件：

```yaml
# 关键配置项
security:
  admin_token: "your_secure_admin_token"  # 修改为安全的管理员令牌

api_gateway:
  real_api_key: "your_production_api_key"  # 修改为生产环境API密钥

model_routing:
  auth:
    app_key: "your_cloud_proxy_app_key"  # 修改为云端代理应用密钥
```

### 环境变量

可通过 Docker Compose 的环境变量覆盖配置：

```yaml
environment:
  - ADMIN_TOKEN=your_secure_token
  - API_KEY=your_production_key
  - APP_KEY=your_app_key
```

## 📊 服务访问

部署成功后，可访问以下地址：

- **主服务**: http://localhost:8514
- **健康检查**: http://localhost:8514/health
- **API 文档**: http://localhost:8514/docs
- **管理界面**: http://localhost:8514/admin/ui

## 🔍 故障排查

### 查看日志
```bash
# 查看容器日志
docker-compose logs -f

# 查看应用日志
docker-compose exec m-fastgate tail -f logs/fastgate.log
```

### 检查服务状态
```bash
# 检查容器状态
docker-compose ps

# 检查健康状态
curl -v http://localhost:8514/health
```

### 重启服务
```bash
# 重启容器
docker-compose restart

# 完全重建
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 🛡️ 安全建议

1. **修改默认密钥**: 确保修改所有默认的 token 和 key
2. **网络安全**: 在生产环境中配置防火墙规则
3. **日志管理**: 定期清理和备份日志文件
4. **数据备份**: 定期备份 `data/` 目录中的数据库

## 📈 性能优化

1. **资源限制**: 根据需要在 docker-compose.yml 中添加资源限制
2. **数据库优化**: 考虑使用外部数据库（如 PostgreSQL）替代 SQLite
3. **负载均衡**: 在高负载场景下配置多实例部署

## ⚠️ 注意事项

- **架构限制**: 此配置仅适用于 ARM64 架构
- **跨平台构建**: 在 AMD64 开发机器上无法直接构建镜像
- **数据持久化**: 确保 `data/` 和 `logs/` 目录的持久化存储
- **端口冲突**: 确保 8514 端口未被其他服务占用 