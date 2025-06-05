/**
 * 审计日志页面的JavaScript逻辑
 */

class AuditLogsManager {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 50;
        this.autoRefreshInterval = null;
        this.filters = {
            api_key: '',
            method: '',
            status_code: '',
            source_path: '',
            time_range: ''
        };
        
        this.init();
    }
    
    init() {
        this.loadLogs();
        this.setupEventListeners();
        this.updateStats();
    }
    
    setupEventListeners() {
        // 自动刷新开关
        $('#autoRefresh').on('change', (e) => {
            if (e.target.checked) {
                this.startAutoRefresh();
            } else {
                this.stopAutoRefresh();
            }
        });
        
        // 过滤器变化
        $('#apiKeyFilter, #methodFilter, #statusFilter, #sourcePathFilter, #timeRangeFilter').on('change', () => {
            // 延迟应用，避免频繁请求
            clearTimeout(this.filterTimeout);
            this.filterTimeout = setTimeout(() => {
                this.applyFilters();
            }, 500);
        });
    }
    
    async loadLogs(page = this.currentPage) {
        try {
            showLoading('#logsTable', 10);
            
            const params = new URLSearchParams({
                skip: (page - 1) * this.pageSize,
                limit: this.pageSize
            });
            
            // 添加过滤条件
            if (this.filters.api_key) {
                params.append('api_key', this.filters.api_key);
            }
            if (this.filters.method) {
                params.append('method', this.filters.method);
            }
            if (this.filters.status_code) {
                params.append('status_code', this.filters.status_code);
            }
            if (this.filters.source_path) {
                params.append('source_path', this.filters.source_path);
            }
            
            const response = await apiClient.get(`/admin/logs?${params}`);
            
            if (response.ok) {
                const logs = await response.json();
                this.renderLogs(logs);
                this.updateCurrentCount(logs.length);
                this.updatePagination(logs.length);
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
        } catch (error) {
            console.error('加载审计日志失败:', error);
            showError('#logsTable', '加载审计日志失败: ' + error.message, 10);
            showAlert('加载审计日志失败: ' + error.message, 'danger');
        }
    }
    
    renderLogs(logs) {
        const tbody = $('#logsTable');
        
        if (!logs || logs.length === 0) {
            tbody.html(`
                <tr>
                    <td colspan="10" class="text-center text-muted py-4">
                        <i class="fas fa-inbox fa-2x mb-2"></i><br>
                        暂无日志数据
                    </td>
                </tr>
            `);
            return;
        }
        
        const rows = logs.map(log => {
            const statusClass = this.getStatusClass(log.status_code);
            const methodClass = this.getMethodClass(log.method);
            
            return `
                <tr>
                    <td>
                        <small class="text-muted">
                            ${formatDateTime(log.timestamp)}
                        </small>
                    </td>
                    <td>
                        <code class="small">
                            ${log.api_key ? log.api_key.substring(0, 12) + '...' : 'N/A'}
                        </code>
                    </td>
                    <td>
                        <span class="badge ${methodClass}">${log.method}</span>
                    </td>
                    <td>
                        <small>
                            ${escapeHtml(log.path || 'N/A')}
                            ${log.target_url ? `<br><span class="text-muted">→ ${escapeHtml(log.target_url.substring(0, 40))}...</span>` : ''}
                        </small>
                    </td>
                    <td>
                        <span class="badge ${statusClass}">${log.status_code}</span>
                    </td>
                    <td>
                        <span class="text-${log.response_time_ms > 1000 ? 'warning' : 'success'}">
                            ${log.response_time_ms}ms
                        </span>
                    </td>
                    <td>
                        <small class="text-muted">
                            ${formatBytes(log.request_size || 0)}
                        </small>
                    </td>
                    <td>
                        <small class="text-muted">
                            ${formatBytes(log.response_size || 0)}
                        </small>
                    </td>
                    <td>
                        <small class="text-muted">
                            ${log.ip_address || 'N/A'}
                        </small>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-outline-info" 
                                onclick="auditLogsManager.viewLogDetail('${log.request_id}')"
                                title="查看详情">
                            <i class="fas fa-eye"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        
        tbody.html(rows);
    }
    
    getStatusClass(statusCode) {
        if (statusCode >= 200 && statusCode < 300) return 'bg-success';
        if (statusCode >= 400 && statusCode < 500) return 'bg-warning';
        if (statusCode >= 500) return 'bg-danger';
        return 'bg-secondary';
    }
    
    getMethodClass(method) {
        const classes = {
            'GET': 'bg-primary',
            'POST': 'bg-success',
            'PUT': 'bg-warning',
            'DELETE': 'bg-danger',
            'PATCH': 'bg-info'
        };
        return classes[method] || 'bg-secondary';
    }
    
    updateCurrentCount(count) {
        $('#currentCount').text(count);
    }
    
    updatePagination(currentCount) {
        const pagination = $('#pagination');
        
        if (currentCount < this.pageSize && this.currentPage === 1) {
            pagination.empty();
            return;
        }
        
        let paginationHtml = '';
        
        // 上一页
        paginationHtml += `
            <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="auditLogsManager.goToPage(${this.currentPage - 1})">
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
                    <a class="page-link" href="#" onclick="auditLogsManager.goToPage(${this.currentPage + 1})">
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
        this.loadLogs(page);
    }
    
    applyFilters() {
        this.filters.api_key = $('#apiKeyFilter').val();
        this.filters.method = $('#methodFilter').val();
        this.filters.status_code = $('#statusFilter').val();
        this.filters.source_path = $('#sourcePathFilter').val();
        this.filters.time_range = $('#timeRangeFilter').val();
        
        this.currentPage = 1;
        this.loadLogs();
        this.updateStats();
    }
    
    resetFilters() {
        $('#apiKeyFilter').val('');
        $('#methodFilter').val('');
        $('#statusFilter').val('');
        $('#sourcePathFilter').val('');
        $('#timeRangeFilter').val('');
        
        this.filters = {
            api_key: '', method: '', status_code: '', 
            source_path: '', time_range: ''
        };
        
        this.currentPage = 1;
        this.loadLogs();
        this.updateStats();
    }
    
    async updateStats() {
        try {
            // 使用当前过滤条件获取统计信息
            const params = new URLSearchParams();
            
            if (this.filters.api_key) {
                params.append('api_key', this.filters.api_key);
            }
            if (this.filters.method) {
                params.append('method', this.filters.method);
            }
            if (this.filters.status_code) {
                params.append('status_code', this.filters.status_code);
            }
            if (this.filters.source_path) {
                params.append('source_path', this.filters.source_path);
            }
            
            // 获取大量数据用于统计
            params.append('limit', '1000');
            
            const response = await apiClient.get(`/admin/logs?${params}`);
            
            if (response.ok) {
                const logs = await response.json();
                this.calculateStats(logs);
            }
            
        } catch (error) {
            console.error('更新统计信息失败:', error);
        }
    }
    
    calculateStats(logs) {
        const total = logs.length;
        const success = logs.filter(log => log.status_code >= 200 && log.status_code < 400).length;
        const errors = total - success;
        const avgResponseTime = total > 0 ? 
            Math.round(logs.reduce((sum, log) => sum + (log.response_time_ms || 0), 0) / total) : 0;
        
        $('#totalRequests').text(total);
        $('#successRequests').text(success);
        $('#errorRequests').text(errors);
        $('#avgResponseTime').text(avgResponseTime);
    }
    
    changePageSize(newSize) {
        this.pageSize = newSize;
        $('#currentPageSize').text(newSize);
        this.currentPage = 1;
        this.loadLogs();
    }
    
    async viewLogDetail(requestId) {
        try {
            // 从当前logs中查找详情（实际应该有专门的API接口）
            const params = new URLSearchParams({
                limit: 1000
            });
            
            const response = await apiClient.get(`/admin/logs?${params}`);
            
            if (response.ok) {
                const logs = await response.json();
                const log = logs.find(l => l.request_id === requestId);
                
                if (log) {
                    this.showLogDetail(log);
                } else {
                    showAlert('未找到请求详情', 'warning');
                }
            } else {
                throw new Error('获取日志详情失败');
            }
            
        } catch (error) {
            console.error('查看日志详情失败:', error);
            showAlert('查看日志详情失败: ' + error.message, 'danger');
        }
    }
    
    showLogDetail(log) {
        const detail = `
            <div class="row">
                <div class="col-md-6">
                    <h6 class="text-primary">请求信息</h6>
                    <table class="table table-sm">
                        <tr>
                            <th width="120">请求ID:</th>
                            <td><code class="small">${log.request_id}</code></td>
                        </tr>
                        <tr>
                            <th>时间:</th>
                            <td>${formatDateTime(log.timestamp)}</td>
                        </tr>
                        <tr>
                            <th>API Key:</th>
                            <td><code class="small">${log.api_key || 'N/A'}</code></td>
                        </tr>
                        <tr>
                            <th>IP地址:</th>
                            <td>${log.ip_address || 'N/A'}</td>
                        </tr>
                        <tr>
                            <th>User Agent:</th>
                            <td class="small text-muted">${escapeHtml(log.user_agent || 'N/A')}</td>
                        </tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6 class="text-primary">响应信息</h6>
                    <table class="table table-sm">
                        <tr>
                            <th width="120">状态码:</th>
                            <td>
                                <span class="badge ${this.getStatusClass(log.status_code)}">${log.status_code}</span>
                            </td>
                        </tr>
                        <tr>
                            <th>响应时间:</th>
                            <td>
                                <span class="text-${log.response_time_ms > 1000 ? 'warning' : 'success'}">
                                    ${log.response_time_ms}ms
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <th>请求大小:</th>
                            <td>${formatBytes(log.request_size || 0)}</td>
                        </tr>
                        <tr>
                            <th>响应大小:</th>
                            <td>${formatBytes(log.response_size || 0)}</td>
                        </tr>
                        <tr>
                            <th>来源路径:</th>
                            <td><code class="small">${escapeHtml(log.source_path || 'N/A')}</code></td>
                        </tr>
                    </table>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-12">
                    <h6 class="text-primary">请求路径</h6>
                    <div class="alert alert-light">
                        <strong>${log.method}</strong> <code>${escapeHtml(log.path || 'N/A')}</code>
                    </div>
                </div>
            </div>
            
            ${log.target_url ? `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6 class="text-primary">目标地址</h6>
                        <div class="alert alert-light">
                            <code>${escapeHtml(log.target_url)}</code>
                        </div>
                    </div>
                </div>
            ` : ''}
            
            ${log.error_message ? `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6 class="text-danger">错误信息</h6>
                        <div class="alert alert-danger">
                            ${escapeHtml(log.error_message)}
                        </div>
                    </div>
                </div>
            ` : ''}
        `;
        
        $('#logDetailContent').html(detail);
        $('#logDetailModal').modal('show');
    }
    
    refreshLogs() {
        this.loadLogs();
        this.updateStats();
    }
    
    startAutoRefresh() {
        this.autoRefreshInterval = setInterval(() => {
            this.loadLogs();
            this.updateStats();
        }, 30000); // 每30秒刷新一次
    }
    
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }
    
    async exportLogs() {
        try {
            showAlert('正在导出日志...', 'info');
            
            const params = new URLSearchParams({
                limit: 10000 // 导出更多数据
            });
            
            // 添加当前过滤条件
            Object.keys(this.filters).forEach(key => {
                if (this.filters[key]) {
                    params.append(key, this.filters[key]);
                }
            });
            
            const response = await apiClient.get(`/admin/logs?${params}`);
            
            if (response.ok) {
                const logs = await response.json();
                this.downloadLogsAsCSV(logs);
                showAlert('日志导出成功！', 'success');
            } else {
                throw new Error('导出失败');
            }
            
        } catch (error) {
            console.error('导出日志失败:', error);
            showAlert('导出日志失败: ' + error.message, 'danger');
        }
    }
    
    downloadLogsAsCSV(logs) {
        const headers = [
            '时间', 'API Key', '请求方法', '请求路径', '目标地址', 
            '状态码', '响应时间(ms)', '请求大小', '响应大小', 'IP地址', '错误信息'
        ];
        
        const csvContent = [
            headers.join(','),
            ...logs.map(log => [
                formatDateTime(log.timestamp),
                log.api_key || '',
                log.method || '',
                escapeCSV(log.path || ''),
                escapeCSV(log.target_url || ''),
                log.status_code || '',
                log.response_time_ms || '',
                log.request_size || '',
                log.response_size || '',
                log.ip_address || '',
                escapeCSV(log.error_message || '')
            ].join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
    }
}

// 全局函数
function refreshLogs() {
    if (window.auditLogsManager) {
        auditLogsManager.refreshLogs();
    } else {
        console.error('AuditLogsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function applyFilters() {
    if (window.auditLogsManager) {
        auditLogsManager.applyFilters();
    } else {
        console.error('AuditLogsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function resetFilters() {
    if (window.auditLogsManager) {
        auditLogsManager.resetFilters();
    } else {
        console.error('AuditLogsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function changePageSize(size) {
    if (window.auditLogsManager) {
        auditLogsManager.changePageSize(size);
    } else {
        console.error('AuditLogsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function exportLogs() {
    if (window.auditLogsManager) {
        auditLogsManager.exportLogs();
    } else {
        console.error('AuditLogsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

let auditLogsManager;

function waitForApiClient() {
    if (window.apiClient) return Promise.resolve();
    return new Promise(r => {
        const t = setInterval(() => {
            if (window.apiClient) { clearInterval(t); r(); }
        }, 100);
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        await waitForApiClient();
        auditLogsManager = new AuditLogsManager();
        window.auditLogsManager = auditLogsManager;
        console.log('AuditLogsManager ready');
    } catch (e) {
        console.error('Init AuditLogsManager failed', e);
        showAlert('初始化审计日志页面失败: ' + e.message, 'danger');
    }
});