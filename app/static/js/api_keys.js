/**
 * API Keys 管理页面的JavaScript逻辑
 */

class ApiKeysManager {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 20;
        this.totalPages = 1;
        this.filters = {
            search: '',
            status: ''
        };
        
        this.init();
    }
    
    init() {
        // 页面加载完成后初始化
        this.loadApiKeys();
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // 搜索框实时搜索
        $('#searchInput').on('input', debounce(() => {
            this.filters.search = $('#searchInput').val().trim();
            this.currentPage = 1;
            this.loadApiKeys();
        }, 500));
        
        // 过滤器变化
        $('#statusFilter').on('change', () => {
            this.applyFilters();
        });
        
        // 回车键搜索
        $('#searchInput').on('keypress', (e) => {
            if (e.which === 13) {
                this.applyFilters();
            }
        });
    }
    
    async loadApiKeys(page = this.currentPage) {
        try {
            showLoading('#apiKeysTable', 8);
            
            // 构建查询参数
            const params = new URLSearchParams({
                skip: (page - 1) * this.pageSize,
                limit: this.pageSize
            });
            
            // 添加过滤条件
            if (this.filters.search) {
                // Assuming backend supports a 'source_path_like' or similar parameter for searching source_path
                params.append('source_path_like', this.filters.search); 
            }
            if (this.filters.status !== '') {
                params.append('is_active', this.filters.status);
            }
            
            const response = await apiClient.get(`/keys?${params}`);
            
            if (response.ok) {
                const keys = await response.json();
                this.renderApiKeys(keys);
                this.updateTotalCount(keys.length);
                this.updatePagination(keys.length);
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
        } catch (error) {
            console.error('加载API Keys失败:', error);
            showError('#apiKeysTable', '加载API Keys失败: ' + error.message, 8);
            showAlert('加载API Keys失败: ' + error.message, 'danger');
        }
    }
    
    renderApiKeys(keys) {
        const tbody = $('#apiKeysTable');
        
        if (!keys || keys.length === 0) {
            tbody.html(`
                <tr>
                    <td colspan="7" class="text-center text-muted py-4">
                        <i class="fas fa-inbox fa-2x mb-2"></i><br>
                        暂无API Key数据
                    </td>
                </tr>
            `);
            return;
        }
        
        const rows = keys.map(key => `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <i class="fas fa-user text-primary me-2"></i>
                        <span class="fw-medium">${escapeHtml(key.source_path || 'N/A')}</span>
                    </div>
                </td>
                <td>
                    <div class="d-flex align-items-center">
                        <code class="bg-light px-2 py-1 rounded text-monospace">
                            ${key.key_value ? key.key_value.substring(0, 20) + '...' : 'N/A'}
                        </code>
                        <button class="btn btn-sm btn-outline-secondary ms-2" 
                                onclick="copyToClipboard('${key.key_value}', this)">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                </td>
                <td>
                    ${key.is_active ? 
                        '<span class="badge bg-success"><i class="fas fa-check-circle me-1"></i>有效</span>' : 
                        '<span class="badge bg-danger"><i class="fas fa-times-circle me-1"></i>无效</span>'
                    }
                </td>
                <td>
                    <span class="text-primary fw-medium">${key.usage_count || 0}</span>
                </td>
                <td>
                    <small class="text-muted">
                        ${formatDateTime(key.created_at)}
                    </small>
                </td>
                <td>
                    <small class="text-muted">
                        ${key.expires_at ? formatDateTime(key.expires_at) : '永不过期'}
                    </small>
                </td>
                <td>
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-info" onclick="apiKeysManager.viewKey('${key.key_id}')"
                                title="查看详情">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-outline-warning" onclick="apiKeysManager.editKey('${key.key_id}')"
                                title="编辑">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="apiKeysManager.deleteKey('${key.key_id}', '${escapeHtml(key.source_path || 'N/A')}')"
                                title="删除">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
        
        tbody.html(rows);
    }
    
    updateTotalCount(count) {
        $('#totalCount').text(count);
    }
    
    updatePagination(currentCount) {
        // 简单分页实现，实际应该从API获取总数
        const pagination = $('#pagination');
        
        if (currentCount < this.pageSize && this.currentPage === 1) {
            pagination.empty();
            return;
        }
        
        let paginationHtml = '';
        
        // 上一页
        paginationHtml += `
            <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="apiKeysManager.goToPage(${this.currentPage - 1})">
                    <i class="fas fa-chevron-left"></i>
                </a>
            </li>
        `;
        
        // 当前页
        paginationHtml += `
            <li class="page-item active">
                <span class="page-link">${this.currentPage}</span>
            </li>
        `;
        
        // 下一页
        if (currentCount === this.pageSize) {
            paginationHtml += `
                <li class="page-item">
                    <a class="page-link" href="#" onclick="apiKeysManager.goToPage(${this.currentPage + 1})">
                        <i class="fas fa-chevron-right"></i>
                    </a>
                </li>
            `;
        }
        
        pagination.html(paginationHtml);
    }
    
    goToPage(page) {
        if (page < 1) return;
        this.currentPage = page;
        this.loadApiKeys(page);
    }
    
    applyFilters() {
        this.filters.status = $('#statusFilter').val();
        this.filters.search = $('#searchInput').val().trim();
        this.currentPage = 1;
        this.loadApiKeys();
    }
    
    resetFilters() {
        $('#searchInput').val('');
        $('#statusFilter').val('');
        this.filters = { search: '', status: '' };
        this.currentPage = 1;
        this.loadApiKeys();
    }
    
    async createApiKey() {
        try {
            const keyData = {
                source_path: $('#keySourcePath').val().trim() || null,
                description: $('#keyDescription').val().trim() || null
            };
            
            // 处理过期时间
            const expiry = $('#keyExpiry').val();
            if (expiry) {
                keyData.expires_at = new Date(expiry).toISOString();
            }
            
            if (!keyData.source_path) {
                showAlert('请输入用户标识', 'warning');
                return;
            }
            
            const response = await apiClient.post('/keys', keyData);
            
            if (response.ok) {
                const result = await response.json();
                showAlert('API Key创建成功！', 'success');
                $('#createKeyModal').modal('hide');
                $('#createKeyForm')[0].reset();
                this.loadApiKeys();
                
                // 显示新创建的Key
                setTimeout(() => {
                    alert(`新的API Key已创建：\n\n${result.key_value}\n\n请妥善保存，此Key不会再次显示！`);
                }, 500);
            } else {
                const error = await response.json();
                throw new Error(error.detail || '创建失败');
            }
            
        } catch (error) {
            console.error('创建API Key失败:', error);
            showAlert('创建API Key失败: ' + error.message, 'danger');
        }
    }
    
    async viewKey(keyId) {
        try {
            const response = await apiClient.get(`/keys/${keyId}`);
            
            if (response.ok) {
                const key = await response.json();
                this.showKeyDetails(key);
            } else {
                throw new Error('获取Key详情失败');
            }
            
        } catch (error) {
            console.error('查看Key详情失败:', error);
            showAlert('查看Key详情失败: ' + error.message, 'danger');
        }
    }
    
    showKeyDetails(key) {
        const details = `
            <div class="row">
                <div class="col-md-6">
                    <h6 class="text-primary">基本信息</h6>
                    <table class="table table-sm">
                        <tr>
                            <th width="120">Key ID:</th>
                            <td><code>${key.key_id}</code></td>
                        </tr>
                        <tr>
                            <th>用户标识:</th>
                            <td>${escapeHtml(key.source_path || 'N/A')}</td>
                        </tr>
                        <tr>
                            <th>状态:</th>
                            <td>
                                ${key.is_active ? 
                                    '<span class="badge bg-success">有效</span>' : 
                                    '<span class="badge bg-danger">无效</span>'
                                }
                            </td>
                        </tr>
                        <tr>
                            <th>来源路径:</th>
                            <td>${escapeHtml(key.source_path || '全局')}</td>
                        </tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6 class="text-primary">使用统计</h6>
                    <table class="table table-sm">
                        <tr>
                            <th width="120">使用次数:</th>
                            <td><span class="badge bg-info">${key.usage_count || 0}</span></td>
                        </tr>
                        <tr>
                            <th>创建时间:</th>
                            <td>${formatDateTime(key.created_at)}</td>
                        </tr>
                        <tr>
                            <th>过期时间:</th>
                            <td>${key.expires_at ? formatDateTime(key.expires_at) : '永不过期'}</td>
                        </tr>
                        <tr>
                            <th>最后使用:</th>
                            <td>${key.last_used ? formatDateTime(key.last_used) : '从未使用'}</td>
                        </tr>
                    </table>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-12">
                    <h6 class="text-primary">API Key</h6>
                    <div class="input-group">
                        <input type="text" class="form-control font-monospace" 
                               value="${key.key_value}" readonly>
                        <button class="btn btn-outline-secondary" 
                                onclick="copyToClipboard('${key.key_value}', this)">
                            <i class="fas fa-copy me-1"></i>复制
                        </button>
                    </div>
                </div>
            </div>
            
            ${key.description ? `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6 class="text-primary">描述</h6>
                        <p class="text-muted">${escapeHtml(key.description)}</p>
                    </div>
                </div>
            ` : ''}
        `;
        
        $('#keyDetails').html(details);
        $('#viewKeyModal').modal('show');
    }
    
    async editKey(keyId) {
        try {
            const response = await apiClient.get(`/keys/${keyId}`);
            
            if (response.ok) {
                const key = await response.json();
                this.showEditKeyModal(key);
            } else {
                throw new Error('获取Key信息失败');
            }
            
        } catch (error) {
            console.error('编辑Key失败:', error);
            showAlert('编辑Key失败: ' + error.message, 'danger');
        }
    }
    
    showEditKeyModal(key) {
        $('#editKeyId').val(key.key_id);
        $('#editKeySourcePath').val(key.source_path || '');
        $('#editKeyExpiry').val(key.expires_at ? key.expires_at.substring(0, 16) : '');
        $('#editKeyDescription').val(key.description || '');
        $('#editKeyActive').prop('checked', key.is_active);
        
        new bootstrap.Modal(document.getElementById('editKeyModal')).show();
    }
    
    async updateApiKey() {
        const keyId = $('#editKeyId').val();
        const keyData = {
            source_path: $('#editKeySourcePath').val().trim() || null,
            description: $('#editKeyDescription').val().trim() || null,
            is_active: $('#editKeyActive').is(':checked')
        };
        
        // 处理过期时间
        const expiry = $('#editKeyExpiry').val();
        if (expiry) {
            keyData.expires_at = new Date(expiry).toISOString();
        }
        
        if (!keyData.source_path) {
            showAlert('请输入用户标识', 'warning');
            return;
        }
        
        const response = await apiClient.post(`/keys/update/${keyId}`, keyData);
        
        if (response.ok) {
            showAlert('API Key更新成功！', 'success');
            $('#editKeyModal').modal('hide');
            this.loadApiKeys();
        } else {
            const error = await response.json();
            throw new Error(error.detail || '更新失败');
        }
    }
    
    async deleteKey(keyId, userName) {
        if (!confirm(`确定要删除用户 "${userName}" 的API Key吗？\n\n此操作不可恢复！`)) {
            return;
        }
        
        try {
            const response = await apiClient.post(`/keys/delete/${keyId}`);
            
            if (response.ok) {
                showAlert('API Key删除成功！', 'success');
                this.loadApiKeys();
            } else {
                const error = await response.json();
                throw new Error(error.detail || '删除失败');
            }
            
        } catch (error) {
            console.error('删除API Key失败:', error);
            showAlert('删除API Key失败: ' + error.message, 'danger');
        }
    }
    
    refreshKeys() {
        this.loadApiKeys();
    }
}

// 全局函数
function showCreateKeyModal() {
    $('#createKeyModal').modal('show');
}

function createApiKey() {
    if (window.apiKeysManager) {
        apiKeysManager.createApiKey();
    } else {
        console.error('ApiKeysManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function updateApiKey() {
    if (window.apiKeysManager) {
        apiKeysManager.updateApiKey();
    } else {
        console.error('ApiKeysManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function applyFilters() {
    if (window.apiKeysManager) {
        apiKeysManager.applyFilters();
    } else {
        console.error('ApiKeysManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function resetFilters() {
    if (window.apiKeysManager) {
        apiKeysManager.resetFilters();
    } else {
        console.error('ApiKeysManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function refreshKeys() {
    if (window.apiKeysManager) {
        apiKeysManager.refreshKeys();
    } else {
        console.error('ApiKeysManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

// 初始化管理器
let apiKeysManager;

/* 等待 apiClient 注入（common.js 会在 window 上挂 apiClient） */
function waitForApiClient() {
    if (window.apiClient) return Promise.resolve();
    return new Promise(resolve => {
        const timer = setInterval(() => {
            if (window.apiClient) {
                clearInterval(timer);
                resolve();
            }
        }, 100);
    });
}

/* DOM 就绪后初始化 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await waitForApiClient();          // <-- 关键
        apiKeysManager = new ApiKeysManager();
        window.apiKeysManager = apiKeysManager;   // 让 onclick 能访问
        console.log('ApiKeysManager ready');
    } catch (e) {
        console.error('Init ApiKeysManager failed', e);
        showAlert('初始化 API Key 页面失败: ' + e.message, 'danger');
    }
});