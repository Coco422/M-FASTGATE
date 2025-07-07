/**
 * 审计日志页面的JavaScript逻辑
 */

// Helper function to safely render JSON with formatting and optional highlighting
function safeRenderJson(data, isHighlighted = false) {
    if (data === null || data === undefined || data === '') return '<span class="text-muted">无数据</span>';
    try {
        let jsonStr = data;
        // If data is already an object/array, stringify it first for consistent formatting
        if (typeof data === 'object') {
            jsonStr = JSON.stringify(data, null, 2);
        } else {
            // If it's a string, try to parse and re-stringify to ensure it's valid and formatted
            const parsed = JSON.parse(data);
            jsonStr = JSON.stringify(parsed, null, 2);
        }
        
        let formatted = escapeHtml(jsonStr); // Always escape first
        if (isHighlighted) {
            formatted = highlightJson(formatted);
        }
        return `<pre class="json-content">${formatted}</pre>`;
    } catch (e) {
        // If JSON parsing/formatting fails, display the original data, escaped.
        return `<pre class="json-content text-muted">${escapeHtml(String(data))}</pre>`;
    }
}

// Basic JSON syntax highlighting (primarily for strings, keys, and common literals)
function highlightJson(jsonString) {
    return jsonString
        .replace(/(\"&quot;[\\w\\s\\.\\-\\:]+&quot;\"):/g, '<span class="json-key">$1</span>:') // Keys
        .replace(/: (\".*?\")/g, ': <span class="json-string">$1</span>') // Strings
        .replace(/: (&quot;.*?&quot;)/g, ': <span class="json-string">$1</span>') // Strings with escaped quotes from html
        .replace(/: (true|false)/g, ': <span class="json-boolean">$1</span>') // Booleans
        .replace(/: (null)/g, ': <span class="json-null">$1</span>') // Nulls
        .replace(/: (\\d+\\.?\\d*)/g, ': <span class="json-number">$1</span>'); // Numbers
}

// Helper function to escape values for CSV export
function escapeCSV(value) {
    if (value === null || value === undefined) {
        return '';
    }
    let stringValue = String(value);
    // If the value contains a comma, double quote, or newline, enclose in double quotes
    if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n') || stringValue.includes('\r')) {
        // Escape existing double quotes by replacing them with two double quotes
        stringValue = stringValue.replace(/"/g, '""');
        return `"${stringValue}"`;
    }
    return stringValue;
}

class AuditLogsManager {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 50;
        this.autoRefreshInterval = null;
        this.filters = {
            api_key: '',
            caller: '',
            method: '',
            status_code: '',
            source_path: '',
            time_range: ''
        };
        this.currentLogs = []; // To store the currently loaded logs
        
        this.init();
    }
    
    init() {
        this.loadLogs();
        this.setupEventListeners();
        this.updateStats();
        this.loadKeySources();
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
        $('#apiKeyFilter, #callerFilter, #methodFilter, #statusFilter, #sourcePathFilter, #timeRangeFilter').on('change', () => {
            // 延迟应用，避免频繁请求
            clearTimeout(this.filterTimeout);
            this.filterTimeout = setTimeout(() => {
                this.applyFilters();
            }, 500);
        });
    }
    
    async loadLogs(page = this.currentPage) {
        try {
            showLoading('#logsTable', 7);
            
            const params = new URLSearchParams({
                skip: (page - 1) * this.pageSize,
                limit: this.pageSize
            });
            
            // 添加过滤条件
            if (this.filters.api_key) {
                params.append('api_key', this.filters.api_key);
            }
            if (this.filters.caller) {
                params.append('caller', this.filters.caller);
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
            
            const response = await apiClient.get(`/logs?${params}`);
            
            if (response.ok) {
                const logs = await response.json();
                this.currentLogs = logs; // Store fetched logs
                this.renderLogs(logs);
                this.updateCurrentCount(logs.length);
                this.updatePagination(logs.length);
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
        } catch (error) {
            console.error('加载审计日志失败:', error);
            showError('#logsTable', '加载审计日志失败: ' + error.message, 7);
            showAlert('加载审计日志失败: ' + error.message, 'danger');
            this.currentLogs = []; // Clear logs on error
        }
    }
    
    renderLogs(logs) {
        const tbody = $('#logsTable');
        
        if (!logs || logs.length === 0) {
            tbody.html(`
                <tr>
                    <td colspan="7" class="text-center text-muted py-4">
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
            
            const row = `
                <tr>
                    <td>
                        <small class="text-muted">${formatDateTime(log.created_at)}</small>
                    </td>
                    <td>
                        <small class="text-muted" title="${escapeHtml(log.api_key || '')}">${escapeHtml(log.api_key_source_path || 'N/A')}</small>
                    </td>
                    <td>
                        <span class="badge ${methodClass}">${escapeHtml(log.method)}</span>
                    </td>
                    <td>
                        <small>
                            ${escapeHtml(log.path || 'N/A')}
                            ${log.target_url ? `<br><span class="text-muted">→ ${escapeHtml(log.target_url.substring(0, 60))}...</span>` : ''}
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
                        <button class="btn btn-sm btn-outline-info" 
                                onclick="auditLogsManager.viewLogDetail('${log.request_id}')"
                                title="查看详情">
                            <i class="fas fa-eye"></i>
                        </button>
                    </td>
                </tr>
            `;
            return row;
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
        this.currentPage = 1;
        this.filters = {
            api_key: $('#apiKeyFilter').val().trim(),
            caller: $('#callerFilter').val().trim(),
            method: $('#methodFilter').val(),
            status_code: $('#statusFilter').val().trim(),
            source_path: $('#sourcePathFilter').val().trim(),
            time_range: $('#timeRangeFilter').val()
        };
        this.loadLogs();
        this.updateStats();
    }
    
    resetFilters() {
        $('#apiKeyFilter').val('');
        $('#callerFilter').val('');
        $('#methodFilter').val('');
        $('#statusFilter').val('');
        $('#sourcePathFilter').val('');
        $('#timeRangeFilter').val('');
        
        this.filters = {
            api_key: '',
            caller: '',
            method: '',
            status_code: '',
            source_path: '',
            time_range: ''
        };
        
        this.currentPage = 1;
        this.loadLogs();
        this.updateStats();
    }
    
    async updateStats() {
        try {
            const response = await apiClient.get('/metrics');
            if (response.ok) {
                const stats = await response.json();
                $('#totalRequests').text(stats.total_requests || 0);
                const successRequests = (stats.total_requests || 0) - (stats.total_errors || 0);
                $('#successRequests').text(successRequests);
                $('#errorRequests').text(stats.total_errors || 0);
                $('#avgResponseTime').text(stats.average_response_time || 0);

                // 渲染 Top 5 路径
                this.renderTopList('#topPathsList', stats.top_paths, 'path');

                // 渲染 Top 5 API Keys
                this.renderTopList('#topApiKeysList', stats.top_api_keys, 'source_path');

            } else {
                console.error('获取统计数据失败');
            }
        } catch (error) {
            console.error('更新统计数据时出错:', error);
        }
    }
    
    renderTopList(selector, items, keyField) {
        const list = $(selector);
        list.empty();
        if (items && items.length > 0) {
            items.forEach(item => {
                const li = `
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <span class="text-truncate" title="${escapeHtml(item[keyField])}">${escapeHtml(item[keyField])}</span>
                        <span class="badge bg-primary rounded-pill">${item.count}</span>
                    </li>
                `;
                list.append(li);
            });
        } else {
            list.append('<li class="list-group-item text-muted">暂无数据</li>');
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
        this.pageSize = parseInt(newSize, 10);
        $('#currentPageSize').text(this.pageSize);
        this.currentPage = 1;
        this.loadLogs();
    }
    
    async viewLogDetail(requestId) {
        try {
            showAlert('正在加载日志详情...', 'info', 2000);
            let logDetail = null;
            if (this.currentLogs && this.currentLogs.find) {
                 logDetail = this.currentLogs.find(l => l.request_id === requestId);
            }

            // Check if essential details are present, if not, fetch from server
            if (logDetail && logDetail.request_headers !== undefined && logDetail.response_headers !== undefined) {
                this.showLogDetail(logDetail);
                new bootstrap.Modal(document.getElementById('logDetailModal')).show();
            } else {
                const params = new URLSearchParams({ request_id: requestId, limit: 1 });
                const response = await apiClient.get(`/logs?${params}`); 
                if (response.ok) {
                    const logsArray = await response.json();
                    if (logsArray && logsArray.length > 0) {
                        this.showLogDetail(logsArray[0]);
                        new bootstrap.Modal(document.getElementById('logDetailModal')).show();
                    } else {
                        throw new Error('Log not found with the given request ID.');
                    }
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }
        } catch (error) {
            console.error('加载日志详情失败:', error);
            showAlert('加载日志详情失败: ' + error.message, 'danger');
        }
    }
    
    showLogDetail(log) {
        const contentDiv = document.getElementById('logDetailContent');
        if (!log) {
            contentDiv.innerHTML = '<p class="text-danger">无法加载日志详情。</p>';
            return;
        }

        let html = '<div class="container-fluid"><div class="row gy-3">';

        // Card 1: Basic Information
        html += `
        <div class="col-12">
            <div class="card">
                <div class="card-header"><h6 class="mb-0"><i class="fas fa-info-circle me-2"></i>基础信息</h6></div>
                <div class="card-body">
                    <dl class="row mb-0">
                        <dt class="col-sm-3">请求 ID:</dt><dd class="col-sm-9 text-monospace">${escapeHtml(log.request_id || 'N/A')}</dd>
                        <dt class="col-sm-3">时间戳:</dt><dd class="col-sm-9">${formatDateTime(log.created_at)}</dd>
                        <dt class="col-sm-3">API Key:</dt><dd class="col-sm-9 text-monospace">${escapeHtml(log.api_key || 'N/A')}</dd>
                        <dt class="col-sm-3">用户标识:</dt><dd class="col-sm-9">${escapeHtml(log.source_path || 'N/A')}</dd>
                        <hr class="my-2">
                        <dt class="col-sm-3">请求方法:</dt><dd class="col-sm-9"><span class="badge ${this.getMethodClass(log.method)}">${escapeHtml(log.method || 'N/A')}</span></dd>
                        <dt class="col-sm-3">请求路径:</dt><dd class="col-sm-9 text-break">${escapeHtml(log.path || 'N/A')}</dd>
                        <dt class="col-sm-3">目标 URL:</dt><dd class="col-sm-9 text-break">${escapeHtml(log.target_url || 'N/A')}</dd>
                        <hr class="my-2">
                        <dt class="col-sm-3">状态码:</dt><dd class="col-sm-9"><span class="badge ${this.getStatusClass(log.status_code)}">${log.status_code}</span></dd>
                        <dt class="col-sm-3">响应时间:</dt><dd class="col-sm-9">${log.response_time_ms} ms</dd>
                        ${log.error_message ? `<dt class="col-sm-3 text-danger">错误信息:</dt><dd class="col-sm-9 text-danger text-break">${escapeHtml(log.error_message)}</dd>` : ''}
                    </dl>
                </div>
            </div>
        </div>`;

        // Card 2: Request Details
        html += `
        <div class="col-md-6">
            <div class="card h-100">
                <div class="card-header"><h6 class="mb-0"><i class="fas fa-arrow-up me-2"></i>请求信息</h6></div>
                <div class="card-body" style="overflow-y: auto; max-height: 400px;">
                    <h6 class="card-subtitle mb-2 text-muted">请求头 (${formatBytes(log.request_size || 0)})</h6>
                    ${safeRenderJson(log.request_headers, true)}
                    <h6 class="card-subtitle mt-3 mb-2 text-muted">请求体</h6>
                    ${safeRenderJson(log.request_body, true)}
                </div>
            </div>
        </div>`;

        // Card 3: Response Details
        html += `
        <div class="col-md-6">
            <div class="card h-100">
                <div class="card-header"><h6 class="mb-0"><i class="fas fa-arrow-down me-2"></i>响应信息</h6></div>
                <div class="card-body" style="overflow-y: auto; max-height: 400px;">
                    <h6 class="card-subtitle mb-2 text-muted">响应头 (${formatBytes(log.response_size || 0)})</h6>
                    ${safeRenderJson(log.response_headers, true)}
                    <h6 class="card-subtitle mt-3 mb-2 text-muted">响应体</h6>
                    ${safeRenderJson(log.response_body, true)}
                </div>
            </div>
        </div>`;

        // Card 4: Stream Information (if applicable)
        if (log.is_stream) {
            html += `
            <div class="col-12">
                <div class="card">
                    <div class="card-header"><h6 class="mb-0"><i class="fas fa-stream me-2"></i>流式信息</h6></div>
                    <div class="card-body">
                        <dl class="row mb-0">
                            <dt class="col-sm-3">是否流式:</dt><dd class="col-sm-9">是</dd>
                            <dt class="col-sm-3">数据块数量:</dt><dd class="col-sm-9">${log.stream_chunks || 0}</dd>
                        </dl>
                    </div>
                </div>
            </div>`;
        }
        
        html += '</div></div>'; // Close row and container-fluid
        contentDiv.innerHTML = html;
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
        showAlert('正在准备导出数据...', 'info');
        try {
            // Fetch all logs for export (consider pagination if dataset is very large)
            // For now, let's assume we fetch a reasonable number, e.g., up to 5000 logs.
            // Or, ideally, the backend should provide a dedicated export endpoint.
            const maxLogsToExport = 5000; 
            const params = new URLSearchParams({
                skip: 0,
                limit: maxLogsToExport
            });
            if (this.filters.api_key) params.append('api_key', this.filters.api_key);
            if (this.filters.caller) params.append('caller', this.filters.caller);
            if (this.filters.method) params.append('method', this.filters.method);
            if (this.filters.status_code) params.append('status_code', this.filters.status_code);
            if (this.filters.source_path) params.append('source_path', this.filters.source_path);
            // Add time_range to params if it's implemented and needed for export

            const response = await apiClient.get(`/logs?${params}`);
            if (response.ok) {
                const logsToExport = await response.json();
                if (logsToExport && logsToExport.length > 0) {
                    this.downloadLogsAsCSV(logsToExport);
                    showAlert('日志已成功导出!', 'success');
                } else {
                    showAlert('没有可导出的日志数据。', 'warning');
                }
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('导出日志失败:', error);
            showAlert('导出日志失败: ' + error.message, 'danger');
        }
    }
    
    downloadLogsAsCSV(logs) {
        if (!logs || logs.length === 0) {
            showAlert('没有可导出的日志数据。', 'warning');
            return;
        }

        const headers = [
            'ID', 'Request ID', 'API Key', 'User Identifier (Source Path)', 'Method', 'Path',
            'Target URL', 'Status Code', 'Response Time (ms)', 'Request Size (bytes)', 
            'Response Size (bytes)', 'User Agent', 'IP Address', 'Error Message',
            'Is Stream', 'Stream Chunks', 'Created At',
            'Request Headers', 'Request Body', 'Response Headers', 'Response Body'
        ];

        const csvRows = [];
        csvRows.push(headers.join(',')); // Add header row

        logs.forEach(log => {
            const row = [
                escapeCSV(log.id),
                escapeCSV(log.request_id),
                escapeCSV(log.api_key),
                escapeCSV(log.source_path),
                escapeCSV(log.method),
                escapeCSV(log.path),
                escapeCSV(log.target_url),
                escapeCSV(log.status_code),
                escapeCSV(log.response_time_ms),
                escapeCSV(log.request_size),
                escapeCSV(log.response_size),
                escapeCSV(log.user_agent),
                escapeCSV(log.ip_address),
                escapeCSV(log.error_message),
                escapeCSV(log.is_stream),
                escapeCSV(log.stream_chunks),
                escapeCSV(formatDateTime(log.created_at)), // Format datetime for readability
                escapeCSV(log.request_headers),
                escapeCSV(log.request_body),
                escapeCSV(log.response_headers),
                escapeCSV(log.response_body)
            ];
            csvRows.push(row.join(','));
        });

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        if (link.download !== undefined) { // Check for download attribute support
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            const now = new Date();
            const timestamp = `${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}_${now.getHours().toString().padStart(2, '0')}${now.getMinutes().toString().padStart(2, '0')}${now.getSeconds().toString().padStart(2, '0')}`;
            link.setAttribute('download', `audit_logs_${timestamp}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        } else {
            showAlert('浏览器不支持直接下载 CSV 文件。', 'warning');
        }
    }

    // Add copyLogDetails function globally or within the class
    copyLogDetails() {
        const contentDiv = document.getElementById('logDetailContent');
        if (contentDiv) {
            // Attempt to create a more readable text format
            let textToCopy = "";
            contentDiv.querySelectorAll('.card').forEach(card => {
                const header = card.querySelector('.card-header h6');
                if (header) {
                    textToCopy += `\n--- ${header.innerText.trim()} ---\n`;
                }
                card.querySelectorAll('dl.row dt, dl.row dd').forEach(el => {
                    textToCopy += `${el.tagName === 'DT' ? el.innerText.trim() + ":" : el.innerText.trim() + "\n"}`;
                });
                card.querySelectorAll('pre.json-content').forEach((pre, index) => {
                    const subtitle = pre.previousElementSibling;
                    if (subtitle && subtitle.classList.contains('card-subtitle')) {
                         textToCopy += `\n${subtitle.innerText.trim()}:\n`;
                    }
                    textToCopy += pre.innerText + '\n';
                });
                textToCopy += '\n';
            });

            navigator.clipboard.writeText(textToCopy.trim())
                .then(() => {
                    showAlert('日志详情已复制到剪贴板', 'success');
                })
                .catch(err => {
                    console.error('复制失败:', err);
                    showAlert('复制日志详情失败', 'danger');
                });
        }
    }

    async loadKeySources() {
        try {
            const response = await apiClient.get('/keys/sources');
            if (response.ok) {
                const sources = await response.json();
                const select = $('#callerFilter');
                sources.forEach(source => {
                    select.append(`<option value="${escapeHtml(source)}">${escapeHtml(source)}</option>`);
                });
            }
        } catch (error) {
            console.error('加载Key来源失败:', error);
        }
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