#!/bin/bash

# M-FastGate v0.2.0 生产环境初始化脚本
# 配置多个API密钥和云天代理路由

# 注意：不使用 set -e，避免因为正常的空结果导致脚本退出

# 配置信息
GATEWAY_HOST="localhost:8514"
ADMIN_TOKEN=""  # 需要从配置文件中获取

# 云天代理配置
PROXY_HOST="10.101.32.14"
PROXY_PORT="34094"
APP_KEY="1_C2D6F4B1183D592E04BA216D71A84F17"

# 模型配置 - 使用函数而不是关联数组
get_model_info() {
    case "$1" in
        "DeepSeekR1") echo "10.101.32.26:61025" ;;
        "QwQ-32B") echo "10.101.32.26:51025" ;;
        "Qwen2.5-32B-Instruct") echo "10.101.32.26:41025" ;;
        "Qwen3-32B") echo "10.101.32.26:21025" ;;
        *) echo "" ;;
    esac
}

# 模型列表
MODEL_LIST="DeepSeekR1 QwQ-32B Qwen2.5-32B-Instruct Qwen3-32B"

# 向量模型配置
EMBED_MODEL_HOST="10.101.32.26"
EMBED_MODEL_PORT="21031"
EMBED_MODEL_NAME="bge-large-zh-v1.5"

# API密钥配置
API_KEYS="liqi aisum kbai"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 输出函数
print_header() {
    echo -e "${BLUE}🚀 M-FastGate v0.2.0 生产环境初始化${NC}"
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
create_api_keys() {
    echo -e "${BLUE}🔑 创建生产环境API密钥...${NC}"
    
    # 创建临时文件存储密钥
    KEYS_FILE="/tmp/m-fastgate-keys.txt"
    > "$KEYS_FILE"
    
    for source_path in $API_KEYS; do
        echo -e "${BLUE}📝 创建 ${source_path} 的API密钥...${NC}"
        
        response=$(curl -s -X POST "http://${GATEWAY_HOST}/admin/keys?token=${ADMIN_TOKEN}" \
            -H "Content-Type: application/json" \
            -d '{
                "source_path": "'${source_path}'",
                "permissions": ["chat.completions", "models.list", "embeddings"],
                "expires_days": 365,
                "rate_limit": 2000
            }' 2>/dev/null)
        
        # 检查响应是否包含错误
        if echo "$response" | grep -q '"detail"'; then
            error_msg=$(echo "$response" | grep -o '"detail":"[^"]*"' | cut -d'"' -f4)
            print_error "创建 ${source_path} API密钥失败: $error_msg"
        fi
        
        # 提取密钥值
        key_value=$(echo "$response" | grep -o '"key_value":"[^"]*"' | cut -d'"' -f4)
        key_id=$(echo "$response" | grep -o '"key_id":"[^"]*"' | cut -d'"' -f4)
        
        if [ -z "$key_value" ]; then
            print_error "无法获取 ${source_path} 的API密钥值"
        fi
        
        # 保存到临时文件
        echo "${source_path}:${key_value}" >> "$KEYS_FILE"
        print_success "创建 ${source_path} API密钥成功: $key_id"
    done
    
    # 显示所有创建的密钥
    echo -e "${BLUE}📋 已创建的API密钥:${NC}"
    while IFS=: read -r source_path key_value; do
        print_info "${source_path}: ${key_value}"
    done < "$KEYS_FILE"
}

# 删除已存在的生产路由
delete_existing_routes() {
    echo -e "${BLUE}🗑️  删除已存在的生产路由...${NC}"
    
    # 获取所有路由
    routes=$(curl -s -X GET "http://${GATEWAY_HOST}/admin/routes?token=${ADMIN_TOKEN}" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$routes" ]; then
        # 提取生产相关的路由ID (包含模型名或embed)
        route_ids=$(echo "$routes" | grep -o '"route_id":"[^"]*"' | cut -d'"' -f4 | grep -E "(DeepSeek|QwQ|Qwen|embed)" || true)
        
        if [ -n "$route_ids" ]; then
            for route_id in $route_ids; do
                curl -s -X DELETE "http://${GATEWAY_HOST}/admin/routes/${route_id}?token=${ADMIN_TOKEN}" > /dev/null 2>&1
                print_info "删除路由: $route_id"
            done
        else
            print_info "没有找到需要删除的生产路由"
        fi
    else
        print_info "无法获取现有路由或路由为空"
    fi
    
    print_info "路由删除步骤完成"
}

# 创建推理模型路由
create_inference_routes() {
    echo -e "${BLUE}🛣️  创建推理模型路由...${NC}"
    
    for model_name in $MODEL_LIST; do
        model_host_port=$(get_model_info "$model_name")
        model_ip=$(echo $model_host_port | cut -d':' -f1)
        model_port=$(echo $model_host_port | cut -d':' -f2)
        
        echo -e "${BLUE}📝 创建 ${model_name} 路由...${NC}"
        
        response=$(curl -s -X POST "http://${GATEWAY_HOST}/admin/routes?token=${ADMIN_TOKEN}" \
            -H "Content-Type: application/json" \
            -d '{
                "route_name": "'${model_name}' Chat Completions",
                "description": "'${model_name}'模型聊天完成接口 - 云天代理",
                "match_path": "/v1/chat/completions",
                "match_method": "POST",
                "match_body_schema": {"model": "'${model_name}'"},
                "target_host": "'${PROXY_HOST}':'${PROXY_PORT}'",
                "target_path": "/openapi/proxy/v1/chat/completions",
                "target_protocol": "http",
                "strip_path_prefix": false,
                "add_headers": {
                    "appKey": "'${APP_KEY}'",
                    "accept": "application/json",
                    "Content-Type": "application/json"
                },
                "add_body_fields": {
                    "systemSource": "智能客服系统",
                    "modelIp": "'${model_ip}'",
                    "modelPort": "'${model_port}'",
                    "modelName": "'${model_name}'"
                },
                "remove_headers": ["host"],
                "is_active": true,
                "priority": 100
            }' 2>/dev/null)
        
        # 检查响应是否包含错误
        if echo "$response" | grep -q '"detail"'; then
            error_msg=$(echo "$response" | grep -o '"detail":"[^"]*"' | cut -d'"' -f4)
            print_error "创建 ${model_name} 路由失败: $error_msg"
        fi
        
        print_success "创建 ${model_name} 路由成功"
    done
}

# 创建向量模型路由
create_embedding_route() {
    echo -e "${BLUE}🛣️  创建向量模型路由...${NC}"
    
    response=$(curl -s -X POST "http://${GATEWAY_HOST}/admin/routes?token=${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{
            "route_name": "BGE Large ZH Embeddings",
            "description": "bge-large-zh-v1.5向量模型接口 - 云天代理",
            "match_path": "/v1/embeddings",
            "match_method": "POST",
            "target_host": "'${PROXY_HOST}':'${PROXY_PORT}'",
            "target_path": "/openapi/proxy/embed",
            "target_protocol": "http",
            "strip_path_prefix": false,
            "add_headers": {
                "appKey": "'${APP_KEY}'",
                "accept": "application/json",
                "Content-Type": "application/json"
            },
            "add_body_fields": {
                "systemSource": "智能客服系统",
                "modelIp": "'${EMBED_MODEL_HOST}'",
                "modelPort": "'${EMBED_MODEL_PORT}'",
                "modelName": "'${EMBED_MODEL_NAME}'"
            },
            "remove_headers": ["host"],
            "is_active": true,
            "priority": 200
        }' 2>/dev/null)
    
    # 检查响应是否包含错误
    if echo "$response" | grep -q '"detail"'; then
        error_msg=$(echo "$response" | grep -o '"detail":"[^"]*"' | cut -d'"' -f4)
        print_error "创建向量模型路由失败: $error_msg"
    fi
    
    print_success "创建向量模型路由成功"
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
        
        # 显示模型相关路由
        echo -e "${BLUE}📋 已配置的模型路由:${NC}"
        for model_name in $MODEL_LIST; do
            if echo "$routes" | grep -q "$model_name"; then
                print_info "✅ $model_name - 已配置"
            else
                print_warning "❌ $model_name - 未找到"
            fi
        done
        
        if echo "$routes" | grep -q "bge-large"; then
            print_info "✅ 向量模型 (bge-large-zh-v1.5) - 已配置"
        else
            print_warning "❌ 向量模型 - 未找到"
        fi
    fi
}

# 生成测试示例
generate_test_examples() {
    echo -e "${BLUE}📝 生成测试示例...${NC}"
    
    # 获取第一个API密钥用于示例
    first_key_response=$(curl -s -X GET "http://${GATEWAY_HOST}/admin/keys?token=${ADMIN_TOKEN}" 2>/dev/null)
    sample_key=$(echo "$first_key_response" | grep -o '"key_value":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    # 统计模型数量
    model_count=$(echo "$MODEL_LIST" | wc -w)
    api_key_count=$(echo "$API_KEYS" | wc -w)
    
    cat << EOF

🎉 生产环境初始化完成！
======================================================================
✅ 已配置的模型和服务:
   🤖 推理模型: $MODEL_LIST
   📊 向量模型: $EMBED_MODEL_NAME
   🔑 API密钥: $API_KEYS
   🌐 代理服务: ${PROXY_HOST}:${PROXY_PORT}

📝 测试请求示例:

# 1. 推理模型测试 (以DeepSeekR1为例)
curl -X POST http://${GATEWAY_HOST}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${sample_key}" \\
  -d '{
    "model": "DeepSeekR1",
    "messages": [
      {"role": "user", "content": "你好，请介绍一下自己"}
    ],
    "max_tokens": 100,
    "temperature": 0.7
  }'

# 2. 向量模型测试
curl -X POST http://${GATEWAY_HOST}/v1/embeddings \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${sample_key}" \\
  -d '{
    "input": "数据是生产要素",
    "model": "bge-large-zh-v1.5"
  }'

# 3. 其他模型测试
# 将上面的 "model" 字段替换为: "QwQ-32B", "Qwen2.5-32B-Instruct", "Qwen3-32B"

📌 重要说明:
   - 所有请求通过云天代理转发 (${PROXY_HOST}:${PROXY_PORT})
   - 自动添加 appKey 和监控字段
   - 支持流式和非流式推理
   - 支持向量化服务

EOF

    # 清理临时文件
    rm -f /tmp/m-fastgate-keys.txt
}

# 主函数
main() {
    print_header
    
    # 统计配置信息
    model_count=$(echo "$MODEL_LIST" | wc -w)
    api_key_count=$(echo "$API_KEYS" | wc -w)
    
    print_info "生产环境配置信息:"
    print_info "云天代理地址: ${PROXY_HOST}:${PROXY_PORT}"
    print_info "AppKey: ${APP_KEY}"
    print_info "推理模型数量: $model_count"
    print_info "向量模型: ${EMBED_MODEL_NAME}"
    print_info "API密钥数量: $api_key_count"
    echo "----------------------------------------------------------------------"
    
    get_admin_token
    wait_for_service
    create_api_keys
    delete_existing_routes
    create_inference_routes
    create_embedding_route
    verify_setup
    generate_test_examples
    
    print_success "🎉 M-FastGate生产环境初始化完成！"
}

# 执行主函数
main "$@" 