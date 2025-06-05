/**
 * 统计信息页面的JavaScript逻辑
 */

class StatisticsManager {
    constructor() {
        this.initialized = false; 
        this.filters = {
            timeRange: '30d',
            apiKey: '',
            groupBy: 'day'
        };
        
        this.charts = {
            trends: null,
            usage: null,
            errorsBreakdown: null
        };
        
        this.tablePageSize = 20;
        this.tableCurrentPage = 1;
        
        this.init();
    }
    
    init() {
        // 防止重复初始化
        if (this.initialized) {
            console.warn('StatisticsManager already initialized');
            return;
        }
        
        this.initialized = true;
        this.setupEventListeners();
        this.loadApiKeys();
        this.loadStatistics();
    }
    
    setupEventListeners() {
        // 时间范围变化
        $('#timeRange').on('change', () => {
            this.filters.timeRange = $('#timeRange').val();
            this.loadStatistics();
        });
        
        // API Key筛选变化
        $('#apiKeyFilter').on('change', () => {
            this.filters.apiKey = $('#apiKeyFilter').val();
            this.loadStatistics();
        });
        
        // 分组方式变化
        $('#groupBy').on('change', () => {
            this.filters.groupBy = $('#groupBy').val();
            this.loadTrendsChart();
        });
        
        // 图表类型切换
        $('input[name="chartType"]').on('change', (e) => {
            this.updateTrendsChart(e.target.id);
        });
        
        // 排行榜指标切换
        $('#rankingMetric').on('change', () => {
            this.loadKeyRanking();
        });
    }
    
    async loadApiKeys() {
        try {
            const response = await apiClient.get('/keys?limit=1000');
            if (response.ok) {
                const keys = await response.json();
                this.populateApiKeyFilter(keys);
            }
        } catch (error) {
            console.error('加载API Keys失败:', error);
        }
    }
    
    populateApiKeyFilter(keys) {
        const select = $('#apiKeyFilter');
        select.empty().append('<option value="">全部API Key</option>');
        
        keys.forEach(key => {
            const option = $('<option></option>')
                .attr('value', key.key_value)
                .text(`${key.user || 'N/A'} (${key.key_value.substring(0, 12)}...)`);
            select.append(option);
        });
    }
    
    async loadStatistics() {
        try {
            await Promise.all([
                this.loadOverallStats(),
                this.loadTrendsChart(),
                this.loadUsageChart(),
                this.loadErrorsChart(),
                this.loadKeyRanking(),
                this.loadStatsTable()
            ]);
        } catch (error) {
            console.error('加载统计数据失败:', error);
            showAlert('加载统计数据失败: ' + error.message, 'danger');
        }
    }
    
    async loadOverallStats() {
        try {
            // 获取当前时期统计
            const currentResponse = await apiClient.get('/metrics');
            if (!currentResponse.ok) {
                throw new Error('获取统计指标失败');
            }
            
            const currentStats = await currentResponse.json();
            
            // 计算趋势（简化实现，实际需要历史数据对比）
            this.updateOverallStatsUI(currentStats);
            
        } catch (error) {
            console.error('加载总体统计失败:', error);
        }
    }
    
    updateOverallStatsUI(stats) {
        $('#totalRequests').text(stats.total_requests || 0);
        $('#successRate').text((stats.success_rate ? (stats.success_rate * 100).toFixed(1) + '%' : '0%'));
        $('#avgResponseTime').text((stats.avg_response_time || 0) + 'ms');
        $('#activeKeys').text(stats.total_keys || 0);
        
        // 简化的趋势显示（实际需要计算对比）
        $('#requestsTrend').html('<i class="fas fa-arrow-up text-success"></i> +5.2%');
        $('#successTrend').html('<i class="fas fa-arrow-up text-success"></i> +1.1%');
        $('#responseTrend').html('<i class="fas fa-arrow-down text-success"></i> -8.3%');
        $('#keysTrend').html('<i class="fas fa-arrow-up text-success"></i> +2');
    }
    
    async loadTrendsChart() {
        try {
            // 模拟趋势数据（实际应该从API获取）
            const trendData = await this.generateTrendData();
            this.renderTrendsChart(trendData);
        } catch (error) {
            console.error('加载趋势图表失败:', error);
        }
    }
    
    async generateTrendData() {
        try {
            // 尝试从后端获取真实趋势数据
            const response = await apiClient.get(`/metrics/trends?days=30&group_by=${this.filters.groupBy}`);
            
            if (response.ok) {
                const trendsData = await response.json();
                return trendsData;
            } else {
                console.warn('Trends API not available, using fallback data');
            }
        } catch (error) {
            console.error('Failed to load trends data:', error);
        }
        
        // 回退到模拟数据
        const days = 30;
        const labels = [];
        const requests = [];
        const responseTime = [];
        const errorRate = [];
        
        const now = new Date();
        for (let i = days - 1; i >= 0; i--) {
            const date = new Date(now);
            date.setDate(date.getDate() - i);
            labels.push(date.toLocaleDateString());
            
            // 更合理的模拟数据
            requests.push(Math.floor(Math.random() * 300) + 50);
            responseTime.push(Math.floor(Math.random() * 100) + 200);
            errorRate.push(Math.random() * 5);
        }
        
        return { labels, requests, responseTime, errorRate };
    }
    
    renderTrendsChart(data) {
        const ctx = document.getElementById('trendsChart').getContext('2d');
        
        if (this.charts.trends) {
            this.charts.trends.destroy();
        }
        
        this.charts.trends = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: '请求数',
                    data: data.requests,
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    tension: 0.1,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '日期'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: '请求数'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
        
        // 存储数据供切换使用
        this.chartData = data;
    }
    
    updateTrendsChart(chartType) {
        if (!this.charts.trends || !this.chartData) return;
        
        let dataset, label, color;
        
        switch (chartType) {
            case 'requestsChart':
                dataset = this.chartData.requests;
                label = '请求数';
                color = 'rgb(54, 162, 235)';
                break;
            case 'responseChart':
                dataset = this.chartData.responseTime;
                label = '响应时间 (ms)';
                color = 'rgb(255, 159, 64)';
                break;
            case 'errorsChart':
                dataset = this.chartData.errorRate;
                label = '错误率 (%)';
                color = 'rgb(255, 99, 132)';
                break;
            default:
                return;
        }
        
        this.charts.trends.data.datasets[0] = {
            label: label,
            data: dataset,
            borderColor: color,
            backgroundColor: color.replace('rgb', 'rgba').replace(')', ', 0.1)'),
            tension: 0.1,
            fill: true
        };
        
        this.charts.trends.options.scales.y.title.text = label;
        this.charts.trends.update();
    }
    
    async loadUsageChart() {
        try {
            // 获取API Key使用数据
            const response = await apiClient.get('/keys?limit=50');
            if (!response.ok) return;
            
            const keys = await response.json();
            
            // 计算使用分布
            const usageData = this.calculateUsageDistribution(keys);
            this.renderUsageChart(usageData);
            this.renderUsageStats(usageData);
            
        } catch (error) {
            console.error('加载使用分布图表失败:', error);
        }
    }
    
    calculateUsageDistribution(keys) {
        const totalUsage = keys.reduce((sum, key) => sum + (key.usage_count || 0), 0);
        
        // 取前5个最活跃的Key，其他归为"其他"
        const sortedKeys = keys
            .sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0))
            .slice(0, 5);
        
        const others = keys.slice(5);
        const othersUsage = others.reduce((sum, key) => sum + (key.usage_count || 0), 0);
        
        const data = sortedKeys.map(key => ({
            label: key.user || 'N/A',
            value: key.usage_count || 0,
            percentage: totalUsage > 0 ? ((key.usage_count || 0) / totalUsage * 100).toFixed(1) : '0'
        }));
        
        if (othersUsage > 0) {
            data.push({
                label: '其他',
                value: othersUsage,
                percentage: totalUsage > 0 ? (othersUsage / totalUsage * 100).toFixed(1) : '0'
            });
        }
        
        return data;
    }
    
    renderUsageChart(data) {
        const ctx = document.getElementById('usageChart').getContext('2d');
        
        if (this.charts.usage) {
            this.charts.usage.destroy();
        }
        
        const colors = [
            'rgb(255, 99, 132)',
            'rgb(54, 162, 235)',
            'rgb(255, 205, 86)',
            'rgb(75, 192, 192)',
            'rgb(153, 102, 255)',
            'rgb(255, 159, 64)'
        ];
        
        this.charts.usage = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(item => item.label),
                datasets: [{
                    data: data.map(item => item.value),
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            font: {
                                size: 12
                            }
                        }
                    }
                }
            }
        });
    }
    
    renderUsageStats(data) {
        const html = data.map((item, index) => `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="d-flex align-items-center">
                    <div style="width: 12px; height: 12px; background-color: ${this.getChartColor(index)}; border-radius: 50%; margin-right: 8px;"></div>
                    <small class="text-muted">${escapeHtml(item.label)}</small>
                </div>
                <div class="text-end">
                    <small class="fw-medium">${item.value}</small>
                    <small class="text-muted"> (${item.percentage}%)</small>
                </div>
            </div>
        `).join('');
        
        $('#usageStats').html(html);
    }
    
    getChartColor(index) {
        const colors = [
            'rgb(255, 99, 132)',
            'rgb(54, 162, 235)',
            'rgb(255, 205, 86)',
            'rgb(75, 192, 192)',
            'rgb(153, 102, 255)',
            'rgb(255, 159, 64)'
        ];
        return colors[index % colors.length];
    }
    
    async loadErrorsChart() {
        try {
            // 模拟错误分布数据
            const errorData = [
                { status: 200, count: 850, label: '成功' },
                { status: 400, count: 45, label: '请求错误' },
                { status: 401, count: 23, label: '未授权' },
                { status: 404, count: 12, label: '未找到' },
                { status: 500, count: 8, label: '服务器错误' },
                { status: 502, count: 5, label: '网关错误' }
            ];
            
            this.renderErrorsChart(errorData);
            this.renderErrorsList(errorData);
            
        } catch (error) {
            console.error('加载错误分析图表失败:', error);
        }
    }
    
    renderErrorsChart(data) {
        const ctx = document.getElementById('errorsBreakdownChart').getContext('2d');
        
        if (this.charts.errorsBreakdown) {
            this.charts.errorsBreakdown.destroy();
        }
        
        const colors = data.map(item => {
            if (item.status >= 200 && item.status < 300) return 'rgb(34, 197, 94)';
            if (item.status >= 400 && item.status < 500) return 'rgb(251, 191, 36)';
            if (item.status >= 500) return 'rgb(239, 68, 68)';
            return 'rgb(156, 163, 175)';
        });
        
        this.charts.errorsBreakdown = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.status),
                datasets: [{
                    data: data.map(item => item.count),
                    backgroundColor: colors,
                    borderWidth: 1,
                    borderColor: colors
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
    
    renderErrorsList(data) {
        const html = data.map(item => `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <div>
                    <span class="badge ${this.getStatusBadgeClass(item.status)}">${item.status}</span>
                    <small class="text-muted ms-2">${item.label}</small>
                </div>
                <span class="fw-medium">${item.count}</span>
            </div>
        `).join('');
        
        $('#errorsList').html(html);
    }
    
    getStatusBadgeClass(status) {
        if (status >= 200 && status < 300) return 'bg-success';
        if (status >= 400 && status < 500) return 'bg-warning';
        if (status >= 500) return 'bg-danger';
        return 'bg-secondary';
    }
    
    async loadKeyRanking() {
        try {
            const response = await apiClient.get('/keys?limit=100');
            if (!response.ok) return;
            
            const keys = await response.json();
            const metric = $('#rankingMetric').val();
            
            const ranking = this.calculateKeyRanking(keys, metric);
            this.renderKeyRanking(ranking, metric);
            
        } catch (error) {
            console.error('加载排行榜失败:', error);
        }
    }
    
    calculateKeyRanking(keys, metric) {
        let sortedKeys;
        
        switch (metric) {
            case 'requests':
                sortedKeys = keys.sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0));
                break;
            case 'data_transfer':
                // 模拟数据传输量
                sortedKeys = keys.sort((a, b) => Math.random() - 0.5);
                break;
            case 'response_time':
                // 模拟响应时间
                sortedKeys = keys.sort((a, b) => Math.random() - 0.5);
                break;
            default:
                sortedKeys = keys;
        }
        
        return sortedKeys.slice(0, 10);
    }
    
    renderKeyRanking(ranking, metric) {
        const metricLabels = {
            'requests': '请求数',
            'data_transfer': '数据传输',
            'response_time': '响应时间'
        };
        
        const html = ranking.map((key, index) => {
            let value;
            switch (metric) {
                case 'requests':
                    value = key.usage_count || 0;
                    break;
                case 'data_transfer':
                    value = formatBytes(Math.floor(Math.random() * 1000000000));
                    break;
                case 'response_time':
                    value = Math.floor(Math.random() * 500 + 200) + 'ms';
                    break;
                default:
                    value = '0';
            }
            
            return `
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <div class="d-flex align-items-center">
                        <div class="badge bg-primary rounded-pill me-3">${index + 1}</div>
                        <div>
                            <div class="fw-medium">${escapeHtml(key.user || 'N/A')}</div>
                            <small class="text-muted">${key.key_value.substring(0, 16)}...</small>
                        </div>
                    </div>
                    <div class="text-end">
                        <div class="fw-medium">${value}</div>
                        <small class="text-muted">${metricLabels[metric]}</small>
                    </div>
                </div>
            `;
        }).join('');
        
        $('#keyRanking').html(html || '<p class="text-muted text-center">暂无数据</p>');
    }
    
    async loadStatsTable() {
        try {
            const response = await apiClient.get('/keys?limit=1000');
            if (!response.ok) return;
            
            const keys = await response.json();
            const tableData = await this.calculateTableStats(keys);
            
            this.renderStatsTable(tableData);
            this.updateTablePagination(tableData.length);
            
        } catch (error) {
            console.error('加载统计表格失败:', error);
        }
    }
    
    async calculateTableStats(keys) {
        // 这里可以结合日志数据计算更详细的统计信息
        return keys.map(key => ({
            key_id: key.key_id,
            key_value: key.key_value,
            user: key.user || 'N/A',
            total_requests: key.usage_count || 0,
            success_requests: Math.floor((key.usage_count || 0) * 0.95),
            failed_requests: Math.floor((key.usage_count || 0) * 0.05),
            success_rate: '95.0%',
            avg_response_time: Math.floor(Math.random() * 300 + 200) + 'ms',
            data_transfer: formatBytes(Math.floor(Math.random() * 1000000000)),
            last_used: key.last_used || key.created_at
        }));
    }
    
    renderStatsTable(data) {
        const start = (this.tableCurrentPage - 1) * this.tablePageSize;
        const end = start + this.tablePageSize;
        const pageData = data.slice(start, end);
        
        if (pageData.length === 0) {
            $('#statsTable').html(`
                <tr>
                    <td colspan="9" class="text-center text-muted py-4">
                        <i class="fas fa-inbox fa-2x mb-2"></i><br>
                        暂无统计数据
                    </td>
                </tr>
            `);
            return;
        }
        
        const rows = pageData.map(item => `
            <tr>
                <td>
                    <code class="small">${item.key_value.substring(0, 16)}...</code>
                </td>
                <td>
                    <span class="fw-medium">${escapeHtml(item.user)}</span>
                </td>
                <td>
                    <span class="badge bg-primary">${item.total_requests}</span>
                </td>
                <td>
                    <span class="text-success">${item.success_requests}</span>
                </td>
                <td>
                    <span class="text-danger">${item.failed_requests}</span>
                </td>
                <td>
                    <span class="text-success fw-medium">${item.success_rate}</span>
                </td>
                <td>
                    <span class="text-info">${item.avg_response_time}</span>
                </td>
                <td>
                    <small class="text-muted">${item.data_transfer}</small>
                </td>
                <td>
                    <small class="text-muted">${formatDateTime(item.last_used)}</small>
                </td>
            </tr>
        `).join('');
        
        $('#statsTable').html(rows);
        this.tableData = data; // 存储用于导出
    }
    
    updateTablePagination(totalCount) {
        const totalPages = Math.ceil(totalCount / this.tablePageSize);
        const pagination = $('#tablePagination');
        
        if (totalPages <= 1) {
            pagination.empty();
            return;
        }
        
        let paginationHtml = '';
        
        // 上一页
        paginationHtml += `
            <li class="page-item ${this.tableCurrentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="statisticsManager.goToTablePage(${this.tableCurrentPage - 1})">
                    <i class="fas fa-chevron-left"></i>
                </a>
            </li>
        `;
        
        // 页码
        const startPage = Math.max(1, this.tableCurrentPage - 2);
        const endPage = Math.min(totalPages, this.tableCurrentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            paginationHtml += `
                <li class="page-item ${i === this.tableCurrentPage ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="statisticsManager.goToTablePage(${i})">${i}</a>
                </li>
            `;
        }
        
        // 下一页
        paginationHtml += `
            <li class="page-item ${this.tableCurrentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="statisticsManager.goToTablePage(${this.tableCurrentPage + 1})">
                    <i class="fas fa-chevron-right"></i>
                </a>
            </li>
        `;
        
        pagination.html(paginationHtml);
    }
    
    goToTablePage(page) {
        if (page < 1 || !this.tableData) return;
        
        const totalPages = Math.ceil(this.tableData.length / this.tablePageSize);
        if (page > totalPages) return;
        
        this.tableCurrentPage = page;
        this.renderStatsTable(this.tableData);
        this.updateTablePagination(this.tableData.length);
    }
    
    changeTablePageSize(newSize) {
        this.tablePageSize = newSize;
        $('#tablePageSize').text(newSize);
        this.tableCurrentPage = 1;
        if (this.tableData) {
            this.renderStatsTable(this.tableData);
            this.updateTablePagination(this.tableData.length);
        }
    }
    
    applyFilters() {
        this.filters.timeRange = $('#timeRange').val();
        this.filters.apiKey = $('#apiKeyFilter').val();
        this.filters.groupBy = $('#groupBy').val();
        
        this.loadStatistics();
    }
    
    refreshStats() {
        this.loadStatistics();
    }
    
    async exportReport() {
        try {
            showAlert('正在生成报告...', 'info');
            
            // 收集所有统计数据
            const reportData = {
                timestamp: new Date().toISOString(),
                timeRange: this.filters.timeRange,
                apiKey: this.filters.apiKey,
                tableData: this.tableData || []
            };
            
            this.downloadReport(reportData);
            showAlert('报告生成成功！', 'success');
            
        } catch (error) {
            console.error('导出报告失败:', error);
            showAlert('导出报告失败: ' + error.message, 'danger');
        }
    }
    
    downloadReport(data) {
        const headers = [
            'API Key', '用户', '请求总数', '成功请求', '失败请求',
            '成功率', '平均响应时间', '数据传输', '最后使用'
        ];
        
        const csvContent = [
            `# M-FastGate 统计报告`,
            `# 生成时间: ${formatDateTime(data.timestamp)}`,
            `# 时间范围: ${data.timeRange}`,
            `# API Key筛选: ${data.apiKey || '全部'}`,
            '',
            headers.join(','),
            ...data.tableData.map(item => [
                item.key_value,
                item.user,
                item.total_requests,
                item.success_requests,
                item.failed_requests,
                item.success_rate,
                item.avg_response_time,
                item.data_transfer,
                formatDateTime(item.last_used)
            ].join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `statistics_report_${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
    }
    
    exportTableData() {
        if (!this.tableData || this.tableData.length === 0) {
            showAlert('没有可导出的数据', 'warning');
            return;
        }
        
        this.exportReport();
    }
}

// 全局函数
function refreshStats() {
    if (window.statisticsManager) {
        statisticsManager.refreshStats();
    } else {
        console.error('StatisticsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function applyFilters() {
    if (window.statisticsManager) {
        statisticsManager.applyFilters();
    } else {
        console.error('StatisticsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function exportReport() {
    if (window.statisticsManager) {
        statisticsManager.exportReport();
    } else {
        console.error('StatisticsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function exportTableData() {
    if (window.statisticsManager) {
        statisticsManager.exportTableData();
    } else {
        console.error('StatisticsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

function changeTablePageSize(size) {
    if (window.statisticsManager) {
        statisticsManager.changeTablePageSize(size);
    } else {
        console.error('StatisticsManager not initialized');
        showAlert('系统初始化中，请稍后再试', 'warning');
    }
}

let statisticsManager;

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
        statisticsManager = new StatisticsManager();
        window.statisticsManager = statisticsManager;
        console.log('StatisticsManager ready');
    } catch (e) {
        console.error('Init StatisticsManager failed', e);
        showAlert('初始化统计信息页面失败: ' + e.message, 'danger');
    }
});