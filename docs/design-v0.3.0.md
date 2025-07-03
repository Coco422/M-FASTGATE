# M-FastGate v0.3.0 设计文档

## 1. 版本概述

v0.3.0版本的主要目标是提升系统在特定生产环境下的兼容性。根据生产环境网关的限制，本次升级将所有API端点的写操作（更新、删除）统一为使用 `POST` HTTP方法，替代原有的 `PUT` 和 `DELETE` 方法。

此变更涉及后端API接口的重新定义以及前端调用方式的相应修改。

## 2. API 接口变更

为了遵循仅允许 `GET` 和 `POST` 请求的原则，我们对管理API中所有使用 `PUT` 和 `DELETE` 方法的端点进行了重构。

### 2.1. 变更原因

生产环境的网关或防火墙策略限制了除 `GET` 和 `POST` 之外的HTTP方法。为确保M-FastGate在这些环境下的正常运行，必须将所有写操作API统一为 `POST` 方法。

### 2.2. 端点变更详情

所有变更均在 `/admin` API路由下。

#### API Key 管理

-   **更新API Key**:
    -   **旧**: `PUT /keys/{key_id}`
    -   **新**: `POST /keys/update/{key_id}`
-   **删除API Key**:
    -   **旧**: `DELETE /keys/{key_id}`
    -   **新**: `POST /keys/delete/{key_id}`

#### 代理路由管理

-   **更新代理路由**:
    -   **旧**: `PUT /routes/{route_id}`
    -   **新**: `POST /routes/update/{route_id}`
-   **删除代理路由**:
    -   **旧**: `DELETE /routes/{route_id}`
    -   **新**: `POST /routes/delete/{route_id}`

### 2.3. 实现细节

-   **后端**:
    -   修改了 `app/api/admin.py` 文件中相关路由的装饰器，从 `@router.put` 和 `@router.delete` 改为 `@router.post`，并更新了URL路径以区分操作（例如 `.../update/{id}` 和 `.../delete/{id}`）。

-   **前端**:
    -   修改了 `app/static/js/api_keys.js` 和 `app/static/js/routes.js` 文件。
    -   将所有调用 `apiClient.put()` 和 `apiClient.delete()` 的地方改为调用 `apiClient.post()`，并更新了请求的URL以匹配后端新的API端点。

## 3. Bug 修复

在进行本次升级的过程中，发现并修复了一个前端的Bug：

-   **问题描述**: `app/static/js/routes.js` 文件中的 `toggleRoute` 函数之前错误地使用了 `PUT` 方法来调用后端的 `/routes/{route_id}/toggle` 接口，而该接口在之前版本中就已经是 `POST` 方法。
-   **修复措施**: 已将 `toggleRoute` 函数中的 `apiClient.put()` 调用更正为 `apiClient.post()`，确保了前端调用与后端接口定义一致。

## 4. 总结

v0.3.0 版本的核心是提升部署兼容性，通过统一API写操作为 `POST` 方法来达成此目标。此次升级还顺带修复了一个前端的潜在Bug，提升了系统的稳定性。 