/**
 * Model Speed Test JavaScript SDK
 * AI模型速度测试框架的 JavaScript SDK
 */

class ModelSpeedTest {
  /**
   * 初始化 SDK 客户端
   * @param {Object} options - 配置选项
   * @param {string} options.baseUrl - API 基础 URL
   * @param {string} options.apiKey - API Key (可选)
   */
  constructor(options = {}) {
    this.baseUrl = options.baseUrl || 'http://localhost:15010';
    this.apiKey = options.apiKey;
    this.eventListeners = new Map();
  }

  /**
   * 发送 HTTP 请求
   * @private
   */
  async _request(method, endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }

    const config = {
      method,
      headers,
      ...options
    };

    if (options.body) {
      config.body = JSON.stringify(options.body);
    }

    const response = await fetch(url, config);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  // ==================== 配置管理 ====================

  /**
   * 获取当前配置
   * @returns {Promise<Object>}
   */
  async getConfig() {
    return this._request('GET', '/config');
  }

  /**
   * 添加模型
   * @param {Object} modelData - 模型数据
   * @returns {Promise<Object>}
   */
  async addModel(modelData) {
    return this._request('POST', '/config/models', { body: modelData });
  }

  /**
   * 更新模型
   * @param {string} modelName - 模型名称
   * @param {Object} modelData - 要更新的字段
   * @returns {Promise<Object>}
   */
  async updateModel(modelName, modelData) {
    return this._request('PUT', `/config/models/${modelName}`, { body: modelData });
  }

  /**
   * 删除模型
   * @param {string} modelName - 模型名称
   * @returns {Promise<Object>}
   */
  async deleteModel(modelName) {
    return this._request('DELETE', `/config/models/${modelName}`);
  }

  /**
   * 添加测试用例
   * @param {Object} testCaseData - 测试用例数据
   * @returns {Promise<Object>}
   */
  async addTestCase(testCaseData) {
    return this._request('POST', '/config/test-cases', { body: testCaseData });
  }

  /**
   * 更新测试用例
   * @param {string} testCaseId - 测试用例 ID
   * @param {Object} testCaseData - 要更新的字段
   * @returns {Promise<Object>}
   */
  async updateTestCase(testCaseId, testCaseData) {
    return this._request('PUT', `/config/test-cases/${testCaseId}`, { body: testCaseData });
  }

  /**
   * 删除测试用例
   * @param {string} testCaseId - 测试用例 ID
   * @returns {Promise<Object>}
   */
  async deleteTestCase(testCaseId) {
    return this._request('DELETE', `/config/test-cases/${testCaseId}`);
  }

  // ==================== 测试控制 ====================

  /**
   * 启动测试
   * @param {Object} options - 测试选项
   * @param {string[]} [options.models] - 要测试的模型名称列表
   * @param {string[]} [options.cases] - 要测试的用例 ID 列表
   * @param {number} [options.testRounds] - 测试轮数
   * @param {number} [options.maxConcurrent] - 最大并发数
   * @param {number} [options.interval] - 请求间隔(秒)
   * @param {string} [options.testName] - 测试名称
   * @param {boolean} [options.concurrent] - 是否启用并发
   * @returns {Promise<Object>}
   */
  async startTest(options = {}) {
    const body = {
      models: options.models || [],
      cases: options.cases || [],
      concurrent: options.concurrent !== false
    };

    if (options.testRounds !== undefined) body.test_rounds = options.testRounds;
    if (options.maxConcurrent !== undefined) body.max_concurrent = options.maxConcurrent;
    if (options.interval !== undefined) body.interval = options.interval;
    if (options.testName !== undefined) body.test_name = options.testName;

    return this._request('POST', '/test/start', { body });
  }

  /**
   * 停止测试
   * @returns {Promise<Object>}
   */
  async stopTest() {
    return this._request('POST', '/test/stop');
  }

  /**
   * 获取测试状态
   * @returns {Promise<Object>}
   */
  async getStatus() {
    return this._request('GET', '/test/status');
  }

  /**
   * 重置测试状态
   * @returns {Promise<Object>}
   */
  async reset() {
    return this._request('POST', '/reset');
  }

  // ==================== 事件流 ====================

  /**
   * 监听 SSE 事件
   * @param {string} eventName - 事件名称
   * @param {Function} callback - 回调函数
   */
  on(eventName, callback) {
    if (!this.eventListeners.has(eventName)) {
      this.eventListeners.set(eventName, []);
    }
    this.eventListeners.get(eventName).push(callback);
  }

  /**
   * 移除事件监听
   * @param {string} eventName - 事件名称
   * @param {Function} callback - 回调函数
   */
  off(eventName, callback) {
    if (!this.eventListeners.has(eventName)) return;
    
    const listeners = this.eventListeners.get(eventName);
    const index = listeners.indexOf(callback);
    if (index > -1) {
      listeners.splice(index, 1);
    }
  }

  /**
   * 开始监听事件流
   * @returns {EventSource}
   */
  connectEvents() {
    const url = `${this.baseUrl}/events`;
    const headers = {};
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }

    // 使用 fetch API 实现 SSE
    this._eventSource = new EventSource(url, { headers });

    this._eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const eventName = data.type || 'message';
        
        if (this.eventListeners.has(eventName)) {
          this.eventListeners.get(eventName).forEach(callback => callback(data));
        }
        
        // 同时触发 all 事件
        if (this.eventListeners.has('all')) {
          this.eventListeners.get('all').forEach(callback => callback(data));
        }
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    this._eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      if (this.eventListeners.has('error')) {
        this.eventListeners.get('error').forEach(callback => callback(error));
      }
    };

    return this._eventSource;
  }

  /**
   * 断开事件连接
   */
  disconnectEvents() {
    if (this._eventSource) {
      this._eventSource.close();
      this._eventSource = null;
    }
  }

  // ==================== 历史记录 ====================

  /**
   * 获取测试历史列表
   * @param {Object} options - 查询选项
   * @param {number} [options.limit=50] - 返回数量限制
   * @param {number} [options.offset=0] - 偏移量
   * @param {string} [options.status] - 状态筛选
   * @param {string} [options.keyword] - 关键词搜索
   * @param {string} [options.modelName] - 模型名称筛选
   * @returns {Promise<Object>}
   */
  async getHistory(options = {}) {
    const params = new URLSearchParams();
    params.append('limit', options.limit || 50);
    params.append('offset', options.offset || 0);
    
    if (options.status) params.append('status', options.status);
    if (options.keyword) params.append('keyword', options.keyword);
    if (options.modelName) params.append('model_name', options.modelName);

    return this._request('GET', `/api/history?${params}`);
  }

  /**
   * 获取测试组详情
   * @param {string} groupId - 测试组 ID
   * @returns {Promise<Object>}
   */
  async getHistoryDetail(groupId) {
    return this._request('GET', `/api/history/${groupId}`);
  }

  /**
   * 获取测试组的所有结果
   * @param {string} groupId - 测试组 ID
   * @param {string} [modelName] - 模型名称筛选
   * @param {string} [testCaseName] - 测试用例名称筛选
   * @returns {Promise<Object>}
   */
  async getHistoryResults(groupId, modelName, testCaseName) {
    const params = new URLSearchParams();
    if (modelName) params.append('model_name', modelName);
    if (testCaseName) params.append('test_case_name', testCaseName);

    const query = params.toString();
    return this._request('GET', `/api/history/${groupId}/results${query ? '?' + query : ''}`);
  }

  /**
   * 获取测试组汇总统计
   * @param {string} groupId - 测试组 ID
   * @returns {Promise<Object>}
   */
  async getHistorySummary(groupId) {
    return this._request('GET', `/api/history/${groupId}/summary`);
  }

  /**
   * 删除测试组
   * @param {string} groupId - 测试组 ID
   * @returns {Promise<Object>}
   */
  async deleteHistory(groupId) {
    return this._request('DELETE', `/api/history/${groupId}`);
  }

  /**
   * 更新测试组信息
   * @param {string} groupId - 测试组 ID
   * @param {Object} options - 更新选项
   * @param {string} [options.name] - 新名称
   * @param {string} [options.status] - 新状态
   * @returns {Promise<Object>}
   */
  async updateHistory(groupId, options = {}) {
    const body = {};
    if (options.name) body.name = options.name;
    if (options.status) body.status = options.status;

    return this._request('PUT', `/api/history/${groupId}`, { body });
  }

  // ==================== Webhook ====================

  /**
   * 配置 Webhook
   * @param {Object} config - Webhook 配置
   * @param {string} config.url - Webhook URL
   * @param {string[]} [config.events] - 触发事件列表
   * @param {boolean} [config.enabled=true] - 是否启用
   * @param {string} [config.secret] - 签名密钥
   * @returns {Promise<Object>}
   */
  async configureWebhook(config) {
    return this._request('POST', '/api/webhook/config', { body: config });
  }

  /**
   * 获取 Webhook 配置
   * @returns {Promise<Object>}
   */
  async getWebhookConfig() {
    return this._request('GET', '/api/webhook/config');
  }

  /**
   * 删除 Webhook 配置
   * @returns {Promise<Object>}
   */
  async deleteWebhookConfig() {
    return this._request('DELETE', '/api/webhook/config');
  }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ModelSpeedTest;
} else if (typeof window !== 'undefined') {
  window.ModelSpeedTest = ModelSpeedTest;
}

export default ModelSpeedTest;