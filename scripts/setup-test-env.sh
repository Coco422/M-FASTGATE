#!/bin/bash

# M-FastGate v0.2.0 测试环境初始化脚本
# 通过API调用设置网关密钥和代理路由

set -e

# 配置信息
GATEWAY_HOST="localhost:8514"
ADMIN_TOKEN=""  # 需要从配置文件中获取
BACKEND_API_KEY="sk-nsItInRUqh7KFKX8l3xVOvLVaRJQo1iNi6ALl6rBUjqTdgFc"
TARGET_HOST="172.16.99.204"
TARGET_PORT="3398"
MODEL_NAME="mckj/Qwen3-30B-A3B"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 输出函数
print_header() {
    echo -e "${BLUE}🚀 M-FastGate v0.2.0 测试环境初始化${NC}"
    echo "======================================================================"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

print_info() {
    echo -e "${BLUE}📋 $1${NC}"
}

# 获取管理员token
get_admin_token() {
    echo -e "${BLUE}🔑 获取管理员token...${NC}"
    
    # 尝试从配置文件读取
    if [ -f "config/config.yaml" ]; then
        ADMIN_TOKEN=$(grep "admin_token:" config/config.yaml | cut -d'"' -f2 | tr -d ' ')
        if [ -n "$ADMIN_TOKEN" ]; then
            print_success "从配置文件获取admin_token"
            return 0
        fi
    fi
    
    # 如果配置文件不存在或读取失败，提示用户输入
    echo "请输入管理员token (从config/config.yaml中的admin_token字段获取):"
    read -r ADMIN_TOKEN
    
    if [ -z "$ADMIN_TOKEN" ]; then
        print_error "管理员token不能为空"
    fi
}

# 等待服务启动
wait_for_service() {
    echo -e "${BLUE}⏳ 等待M-FastGate服务启动...${NC}"
    
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "http://${GATEWAY_HOST}/health" > /dev/null 2>&1; then
            print_success "M-FastGate服务已启动"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "等待服务启动超时"
}

# 创建API密钥
create_api_key() {
    echo -e "${BLUE}🔑 创建网关API密钥...${NC}"
    
    response=$(curl -s -X POST "http://${GATEWAY_HOST}/admin/keys?token=${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "source_path": "qwen3-30b-gateway",
            "permissions": ["chat.completions", "models.list"],
            "expires_days": 365,
            "rate_limit": 1000
        }' 2>/dev/null)
    
    # 检查curl命令是否成功
    if [ $? -ne 0 ]; then
        print_error "API请求失败"
    fi
    
    # 检查响应是否为空
    if [ -z "$response" ]; then
        print_error "API响应为空"
    fi
    
    # 调试：显示原始响应
    print_info "API响应: $response"
    
    # 检查响应是否包含错误
    if echo "$response" | grep -q '"detail"'; then
        error_msg=$(echo "$response" | grep -o '"detail":"[^"]*"' | cut -d'"' -f4)
        print_error "API错误: $error_msg"
    fi
    
    # 提取密钥值 - 改进JSON解析
    GATEWAY_KEY=""
    KEY_ID=""
    
    # 方法1：使用grep和cut
    GATEWAY_KEY=$(echo "$response" | grep -o '"key_value":"[^"]*"' | cut -d'"' -f4)
    KEY_ID=$(echo "$response" | grep -o '"key_id":"[^"]*"' | cut -d'"' -f4)
    
    # 如果方法1失败，尝试方法2：使用sed
    if [ -z "$GATEWAY_KEY" ]; then
        GATEWAY_KEY=$(echo "$response" | sed -n 's/.*"key_value":"\([^"]*\)".*/\1/p')
        KEY_ID=$(echo "$response" | sed -n 's/.*"key_id":"\([^"]*\)".*/\1/p')
    fi
    
    # 如果还是失败，尝试使用python的json模块（如果可用）
    if [ -z "$GATEWAY_KEY" ] && command -v python3 > /dev/null 2>&1; then
        GATEWAY_KEY=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('key_value', ''))" 2>/dev/null)
        KEY_ID=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('key_id', ''))" 2>/dev/null)
    fi
    
    if [ -z "$GATEWAY_KEY" ]; then
        print_error "无法从API响应中提取密钥值。响应: $response"
    fi
    
    print_success "创建网关API密钥成功"
    print_info "密钥ID: $KEY_ID"
    print_info "密钥值: $GATEWAY_KEY"
}

# 删除已存在的测试路由
delete_existing_routes() {
    echo -e "${BLUE}🗑️  删除已存在的测试路由...${NC}"
    
    # 获取所有路由
    routes=$(curl -s -X GET "http://${GATEWAY_HOST}/admin/routes?token=${ADMIN_TOKEN}" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$routes" ]; then
        # 提取qwen3-30b相关的路由ID
        route_ids=$(echo "$routes" | grep -o '"route_id":"qwen3-30b[^"]*"' | cut -d'"' -f4)
        
        for route_id in $route_ids; do
            curl -s -X DELETE "http://${GATEWAY_HOST}/admin/routes/${route_id}?token=${ADMIN_TOKEN}" > /dev/null 2>&1
            print_info "删除路由: $route_id"
        done
    fi
}

# 创建聊天完成路由
create_chat_route() {
    echo -e "${BLUE}🛣️  创建聊天完成路由...${NC}"
    
    response=$(curl -s -X POST "http://${GATEWAY_HOST}/admin/routes?token=${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "route_name": "Qwen3-30B Chat Completions",
            "description": "Qwen3-30B模型聊天完成接口 - '${TARGET_HOST}':'${TARGET_PORT}'",
            "match_path": "/v1/chat/completions",
            "match_method": "POST",
            "match_body_schema": {"model": "'${MODEL_NAME}'"},
            "target_host": "'${TARGET_HOST}':'${TARGET_PORT}'",
            "target_path": "/v1/chat/completions",
            "target_protocol": "http",
            "strip_path_prefix": false,
            "add_headers": {"Authorization": "Bearer '${BACKEND_API_KEY}'", "X-Proxy-Source": "M-FastGate-v0.2.0"},
            "add_body_fields": {"source": "fastgate"},
            "remove_headers": ["host"],
            "is_active": true,
            "priority": 100
        }' 2>/dev/null)
    
    # 调试：显示原始响应
    print_info "聊天路由API响应: $response"
    
    # 检查响应是否包含错误
    if echo "$response" | grep -q '"detail"'; then
        error_msg=$(echo "$response" | grep -o '"detail":"[^"]*"' | cut -d'"' -f4)
        print_error "创建聊天完成路由失败: $error_msg"
    fi
    
    if [ $? -ne 0 ]; then
        print_error "创建聊天完成路由失败"
    fi
    
    print_success "创建聊天完成路由成功"
}

# 创建通用API路由
create_general_route() {
    echo -e "${BLUE}🛣️  创建通用API路由...${NC}"
    
    response=$(curl -s -X POST "http://${GATEWAY_HOST}/admin/routes?token=${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "route_name": "Qwen3-30B General API",
            "description": "Qwen3-30B模型通用API代理 - '${TARGET_HOST}':'${TARGET_PORT}'",
            "match_path": "/v1/.*",
            "match_method": "ANY",
            "target_host": "'${TARGET_HOST}':'${TARGET_PORT}'",
            "target_path": "/v1/",
            "target_protocol": "http",
            "strip_path_prefix": true,
            "add_headers": {"Authorization": "Bearer '${BACKEND_API_KEY}'", "X-Proxy-Source": "M-FastGate-v0.2.0"},
            "remove_headers": ["host"],
            "is_active": true,
            "priority": 200
        }' 2>/dev/null)
    
    # 调试：显示原始响应
    print_info "通用路由API响应: $response"
    
    # 检查响应是否包含错误
    if echo "$response" | grep -q '"detail"'; then
        error_msg=$(echo "$response" | grep -o '"detail":"[^"]*"' | cut -d'"' -f4)
        print_error "创建通用API路由失败: $error_msg"
    fi
    
    if [ $? -ne 0 ]; then
        print_error "创建通用API路由失败"
    fi
    
    print_success "创建通用API路由成功"
}

# 验证配置
verify_setup() {
    echo -e "${BLUE}🔍 验证配置...${NC}"
    
    # 检查API密钥
    keys=$(curl -s -X GET "http://${GATEWAY_HOST}/admin/keys?token=${ADMIN_TOKEN}" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$keys" ]; then
        key_count=$(echo "$keys" | grep -o '"is_active":true' | wc -l | tr -d ' ')
        print_info "活跃API密钥数量: $key_count"
    fi
    
    # 检查代理路由
    routes=$(curl -s -X GET "http://${GATEWAY_HOST}/admin/routes?token=${ADMIN_TOKEN}" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$routes" ]; then
        route_count=$(echo "$routes" | grep -o '"is_active":true' | wc -l | tr -d ' ')
        print_info "活跃代理路由数量: $route_count"
        
        # 显示qwen3相关路由
        echo -e "${BLUE}📋 活跃的代理路由:${NC}"
        echo "$routes" | grep -A5 -B5 "qwen3-30b" | grep -E '"route_name"|"match_path"|"target_host"' | \
        sed 's/.*"route_name":"\([^"]*\)".*/   - \1/' | \
        sed 's/.*"match_path":"\([^"]*\)".*/     路径: \1/' | \
        sed 's/.*"target_host":"\([^"]*\)".*/     目标: http:\/\/\1/'
    fi
}

# 生成测试示例
generate_test_examples() {
    echo -e "${BLUE}📝 生成测试示例...${NC}"
    
    cat << EOF

🎉 测试环境初始化完成！
======================================================================
✅ 现在可以使用以下信息测试系统:
   🔑 网关API密钥: ${GATEWAY_KEY}
   🌍 请求URL: http://${GATEWAY_HOST}/v1/chat/completions
   🤖 模型名称: ${MODEL_NAME}
   🔧 后端服务: http://${TARGET_HOST}:${TARGET_PORT}/v1
   🔐 后端密钥: ${BACKEND_API_KEY:0:20}...

📝 测试请求示例:

# 基本聊天测试
curl -X POST http://${GATEWAY_HOST}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${GATEWAY_KEY}" \\
  -d '{
    "model": "${MODEL_NAME}",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "max_tokens": 100,
    "temperature": 0.7
  }'

# 流式聊天测试
curl -X POST http://${GATEWAY_HOST}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${GATEWAY_KEY}" \\
  -d '{
    "model": "${MODEL_NAME}",
    "messages": [
      {"role": "user", "content": "Tell me a short story"}
    ],
    "max_tokens": 200,
    "temperature": 0.7,
    "stream": true
  }'

📌 重要说明:
   - 用户使用网关密钥: ${GATEWAY_KEY}
   - 网关自动转换为后端密钥
   - 用户无需知道真实的后端API密钥

EOF
}

# 主函数
main() {
    print_header
    
    print_info "配置信息:"
    print_info "后端API密钥: ${BACKEND_API_KEY}"
    print_info "目标主机: ${TARGET_HOST}:${TARGET_PORT}"
    print_info "模型名称: ${MODEL_NAME}"
    echo "----------------------------------------------------------------------"
    
    get_admin_token
    wait_for_service
    create_api_key
    delete_existing_routes
    create_chat_route
    create_general_route
    verify_setup
    generate_test_examples
    
    print_success "🎉 M-FastGate测试环境初始化完成！"
}

# 执行主函数
main "$@" 