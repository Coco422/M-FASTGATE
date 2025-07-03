/**
 * M-FastGate 路由配置管理 JavaScript
 * 处理路由配置的增删改查、测试等功能
 */

// 全局变量
let routes = [];
let currentRoute = null;
let isEditMode = false;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    loadRoutes();
    loadRouteStats();
    initializeEventListeners();
});

// 初始化事件监听器
function initializeEventListeners() {
    // 创建路由按钮
    const createBtn = document.querySelector('button[onclick="showCreateRouteModal()"]');
    if (createBtn) {
        createBtn.onclick = showCreateRouteModal;
    }
    
    // 刷新按钮
    const refreshBtn = document.querySelector('button[onclick="refreshRoutes()"]');
    if (refreshBtn) {
        refreshBtn.onclick = refreshRoutes;
    }
}

// 加载路由列表
async function loadRoutes() {
    const tableBody = document.getElementById('routesTableBody');
    try {
        showLoading('routesTableBody');
        
        const response = await apiClient.get('/routes');
        
        if (response.ok) {
            routes = await response.json();
            renderRoutesTable();
            updateRouteStats();
        } else {
            const errorText = await response.text();
            showErrorInTable('routesTableBody', `加载路由列表失败: ${response.status} ${errorText}`, 7);
        }
    } catch (error) {
        console.error('加载路由列表错误:', error);
        showErrorInTable('routesTableBody', '加载路由列表时发生网络错误，请检查您的连接。', 7);
    }
}

// 渲染路由表格
function renderRoutesTable() {
    const tbody = document.getElementById('routesTableBody');
    
    if (routes.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted py-4">
                    <i class="fas fa-inbox fa-2x mb-2"></i>
                    <br>
                    暂无路由配置，点击"创建路由"开始配置
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = routes.map(route => {
        const statusBadge = route.is_active 
            ? '<span class="badge bg-success">活跃</span>' 
            : '<span class="badge bg-secondary">禁用</span>';
            
        const matchRule = `${route.match_method} ${route.match_path}`;
        const targetUrl = `${route.target_protocol}://${route.target_host}${route.target_path}`;
        
        const priorityClass = route.priority <= 50 ? 'bg-danger' : 
                             route.priority <= 100 ? 'bg-warning' : 'bg-info';
        
        return `
            <tr>
                <td>
                    <div class="fw-bold">${escapeHtml(route.route_name)}</div>
                    <small class="text-muted">${escapeHtml(route.description || '无描述')}</small>
                </td>
                <td>
                    <code class="small">${escapeHtml(matchRule)}</code>
                    ${route.match_body_schema ? '<br><small class="text-info"><i class="fas fa-code"></i> 含请求体匹配</small>' : ''}
                </td>
                <td>
                    <code class="small">${escapeHtml(targetUrl)}</code>
                    <br>
                    <small class="text-muted">
                        <i class="fas fa-clock"></i> ${route.timeout}s, 
                        <i class="fas fa-redo"></i> ${route.retry_count}
                    </small>
                </td>
                <td>
                    <span class="badge ${priorityClass}">${route.priority}</span>
                </td>
                <td>${statusBadge}</td>
                <td>
                    <span class="badge bg-light text-dark">0</span>
                    <br>
                    <small class="text-muted">今日</small>
                </td>
                <td>
                    <div class="btn-group" role="group">
                        <button class="btn btn-sm btn-outline-primary" onclick="viewRoute('${route.route_id}')" title="查看详情">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-success" onclick="editRoute('${route.route_id}')" title="编辑">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-info" onclick="testRouteById('${route.route_id}')" title="测试">
                            <i class="fas fa-flask"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-${route.is_active ? 'warning' : 'success'}" 
                                onclick="toggleRoute('${route.route_id}', ${!route.is_active})" 
                                title="${route.is_active ? '禁用' : '启用'}">
                            <i class="fas fa-${route.is_active ? 'pause' : 'play'}"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteRoute('${route.route_id}')" title="删除">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// 更新路由统计
function updateRouteStats() {
    document.getElementById('totalRoutes').textContent = routes.length;
    document.getElementById('activeRoutes').textContent = routes.filter(r => r.is_active).length;
}

// 加载路由统计数据
async function loadRouteStats() {
    try {
        const response = await apiClient.get('/metrics');
        
        if (response.ok) {
            const metrics = await response.json();
            document.getElementById('matchedRequests').textContent = metrics.total_requests || 0;
            document.getElementById('avgRouteResponse').textContent = 
                metrics.average_response_time ? Math.round(metrics.average_response_time) + 'ms' : '-';
        }
    } catch (error) {
        console.error('加载统计数据错误:', error);
    }
}

// 显示创建路由模态框
function showCreateRouteModal() {
    isEditMode = false;
    currentRoute = null;
    
    // 重置表单
    const form = document.getElementById('routeForm');
    if (form) {
        form.reset();
        
        // 设置默认值
        document.getElementById('routePriority').value = 100;
        document.getElementById('timeout').value = 30;
        document.getElementById('retryCount').value = 0;
        document.getElementById('isActive').checked = true;
        document.getElementById('targetProtocol').value = 'http';
        document.getElementById('matchMethod').value = 'POST';
        
        // 清空文本域
        document.getElementById('matchHeaders').value = '';
        document.getElementById('matchBodySchema').value = '';
        document.getElementById('addHeaders').value = '';
        document.getElementById('removeHeaders').value = '';
        document.getElementById('addBodyFields').value = '';
    }
    
    // 更新模态框标题
    document.getElementById('routeModalLabel').innerHTML = 
        '<i class="fas fa-plus me-2"></i>创建代理路由';
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('routeModal'));
    modal.show();
}

// 编辑路由
function editRoute(routeId) {
    const route = routes.find(r => r.route_id === routeId);
    if (!route) {
        showError('路由不存在');
        return;
    }
    
    isEditMode = true;
    currentRoute = route;
    
    // 填充表单基础字段
    document.getElementById('routeName').value = route.route_name;
    document.getElementById('routeDescription').value = route.description || '';
    document.getElementById('routePriority').value = route.priority;
    document.getElementById('matchPath').value = route.match_path;
    document.getElementById('matchMethod').value = route.match_method;
    document.getElementById('targetProtocol').value = route.target_protocol;
    document.getElementById('targetHost').value = route.target_host;
    document.getElementById('targetPath').value = route.target_path;
    document.getElementById('stripPathPrefix').checked = route.strip_path_prefix;
    document.getElementById('timeout').value = route.timeout;
    document.getElementById('retryCount').value = route.retry_count;
    document.getElementById('isActive').checked = route.is_active;
    
    // 处理JSON字段 - 将对象转换为JSON字符串显示
    document.getElementById('matchHeaders').value = route.match_headers ? 
        JSON.stringify(route.match_headers, null, 2) : '';
    document.getElementById('matchBodySchema').value = route.match_body_schema ? 
        JSON.stringify(route.match_body_schema, null, 2) : '';
    document.getElementById('addHeaders').value = route.add_headers ? 
        JSON.stringify(route.add_headers, null, 2) : '';
    document.getElementById('removeHeaders').value = route.remove_headers ? 
        JSON.stringify(route.remove_headers, null, 2) : '';
    document.getElementById('addBodyFields').value = route.add_body_fields ? 
        JSON.stringify(route.add_body_fields, null, 2) : '';
    
    // 更新模态框标题
    document.getElementById('routeModalLabel').innerHTML = 
        '<i class="fas fa-edit me-2"></i>编辑代理路由';
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('routeModal'));
    modal.show();
}

// 保存路由
async function saveRoute() {
    // 验证表单
    const form = document.getElementById('routeForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    // 验证JSON格式
    const jsonFields = ['matchHeaders', 'matchBodySchema', 'addHeaders', 'removeHeaders', 'addBodyFields'];
    for (const fieldId of jsonFields) {
        const field = document.getElementById(fieldId);
        if (field.value.trim() && !isValidJSON(field.value)) {
            showError(`${field.previousElementSibling.textContent} 格式不正确，请输入有效的JSON`);
            field.focus();
            return;
        }
    }
    
    // 收集表单数据 - 按API设计规范发送结构化数据
    const data = {
        route_name: document.getElementById('routeName').value.trim(),
        description: document.getElementById('routeDescription').value.trim() || null,
        match_path: document.getElementById('matchPath').value.trim(),
        match_method: document.getElementById('matchMethod').value,
        target_protocol: document.getElementById('targetProtocol').value,
        target_host: document.getElementById('targetHost').value.trim(),
        target_path: document.getElementById('targetPath').value.trim(),
        strip_path_prefix: document.getElementById('stripPathPrefix').checked,
        timeout: parseInt(document.getElementById('timeout').value),
        retry_count: parseInt(document.getElementById('retryCount').value),
        priority: parseInt(document.getElementById('routePriority').value),
        is_active: document.getElementById('isActive').checked
    };
    
    // 处理JSON字段 - 转换为实际的JSON对象或null
    const matchHeaders = document.getElementById('matchHeaders').value.trim();
    if (matchHeaders) {
        try {
            data.match_headers = JSON.parse(matchHeaders);
        } catch (e) {
            data.match_headers = null;
        }
    } else {
        data.match_headers = null;
    }
    
    const matchBodySchema = document.getElementById('matchBodySchema').value.trim();
    if (matchBodySchema) {
        try {
            data.match_body_schema = JSON.parse(matchBodySchema);
        } catch (e) {
            data.match_body_schema = null;
        }
    } else {
        data.match_body_schema = null;
    }
    
    const addHeaders = document.getElementById('addHeaders').value.trim();
    if (addHeaders) {
        try {
            data.add_headers = JSON.parse(addHeaders);
        } catch (e) {
            data.add_headers = null;
        }
    } else {
        data.add_headers = null;
    }
    
    const removeHeaders = document.getElementById('removeHeaders').value.trim();
    if (removeHeaders) {
        try {
            data.remove_headers = JSON.parse(removeHeaders);
        } catch (e) {
            data.remove_headers = null;
        }
    } else {
        data.remove_headers = null;
    }
    
    const addBodyFields = document.getElementById('addBodyFields').value.trim();
    if (addBodyFields) {
        try {
            data.add_body_fields = JSON.parse(addBodyFields);
        } catch (e) {
            data.add_body_fields = null;
        }
    } else {
        data.add_body_fields = null;
    }

    const method = isEditMode ? 'POST' : 'POST';
    const endpoint = isEditMode ? `/routes/update/${currentRoute.route_id}` : '/routes';

    try {
        const response = await apiClient.post(endpoint, data);
        
        if (response.ok) {
            showSuccess(`路由已成功${isEditMode ? '更新' : '创建'}`);
            const modal = bootstrap.Modal.getInstance(document.getElementById('routeModal'));
            modal.hide();
            loadRoutes();
        } else {
            const error = await response.json();
            showError(`保存路由失败: ${error.detail || '未知错误'}`);
        }
    } catch (error) {
        console.error('保存路由错误:', error);
        showError('保存路由时发生网络错误');
    }
}

// 测试路由
async function testRoute() {
    if (!currentRoute && !isEditMode) {
        showWarning('请先保存路由后再进行测试');
        return;
    }
    
    // 收集测试数据
    const testData = {
        test_method: document.getElementById('matchMethod').value === 'ANY' ? 'POST' : document.getElementById('matchMethod').value,
        test_headers: {'Content-Type': 'application/json'},
        test_body: {},
        timeout: 10
    };
    
    // 如果有匹配的请求体，使用它作为测试数据
    const matchBodySchema = document.getElementById('matchBodySchema').value.trim();
    if (matchBodySchema && isValidJSON(matchBodySchema)) {
        try {
            testData.test_body = JSON.parse(matchBodySchema);
        } catch (e) {
            testData.test_body = {test: true};
        }
    } else {
        testData.test_body = {test: true};
    }
    
    if (isEditMode && currentRoute) {
        await performRouteTest(currentRoute.route_id, testData);
    } else {
        showWarning('请先保存路由后再进行测试');
    }
}

// 通过ID测试路由
async function testRouteById(routeId) {
    const testData = {
        test_method: 'POST',
        test_headers: {'Content-Type': 'application/json'},
        test_body: {'test': true},
        timeout: 10
    };
    
    await performRouteTest(routeId, testData);
}

// 执行路由测试
async function performRouteTest(routeId, testData) {
    showLoading('testResultBody');
    try {
        const endpoint = routeId ? `/routes/${routeId}/test` : '/routes/test';
        const response = await apiClient.post(endpoint, testData);

        const result = await response.json();
        showTestResult(result);
    } catch (error) {
        console.error('测试路由错误:', error);
        showError('testResultBody', '测试路由时发生网络错误');
    }
}

// 显示测试结果
function showTestResult(result) {
    const content = document.getElementById('testResultContent');
    
    const statusClass = result.success ? 'success' : 'danger';
    const statusIcon = result.success ? 'check-circle' : 'times-circle';
    
    content.innerHTML = `
        <div class="alert alert-${statusClass}">
            <h6><i class="fas fa-${statusIcon} me-2"></i>测试${result.success ? '成功' : '失败'}</h6>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <h6>测试结果</h6>
                <ul class="list-group">
                    <li class="list-group-item d-flex justify-content-between">
                        <span>路由匹配</span>
                        <span class="badge bg-${result.matched ? 'success' : 'danger'}">
                            ${result.matched ? '匹配' : '不匹配'}
                        </span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>响应时间</span>
                        <span>${result.response_time_ms || 0}ms</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>状态码</span>
                        <span class="badge bg-${result.status_code && result.status_code < 400 ? 'success' : 'danger'}">
                            ${result.status_code || 'N/A'}
                        </span>
                    </li>
                </ul>
            </div>
            
            <div class="col-md-6">
                <h6>目标URL</h6>
                <code class="d-block p-2 bg-light small">${escapeHtml(result.target_url || 'N/A')}</code>
                
                ${result.error_message ? `
                    <h6 class="mt-3">错误信息</h6>
                    <div class="alert alert-danger small">${escapeHtml(result.error_message)}</div>
                ` : ''}
            </div>
        </div>
        
        ${result.test_result ? `
            <h6 class="mt-3">详细结果</h6>
            <div class="row text-center">
                <div class="col-md-3">
                    <i class="fas fa-${result.test_result.request_sent ? 'check text-success' : 'times text-danger'} fa-2x"></i>
                    <div class="small mt-1">请求发送</div>
                </div>
                <div class="col-md-3">
                    <i class="fas fa-${result.test_result.response_received ? 'check text-success' : 'times text-danger'} fa-2x"></i>
                    <div class="small mt-1">响应接收</div>
                </div>
                <div class="col-md-3">
                    <i class="fas fa-${result.test_result.headers_applied ? 'check text-success' : 'times text-danger'} fa-2x"></i>
                    <div class="small mt-1">请求头处理</div>
                </div>
                <div class="col-md-3">
                    <i class="fas fa-${result.test_result.body_modified ? 'check text-success' : 'times text-danger'} fa-2x"></i>
                    <div class="small mt-1">请求体处理</div>
                </div>
            </div>
        ` : ''}
    `;
    
    const modal = new bootstrap.Modal(document.getElementById('testResultModal'));
    modal.show();
}

// 查看路由详情
function viewRoute(routeId) {
    const route = routes.find(r => r.route_id === routeId);
    if (!route) {
        showError('路由不存在');
        return;
    }
    
    // 格式化JSON显示的辅助函数
    function formatJsonDisplay(obj) {
        if (!obj) return '无';
        if (typeof obj === 'string') return escapeHtml(obj);
        return '<pre class="bg-light p-2 small">' + escapeHtml(JSON.stringify(obj, null, 2)) + '</pre>';
    }
    
    const content = document.getElementById('routeDetailContent');
    content.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <h6>基础信息</h6>
                <table class="table table-sm">
                    <tr><td>路由ID</td><td><code>${escapeHtml(route.route_id)}</code></td></tr>
                    <tr><td>路由名称</td><td>${escapeHtml(route.route_name)}</td></tr>
                    <tr><td>描述</td><td>${escapeHtml(route.description || '无')}</td></tr>
                    <tr><td>优先级</td><td>${route.priority}</td></tr>
                    <tr><td>状态</td><td><span class="badge bg-${route.is_active ? 'success' : 'secondary'}">${route.is_active ? '活跃' : '禁用'}</span></td></tr>
                </table>
            </div>
            
            <div class="col-md-6">
                <h6>匹配规则</h6>
                <table class="table table-sm">
                    <tr><td>路径</td><td><code>${escapeHtml(route.match_path)}</code></td></tr>
                    <tr><td>方法</td><td><code>${route.match_method}</code></td></tr>
                    <tr><td>请求头</td><td>${formatJsonDisplay(route.match_headers)}</td></tr>
                    <tr><td>请求体</td><td>${formatJsonDisplay(route.match_body_schema)}</td></tr>
                </table>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <h6>目标配置</h6>
                <table class="table table-sm">
                    <tr><td>协议</td><td>${route.target_protocol}</td></tr>
                    <tr><td>主机</td><td><code>${escapeHtml(route.target_host)}</code></td></tr>
                    <tr><td>路径</td><td><code>${escapeHtml(route.target_path)}</code></td></tr>
                    <tr><td>剔除前缀</td><td>${route.strip_path_prefix ? '是' : '否'}</td></tr>
                    <tr><td>超时</td><td>${route.timeout}秒</td></tr>
                    <tr><td>重试</td><td>${route.retry_count}次</td></tr>
                </table>
            </div>
            
            <div class="col-md-6">
                <h6>转换规则</h6>
                <div class="mb-2">
                    <strong>添加请求头:</strong><br>
                    ${formatJsonDisplay(route.add_headers)}
                </div>
                <div class="mb-2">
                    <strong>移除请求头:</strong><br>
                    ${formatJsonDisplay(route.remove_headers)}
                </div>
                <div class="mb-2">
                    <strong>添加请求体字段:</strong><br>
                    ${formatJsonDisplay(route.add_body_fields)}
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-12">
                <h6>时间信息</h6>
                <table class="table table-sm">
                    <tr><td>创建时间</td><td>${new Date(route.created_at).toLocaleString()}</td></tr>
                    <tr><td>更新时间</td><td>${new Date(route.updated_at).toLocaleString()}</td></tr>
                </table>
            </div>
        </div>
    `;
    
    currentRoute = route;
    const modal = new bootstrap.Modal(document.getElementById('routeDetailModal'));
    modal.show();
}

// 从详情模态框编辑路由
function editRouteFromDetail() {
    bootstrap.Modal.getInstance(document.getElementById('routeDetailModal')).hide();
    setTimeout(() => editRoute(currentRoute.route_id), 300);
}

// 切换路由状态
async function toggleRoute(routeId, isActive) {
    try {
        const response = await apiClient.post(`/routes/${routeId}/toggle`, { is_active: isActive });
        
        if (response.ok) {
            showSuccess(`路由已${isActive ? '启用' : '禁用'}`);
            loadRoutes();
        } else {
            const error = await response.json();
            showError(`操作失败: ${error.detail}`);
        }
    } catch (error) {
        console.error('切换路由状态错误:', error);
        showError('切换路由状态时发生网络错误');
    }
}

// 删除路由
async function deleteRoute(routeId) {
    if (!confirm('确定要删除此路由吗？此操作不可撤销。')) {
        return;
    }

    try {
        const response = await apiClient.post(`/routes/delete/${routeId}`);

        if (response.ok) {
            showSuccess('路由已删除');
            loadRoutes();
        } else {
            const error = await response.json();
            showError(`删除失败: ${error.detail}`);
        }
    } catch (error) {
        console.error('删除路由错误:', error);
        showError('删除路由时发生网络错误');
    }
}

// 过滤路由
function filterRoutes(filter) {
    let filteredRoutes = [...routes];
    
    switch (filter) {
        case 'active':
            filteredRoutes = routes.filter(r => r.is_active);
            break;
        case 'inactive':
            filteredRoutes = routes.filter(r => !r.is_active);
            break;
        case 'high-priority':
            filteredRoutes = routes.filter(r => r.priority <= 50);
            break;
        case 'all':
        default:
            // 显示所有路由
            break;
    }
    
    const originalRoutes = routes;
    routes = filteredRoutes;
    renderRoutesTable();
    routes = originalRoutes;
}

// 刷新路由列表
function refreshRoutes() {
    loadRoutes();
    loadRouteStats();
}

// 工具函数 - 验证JSON格式
function isValidJSON(str) {
    if (!str.trim()) return true; // 空字符串认为是有效的
    try {
        JSON.parse(str);
        return true;
    } catch (e) {
        return false;
    }
}

// 工具函数 - HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// 工具函数 - 显示加载中
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    // 如果是tbody，则创建带colspan的加载行
    if (element.tagName.toLowerCase() === 'tbody') {
        const colCount = element.previousElementSibling.rows[0].cells.length || 1;
        element.innerHTML = `
            <tr>
                <td colspan="${colCount}" class="text-center text-muted py-4">
                    <div class="spinner-border spinner-border-sm" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <span class="ms-2">加载中...</span>
                </td>
            </tr>
        `;
    } else {
        element.innerHTML = '加载中...';
    }
}

// 在表格中显示错误信息
function showErrorInTable(elementId, message, colspan = 1) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    if (element.tagName.toLowerCase() === 'tbody') {
        element.innerHTML = `
            <tr>
                <td colspan="${colspan}" class="text-center text-danger py-4">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <br>
                    ${escapeHtml(message)}
                </td>
            </tr>
        `;
    } else {
        element.innerHTML = `<div class="text-danger">${escapeHtml(message)}</div>`;
    }
}

// 从common.js继承的工具函数
function getAdminToken() {
    return new URLSearchParams(window.location.search).get('token') || 'admin_secret_token_dev';
}

function showSuccess(message) {
    showAlert(message, 'success');
}

function showError(message) {
    showAlert(message, 'danger');
}

function showWarning(message) {
    showAlert(message, 'warning');
}

function showInfo(message) {
    showAlert(message, 'info');
}

function showAlert(message, type) {
    const alertContainer = document.getElementById('alertContainer');
    if (alertContainer) {
        const alertId = 'alert-' + Date.now();
        const alertHtml = `
            <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${escapeHtml(message)}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        alertContainer.insertAdjacentHTML('beforeend', alertHtml);
        
        // 3秒后自动移除
        setTimeout(() => {
            const alertElement = document.getElementById(alertId);
            if (alertElement) {
                alertElement.remove();
            }
        }, 3000);
    } else {
        console.log(`${type.toUpperCase()}: ${message}`);
    }
} 