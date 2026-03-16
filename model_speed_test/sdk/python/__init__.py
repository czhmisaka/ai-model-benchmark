"""
Model Speed Test Python SDK
AI模型速度测试框架的 Python SDK
"""
import requests
from typing import Optional, List, Dict, Any
import sseclient
import json


class ModelSpeedTest:
    """AI模型速度测试 Python SDK"""
    
    def __init__(self, base_url: str = "http://localhost:15010", api_key: Optional[str] = None):
        """
        初始化 SDK 客户端
        
        Args:
            base_url: API 基础 URL
            api_key: API Key (可选)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {}
        if api_key:
            self._headers["X-API-Key"] = api_key
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {**self._headers, **kwargs.pop("headers", {})}
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()
    
    # ==================== 配置管理 ====================
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._request("GET", "/config")
    
    def add_model(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加模型
        
        Args:
            model_data: 模型数据，包含 name, endpoint, api_key, model 等字段
            
        Returns:
            添加结果
        """
        return self._request("POST", "/config/models", json=model_data)
    
    def update_model(self, model_name: str, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新模型
        
        Args:
            model_name: 模型名称
            model_data: 要更新的字段
            
        Returns:
            更新结果
        """
        return self._request("PUT", f"/config/models/{model_name}", json=model_data)
    
    def delete_model(self, model_name: str) -> Dict[str, Any]:
        """
        删除模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            删除结果
        """
        return self._request("DELETE", f"/config/models/{model_name}")
    
    def add_test_case(self, test_case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加测试用例
        
        Args:
            test_case_data: 测试用例数据
            
        Returns:
            添加结果
        """
        return self._request("POST", "/config/test-cases", json=test_case_data)
    
    def update_test_case(self, test_case_id: str, test_case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新测试用例
        
        Args:
            test_case_id: 测试用例 ID
            test_case_data: 要更新的字段
            
        Returns:
            更新结果
        """
        return self._request("PUT", f"/config/test-cases/{test_case_id}", json=test_case_data)
    
    def delete_test_case(self, test_case_id: str) -> Dict[str, Any]:
        """
        删除测试用例
        
        Args:
            test_case_id: 测试用例 ID
            
        Returns:
            删除结果
        """
        return self._request("DELETE", f"/config/test-cases/{test_case_id}")
    
    # ==================== 测试控制 ====================
    
    def start_test(
        self,
        models: Optional[List[str]] = None,
        cases: Optional[List[str]] = None,
        test_rounds: Optional[int] = None,
        max_concurrent: Optional[int] = None,
        interval: Optional[float] = None,
        test_name: Optional[str] = None,
        concurrent: bool = True
    ) -> Dict[str, Any]:
        """
        启动测试
        
        Args:
            models: 要测试的模型名称列表
            cases: 要测试的用例 ID 列表
            test_rounds: 测试轮数
            max_concurrent: 最大并发数
            interval: 请求间隔(秒)
            test_name: 测试名称
            concurrent: 是否启用并发
            
        Returns:
            启动结果
        """
        body = {
            "models": models or [],
            "cases": cases or [],
            "concurrent": concurrent
        }
        
        if test_rounds is not None:
            body["test_rounds"] = test_rounds
        if max_concurrent is not None:
            body["max_concurrent"] = max_concurrent
        if interval is not None:
            body["interval"] = interval
        if test_name is not None:
            body["test_name"] = test_name
        
        return self._request("POST", "/test/start", json=body)
    
    def stop_test(self) -> Dict[str, Any]:
        """停止测试"""
        return self._request("POST", "/test/stop")
    
    def get_status(self) -> Dict[str, Any]:
        """获取测试状态"""
        return self._request("GET", "/test/status")
    
    def reset(self) -> Dict[str, Any]:
        """重置测试状态"""
        return self._request("POST", "/reset")
    
    # ==================== 事件流 ====================
    
    def events(self):
        """
        获取 SSE 事件流
        
        Yields:
            事件数据
        """
        url = f"{self.base_url}/events"
        response = requests.get(url, headers=self._headers, stream=True)
        response.raise_for_status()
        
        client = sseclient.SSEClient(response)
        for event in client.events():
            if event.data:
                yield json.loads(event.data)
    
    # ==================== 历史记录 ====================
    
    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取测试历史列表
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            status: 状态筛选
            keyword: 关键词搜索
            model_name: 模型名称筛选
            
        Returns:
            历史记录列表
        """
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if keyword:
            params["keyword"] = keyword
        if model_name:
            params["model_name"] = model_name
        
        return self._request("GET", "/api/history", params=params)
    
    def get_history_detail(self, group_id: str) -> Dict[str, Any]:
        """
        获取测试组详情
        
        Args:
            group_id: 测试组 ID
            
        Returns:
            测试组详情
        """
        return self._request("GET", f"/api/history/{group_id}")
    
    def get_history_results(
        self,
        group_id: str,
        model_name: Optional[str] = None,
        test_case_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取测试组的所有结果
        
        Args:
            group_id: 测试组 ID
            model_name: 模型名称筛选
            test_case_name: 测试用例名称筛选
            
        Returns:
            测试结果列表
        """
        params = {}
        if model_name:
            params["model_name"] = model_name
        if test_case_name:
            params["test_case_name"] = test_case_name
        
        return self._request("GET", f"/api/history/{group_id}/results", params=params)
    
    def get_history_summary(self, group_id: str) -> Dict[str, Any]:
        """
        获取测试组汇总统计
        
        Args:
            group_id: 测试组 ID
            
        Returns:
            汇总统计
        """
        return self._request("GET", f"/api/history/{group_id}/summary")
    
    def delete_history(self, group_id: str) -> Dict[str, Any]:
        """
        删除测试组
        
        Args:
            group_id: 测试组 ID
            
        Returns:
            删除结果
        """
        return self._request("DELETE", f"/api/history/{group_id}")
    
    def update_history(self, group_id: str, name: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """
        更新测试组信息
        
        Args:
            group_id: 测试组 ID
            name: 新名称
            status: 新状态
            
        Returns:
            更新结果
        """
        body = {}
        if name:
            body["name"] = name
        if status:
            body["status"] = status
        
        return self._request("PUT", f"/api/history/{group_id}", json=body)
    
    # ==================== Webhook ====================
    
    def configure_webhook(
        self,
        url: str,
        events: Optional[List[str]] = None,
        enabled: bool = True,
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        配置 Webhook
        
        Args:
            url: Webhook URL
            events: 触发事件列表
            enabled: 是否启用
            secret: 签名密钥
            
        Returns:
            配置结果
        """
        config = {
            "url": url,
            "events": events or ["test_complete"],
            "enabled": enabled
        }
        if secret:
            config["secret"] = secret
        
        return self._request("POST", "/api/webhook/config", json=config)
    
    def get_webhook_config(self) -> Dict[str, Any]:
        """获取 Webhook 配置"""
        return self._request("GET", "/api/webhook/config")
    
    def delete_webhook_config(self) -> Dict[str, Any]:
        """删除 Webhook 配置"""
        return self._request("DELETE", "/api/webhook/config")


# 便捷函数
def create_client(base_url: str = "http://localhost:15010", api_key: Optional[str] = None) -> ModelSpeedTest:
    """创建 SDK 客户端的便捷函数"""
    return ModelSpeedTest(base_url=base_url, api_key=api_key)