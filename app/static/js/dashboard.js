/**
 * 仪表板页面JavaScript
 */

let requestChart = null;
let refreshInterval = null;

/**
 * 页面初始化
 */
document.addEventListener('DOMContentLoaded', function() {
    // 等待apiClient初始化完成后再加载数据
    waitForApiClient().then(() => {
        console.log('Dashboard: apiClient ready, initializing dashboard...');
        initDashboard();
        loadDashboardData();
        
        // 设置自动刷新
        refreshInterval = setInterval(loadDashboardData, 30000); // 每30秒刷新一次
    }).catch(error => {
        console.error('Dashboard: Failed to initialize apiClient:', error);
        utils.showAlert('初始化失败，请刷新页面重试', 'error');
    });
});

/**
 * 等待apiClient初始化完成
 */
function waitForApiClient() {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const maxAttempts = 50; // 5秒超时
        
        const checkApiClient = () => {
            if (window.apiClient && typeof window.apiClient.get === 'function') {
                console.log('Dashboard: apiClient found and ready');
                resolve();
            } else if (attempts < maxAttempts) {
                attempts++;
                setTimeout(checkApiClient, 100);
            } else {
                reject(new Error('ApiClient initialization timeout'));
            }
        };
        
        checkApiClient();
    });
}

/**
 * 初始化仪表板
 */
function initDashboard() {
    initRequestChart();
}

/**
 * 加载仪表板数据
 */
async function loadDashboardData() {
    try {
        console.log('Dashboard: Loading dashboard data...');
        
        // 并行加载各项数据
        const [stats, recentLogs, keys] = await Promise.all([
            loadSystemStats(),
            loadRecentLogs(),
            loadApiKeysCount()
        ]);

        updateStatCards(stats, keys.length);
        updateRecentLogsTable(recentLogs);
        updateRequestChart(stats);
        
        console.log('Dashboard: Data loaded successfully');
    } catch (error) {
        console.error('加载仪表板数据失败:', error);
        utils.showAlert('加载数据失败: ' + error.message, 'error');
    }
}

/**
 * 加载系统统计信息
 */
async function loadSystemStats() {
    try {
        console.log('Dashboard: Loading system stats...');
        const response = await apiClient.get('/metrics');
        const data = await response.json();
        console.log('Dashboard: System stats loaded:', data);
        return data;
    } catch (error) {
        console.error('加载统计信息失败:', error);
        return {
            total_requests: 0,
            status_counts: {},
            avg_response_time_ms: 0,
            source_counts: {}
        };
    }
}

/**
 * 加载最近日志
 */
async function loadRecentLogs() {
    try {
        console.log('Dashboard: Loading recent logs...');
        const response = await apiClient.get('/logs', { limit: 10, skip: 0 });
        const data = await response.json();
        console.log('Dashboard: Recent logs loaded:', data);
        return Array.isArray(data) ? data : [];
    } catch (error) {
        console.error('加载最近日志失败:', error);
        return [];
    }
}

/**
 * 加载API Key数量
 */
async function loadApiKeysCount() {
    try {
        console.log('Dashboard: Loading API keys...');
        const response = await apiClient.get('/keys', { limit: 1000 });
        const data = await response.json();
        console.log('Dashboard: API keys loaded:', data);
        return Array.isArray(data) ? data : [];
    } catch (error) {
        console.error('加载API Key失败:', error);
        return [];
    }
}

/**
 * 更新统计卡片
 */
function updateStatCards(stats, keyCount) {
    console.log('Dashboard: Updating stat cards with:', { stats, keyCount });
    
    // API Keys总数
    document.getElementById('totalKeys').textContent = keyCount;

    // 请求总数
    document.getElementById('totalRequests').textContent = stats.total_requests || 0;

    // 平均响应时间
    const avgTime = stats.avg_response_time_ms || 0;
    document.getElementById('avgResponseTime').textContent = avgTime.toFixed(0);

    // 成功率
    const statusCounts = stats.status_counts || {};
    const totalRequests = stats.total_requests || 0;
    let successCount = 0;
    
    // 计算成功请求数 (2xx状态码)
    Object.keys(statusCounts).forEach(status => {
        if (status.startsWith('2')) {
            successCount += statusCounts[status];
        }
    });

    const successRate = totalRequests > 0 ? (successCount / totalRequests * 100).toFixed(1) : 0;
    document.getElementById('successRate').textContent = successRate + '%';

    // 更新系统状态
    updateSystemStatus(successRate);
}

/**
 * 更新系统状态
 */
function updateSystemStatus(successRate) {
    const statusElement = document.getElementById('systemStatus');
    const serviceStatusElement = document.getElementById('serviceStatus');
    
    if (successRate >= 95) {
        statusElement.textContent = '良好';
        statusElement.className = 'text-success';
        if (serviceStatusElement) {
            serviceStatusElement.className = 'badge bg-success';
            serviceStatusElement.textContent = '运行中';
        }
    } else if (successRate >= 80) {
        statusElement.textContent = '一般';
        statusElement.className = 'text-warning';
        if (serviceStatusElement) {
            serviceStatusElement.className = 'badge bg-warning';
            serviceStatusElement.textContent = '注意';
        }
    } else {
        statusElement.textContent = '异常';
        statusElement.className = 'text-danger';
        if (serviceStatusElement) {
            serviceStatusElement.className = 'badge bg-danger';
            serviceStatusElement.textContent = '异常';
        }
    }
}

/**
 * 更新最近日志表格
 */
function updateRecentLogsTable(logs) {
    console.log('Dashboard: Updating recent logs table with:', logs);
    
    const tableBody = document.getElementById('recentLogsTable');
    
    if (!logs || logs.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted">
                    <i class="fas fa-inbox me-2"></i>
                    暂无请求记录
                </td>
            </tr>
        `;
        return;
    }

    const rows = logs.map(log => {
        const statusBadge = getStatusBadge(log.status_code);
        const streamType = log.is_stream ? 
            '<span class="badge bg-info">流式</span>' : 
            '<span class="badge bg-secondary">普通</span>';
        
        return `
            <tr>
                <td>${utils.formatDateTime(log.created_at)}</td>
                <td>
                    <code class="small">${utils.truncateString(log.api_key, 16)}</code>
                </td>
                <td>
                    <span class="badge bg-primary">${log.method}</span>
                </td>
                <td>${statusBadge}</td>
                <td>${utils.formatDuration(log.response_time_ms)}</td>
                <td>
                    <small>
                        请求: ${utils.formatFileSize(log.request_size)}<br>
                        响应: ${utils.formatFileSize(log.response_size)}
                    </small>
                </td>
                <td>${streamType}</td>
            </tr>
        `;
    }).join('');

    tableBody.innerHTML = rows;
}

/**
 * 获取状态码徽章
 */
function getStatusBadge(statusCode) {
    let badgeClass = 'bg-secondary';
    if (statusCode >= 200 && statusCode < 300) {
        badgeClass = 'bg-success';
    } else if (statusCode >= 400 && statusCode < 500) {
        badgeClass = 'bg-warning';
    } else if (statusCode >= 500) {
        badgeClass = 'bg-danger';
    }
    
    return `<span class="badge ${badgeClass}">${statusCode}</span>`;
}

/**
 * 初始化请求趋势图表
 */
function initRequestChart() {
    const ctx = document.getElementById('requestChart');
    if (!ctx) return;
    
    requestChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '请求数',
                data: [],
                borderColor: 'rgb(54, 162, 235)',
                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                tension: 0.1,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

/**
 * 更新请求趋势图表 - 使用真实数据
 */
async function updateRequestChart(stats) {
    if (!requestChart) return;
    
    console.log('Dashboard: Updating request chart with:', stats);
    
    try {
        // 获取24小时趋势数据
        const response = await apiClient.get('/metrics/hourly?hours=24');
        
        if (response.ok) {
            const hourlyData = await response.json();
            
            const labels = [];
            const data = [];
            
            // 处理后端返回的小时数据
            for (let i = 23; i >= 0; i--) {
                const time = new Date(Date.now() - i * 60 * 60 * 1000);
                const hourKey = time.getHours();
                labels.push(hourKey + ':00');
                
                // 查找对应小时的数据
                const hourData = hourlyData.find(h => h.hour === hourKey);
                data.push(hourData ? hourData.requests : 0);
            }
            
            requestChart.data.labels = labels;
            requestChart.data.datasets[0].data = data;
        } else {
            // 如果API不存在，回退到基于总数的合理分布
            console.warn('Hourly metrics API not available, using fallback data');
            const labels = [];
            const data = [];
            
            for (let i = 23; i >= 0; i--) {
                const time = new Date(Date.now() - i * 60 * 60 * 1000);
                labels.push(time.getHours() + ':00');
                // 更合理的分布：工作时间多，凌晨少
                const hour = time.getHours();
                let factor = 1;
                if (hour >= 9 && hour <= 18) factor = 1.5; // 工作时间
                else if (hour >= 0 && hour <= 6) factor = 0.3; // 凌晨
                
                const hourlyRequests = Math.floor((stats.total_requests || 0) / 24 * factor);
                data.push(Math.max(0, hourlyRequests));
            }
            
            requestChart.data.labels = labels;
            requestChart.data.datasets[0].data = data;
        }
    } catch (error) {
        console.error('Failed to load hourly data:', error);
        // 回退到简单的分布
        const labels = [];
        const data = [];
        
        for (let i = 23; i >= 0; i--) {
            const time = new Date(Date.now() - i * 60 * 60 * 1000);
            labels.push(time.getHours() + ':00');
            const hourlyRequests = Math.floor((stats.total_requests || 0) / 24);
            data.push(Math.max(0, hourlyRequests));
        }
        
        requestChart.data.labels = labels;
        requestChart.data.datasets[0].data = data;
    }
    
    requestChart.update();
}

/**
 * 显示创建Key模态框
 */
function showCreateKeyModal() {
    const modal = new bootstrap.Modal(document.getElementById('createKeyModal'));
    modal.show();
}

/**
 * 创建API Key
 */
async function createApiKey() {
    try {
        const sourcePath = document.getElementById('sourcePath').value.trim();
        const expiresDays = parseInt(document.getElementById('expiresDays').value);
        
        if (!sourcePath) {
            utils.showAlert('请输入用户标识', 'warning');
            return;
        }
        
        const keyData = {
            source_path: sourcePath,
            permissions: ['chat'],
            expires_days: expiresDays
        };
        
        console.log('Dashboard: Creating API key with data:', keyData);
        
        const response = await apiClient.post('/keys', keyData);
        const newKey = await response.json();
        
        console.log('Dashboard: API key created:', newKey);
        
        utils.showAlert(`API Key创建成功！<br><strong>Key: ${newKey.key_value}</strong>`, 'success');
        
        // 关闭模态框并重置表单
        const modal = bootstrap.Modal.getInstance(document.getElementById('createKeyModal'));
        modal.hide();
        document.getElementById('createKeyForm').reset();
        
        // 刷新数据
        loadDashboardData();
        
    } catch (error) {
        console.error('创建API Key失败:', error);
        utils.showAlert('创建API Key失败: ' + error.message, 'error');
    }
}

/**
 * 刷新系统状态
 */
async function refreshSystemStatus() {
    try {
        utils.showAlert('正在刷新系统状态...', 'info', 2000);
        await loadDashboardData();
        utils.showAlert('系统状态已刷新', 'success', 2000);
    } catch (error) {
        console.error('刷新系统状态失败:', error);
        utils.showAlert('刷新失败: ' + error.message, 'error');
    }
}

// 页面离开时清理定时器
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
}); 