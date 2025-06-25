/**
 * M-FastGate 管理界面公共JavaScript函数
 */

// 全局变量
let adminToken = null;
let apiClient = null;

/**
 * API客户端类
 */
class APIClient {
    constructor() {
        this.baseURL = window.apiBaseUrl || '/admin';
    }
    
    // 获取完整的API URL（包含token）
    getApiUrl(endpoint) {
        let url = this.baseURL + endpoint;
        
        // 如果endpoint不包含token参数，则添加
        if (adminToken && !url.includes('token=')) {
            const separator = url.includes('?') ? '&' : '?';
            url += separator + 'token=' + encodeURIComponent(adminToken);
        }
        
        return url;
    }
    
    async get(endpoint, params = {}) {
        let url = this.getApiUrl(endpoint);
        
        // 添加查询参数
        if (params && Object.keys(params).length > 0) {
            const queryString = new URLSearchParams(params).toString();
            const separator = url.includes('?') ? '&' : '?';
            url += separator + queryString;
        }
        
        console.log('API GET:', url); // 调试日志
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return response;
    }
    
    async post(endpoint, data) {
        const url = this.getApiUrl(endpoint);
        console.log('API POST:', url, data); // 调试日志
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return response;
    }
    
    async put(endpoint, data) {
        const url = this.getApiUrl(endpoint);
        console.log('API PUT:', url, data); // 调试日志
        
        const response = await fetch(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return response;
    }
    
    async delete(endpoint) {
        const url = this.getApiUrl(endpoint);
        console.log('API DELETE:', url); // 调试日志
        
        const response = await fetch(url, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return response;
    }
}

/**
 * 页面加载完成后的初始化
 */

// 立即初始化API客户端，因为它不依赖于DOM，且其他脚本需要立即使用它
// 它依赖于在base.html中设置的全局变量 window.apiBaseUrl
initializeApiClient();
initTokenManagement();

$(document).ready(function() {
    console.log('Common.js DOM ready...');
    
    updateLinksWithToken();
    setActiveNavigation();
    
    console.log('Common.js DOM ready setup complete.');
});

/**
 * 初始化Token管理
 */
function initTokenManagement() {
    // 从URL参数中获取token
    adminToken = getUrlParameter('token');
    
    console.log('Admin token:', adminToken); // 调试日志
    
    if (!adminToken) {
        showAlert('缺少访问令牌，请通过正确的URL访问', 'danger');
        return;
    }
}

/**
 * 初始化API客户端
 */
function initializeApiClient() {
    apiClient = new APIClient();
    
    // 将apiClient设置为全局变量，确保其他脚本可以访问
    window.apiClient = apiClient;
    
    console.log('API client initialized:', apiClient); // 调试日志
}

/**
 * 更新页面中所有链接，添加token参数
 */
function updateLinksWithToken() {
    if (!adminToken) return;
    
    const uiPrefix = (window.rootPath || '') + '/admin/ui/';

    // 更新导航链接
    $('a[href^="' + uiPrefix + '"]').each(function() {
        const href = $(this).attr('href');
        const newHref = addTokenToUrl(href);
        $(this).attr('href', newHref);
    });
    
    // 更新表单action（如果有的话）
    $('form[action^="' + uiPrefix + '"]').each(function() {
        const action = $(this).attr('action');
        const newAction = addTokenToUrl(action);
        $(this).attr('action', newAction);
    });
}

/**
 * 设置当前导航项为活跃状态
 */
function setActiveNavigation() {
    const currentPath = window.location.pathname;
    const uiPrefix = (window.rootPath || '') + '/admin/ui/';

    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (href && href.startsWith(uiPrefix)) {
            // 移除token参数后比较
            const linkPath = href.split('?')[0];
            if (linkPath === currentPath) {
                link.classList.add('active');
            }
        }
    });
}

/**
 * 向URL添加token参数
 */
function addTokenToUrl(url) {
    if (!url || !adminToken) return url;
    
    const separator = url.includes('?') ? '&' : '?';
    return url + separator + 'token=' + encodeURIComponent(adminToken);
}

/**
 * 从URL参数中获取指定参数值
 */
function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

/**
 * 页面跳转函数，自动携带token
 */
function navigateToPage(path) {
    const fullUrl = addTokenToUrl(path);
    window.location.href = fullUrl;
}

/**
 * 通用工具函数
 */
class Utils {
    /**
     * 显示消息提示
     */
    static showAlert(message, type = 'info', duration = 5000) {
        const alertId = 'alert-' + Date.now();
        const alertClass = type === 'danger' ? 'alert-danger' : 
                          type === 'success' ? 'alert-success' : 
                          type === 'warning' ? 'alert-warning' : 'alert-info';
        
        const alertHtml = `
            <div id="${alertId}" class="alert ${alertClass} alert-dismissible fade show position-fixed" 
                 style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
                <div>${message}</div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        $('body').append(alertHtml);
        
        // 自动隐藏
        if (duration > 0) {
            setTimeout(() => {
                $(`#${alertId}`).fadeOut(() => {
                    $(`#${alertId}`).remove();
                });
            }, duration);
        }
    }

    /**
     * 格式化日期时间
     */
    static formatDateTime(datetime, showSeconds = true) {
        if (!datetime) return 'N/A';
        
        try {
            const date = new Date(datetime);
            if (isNaN(date.getTime())) return 'N/A';

            const options = {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            };

            if (showSeconds) {
                options.second = '2-digit';
            }

            return date.toLocaleString('zh-CN', options);
        } catch (e) {
            return datetime;
        }
    }

    /**
     * 格式化文件大小
     */
    static formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 格式化毫秒时间
     */
    static formatDuration(ms) {
        if (!ms || ms < 0) return '0ms';
        
        if (ms < 1000) {
            return Math.round(ms) + 'ms';
        } else if (ms < 60000) {
            return (ms / 1000).toFixed(1) + 's';
        } else {
            return Math.floor(ms / 60000) + 'm ' + Math.floor((ms % 60000) / 1000) + 's';
        }
    }

    /**
     * 截断字符串
     */
    static truncateString(str, length = 50) {
        if (!str) return '';
        if (str.length <= length) return str;
        return str.substring(0, length) + '...';
    }

    /**
     * 复制文本到剪贴板
     */
    static async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showAlert('已复制到剪贴板', 'success', 2000);
        } catch (err) {
            console.error('复制失败:', err);
            this.showAlert('复制失败', 'error', 3000);
        }
    }

    /**
     * 防抖函数
     */
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * 生成随机ID
     */
    static generateId() {
        return Math.random().toString(36).substr(2, 9);
    }
}

// 全局实例
window.utils = Utils;

/**
 * 显示加载状态
 */
function showLoading(selector, colspan = 1) {
    $(selector).html(`
        <tr>
            <td colspan="${colspan}" class="text-center text-muted py-4">
                <i class="fas fa-spinner fa-spin me-2"></i>
                加载中...
            </td>
        </tr>
    `);
}

/**
 * 显示错误状态
 */
function showError(selector, message, colspan = 1) {
    $(selector).html(`
        <tr>
            <td colspan="${colspan}" class="text-center text-danger py-4">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${escapeHtml(message)}
            </td>
        </tr>
    `);
}

/**
 * 显示警告信息
 */
function showAlert(message, type = 'info', duration = 5000) {
    Utils.showAlert(message, type, duration);
}

/**
 * HTML转义
 */
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

/**
 * 格式化日期时间
 */
function formatDateTime(dateString) {
    return Utils.formatDateTime(dateString);
}

/**
 * 格式化字节大小
 */
function formatBytes(bytes) {
    return Utils.formatFileSize(bytes);
}

/**
 * 复制文本到剪贴板
 */
function copyToClipboard(text, button) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showCopySuccess(button);
        }).catch(() => {
            fallbackCopyTextToClipboard(text, button);
        });
    } else {
        fallbackCopyTextToClipboard(text, button);
    }
}

function fallbackCopyTextToClipboard(text, button) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showCopySuccess(button);
    } catch (err) {
        showAlert('复制失败，请手动复制', 'warning');
    }
    
    document.body.removeChild(textArea);
}

function showCopySuccess(button) {
    const originalHtml = $(button).html();
    $(button).html('<i class="fas fa-check text-success"></i>');
    
    setTimeout(() => {
        $(button).html(originalHtml);
    }, 1000);
    
    showAlert('已复制到剪贴板', 'success', 2000);
}

/**
 * 防抖函数
 */
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
} 