#!/usr/bin/env python3
"""
Nacos 配置与服务状态工具（兼容 Nacos 2.4.x）

基于 Nacos OpenAPI，提供配置读取、历史版本对比、服务注册状态检查等能力。
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from difflib import unified_diff
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_SERVER_ADDR = os.getenv("NACOS_SERVER_ADDR", "http://127.0.0.1:8848")
DEFAULT_NAMESPACE = os.getenv("NACOS_NAMESPACE")
DEFAULT_GROUP = os.getenv("NACOS_GROUP", "DEFAULT_GROUP")
DEFAULT_USERNAME = os.getenv("NACOS_USERNAME")
DEFAULT_PASSWORD = os.getenv("NACOS_PASSWORD")
DEFAULT_TIMEOUT = float(os.getenv("NACOS_TIMEOUT", "5"))
DEFAULT_DATA_IDS = os.getenv("NACOS_DATA_IDS", "")
DEFAULT_REGISTRY_NAMESPACE = os.getenv("NACOS_REGISTRY_NAMESPACE")


def _configure_utf8_stdio() -> None:
    # Ensure Chinese text renders correctly in stdio transports on Windows.
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


try:
    from fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FastMCP = None
    FASTMCP_AVAILABLE = False


@dataclass
class NacosAuth:
    access_token: Optional[str] = None
    token_ttl: Optional[int] = None
    token_create_time: Optional[float] = None

    def is_valid(self) -> bool:
        if not self.access_token or not self.token_ttl or not self.token_create_time:
            return False
        return (time.time() - self.token_create_time) < max(self.token_ttl - 10, 0)


class NacosClient:
    def __init__(
        self,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        namespace: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.server_addr = (server_addr or DEFAULT_SERVER_ADDR).strip()
        if not self.server_addr.startswith("http://") and not self.server_addr.startswith("https://"):
            self.server_addr = f"http://{self.server_addr}"

        self.username = username if username is not None else DEFAULT_USERNAME
        self.password = password if password is not None else DEFAULT_PASSWORD
        self.namespace = namespace if namespace is not None else DEFAULT_NAMESPACE
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        self._auth = NacosAuth()

    def _request_first_available(
        self,
        method: str,
        endpoints: List[str],
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        last_error: Optional[Exception] = None
        for path in endpoints:
            try:
                return self._request(method, path, params=params, data=data), path
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(
            "Nacos 历史接口不可用，已尝试: "
            + ", ".join(endpoints)
            + f"，最后错误: {last_error}"
        )

    @staticmethod
    def _normalize_history_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        data_section = payload.get("data")
        items = (
            payload.get("pageItems")
            or payload.get("items")
            or (data_section.get("pageItems") if isinstance(data_section, dict) else None)
            or (data_section.get("items") if isinstance(data_section, dict) else None)
            or []
        )
        if not isinstance(items, list):
            items = []
        normalized: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            record = dict(item)
            nid_value = record.get("nid") or record.get("id")
            if nid_value is not None and "nid" not in record:
                record["nid"] = nid_value
            normalized.append(record)

        if normalized:
            payload["normalized_items"] = normalized
            if isinstance(data_section, dict) and "normalized_items" not in data_section:
                data_section["normalized_items"] = normalized
            payload["history_items"] = [
                {
                    "nid": str(entry.get("nid") or entry.get("id") or ""),
                    "id": str(entry.get("id") or ""),
                    "md5": entry.get("md5"),
                    "op_type": entry.get("opType") or entry.get("op_type"),
                    "timestamp": entry.get("lastModifiedTime") or entry.get("timestamp"),
                    "src_ip": entry.get("srcIp") or entry.get("src_ip"),
                }
                for entry in normalized
            ]
        return normalized

    def _login(self) -> None:
        if not self.username or not self.password:
            return
        data = {"username": self.username, "password": self.password}
        response = self._raw_request("POST", "/nacos/v1/auth/login", data=data)
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Nacos 登录响应解析失败: {response}") from exc

        token = payload.get("accessToken")
        ttl = payload.get("tokenTtl")
        if not token:
            raise RuntimeError(f"Nacos 登录失败: {payload}")
        self._auth = NacosAuth(
            access_token=token,
            token_ttl=int(ttl) if ttl is not None else None,
            token_create_time=time.time(),
        )

    def _raw_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        url = f"{self.server_addr}{path}"
        if method.upper() == "GET":
            if params:
                url = f"{url}?{urlencode(params)}"
            req = Request(url, method="GET")
            return self._send(req)

        body = urlencode(data or params).encode("utf-8")
        req = Request(url, data=body, method=method.upper())
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        return self._send(req)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self.username and self.password and not self._auth.is_valid():
            self._login()

        params = params.copy() if params else {}
        if self._auth.is_valid():
            params["accessToken"] = self._auth.access_token

        return self._raw_request(method, path, params=params, data=data)

    def _send(self, req: Request) -> str:
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Nacos HTTP {exc.code} {exc.reason}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"Nacos 请求失败: {exc}") from exc

    def _namespace_param(self, namespace: Optional[str]) -> Optional[str]:
        if namespace is None:
            namespace = self.namespace
        return namespace

    def _parse_data_ids(self, data_ids: Optional[List[str]] = None) -> List[str]:
        if data_ids:
            return [item.strip() for item in data_ids if item and item.strip()]
        if not DEFAULT_DATA_IDS:
            return []
        return [item.strip() for item in DEFAULT_DATA_IDS.split(",") if item.strip()]

    def get_config(self, data_id: str, group: Optional[str] = None, namespace: Optional[str] = None) -> Dict[str, Any]:
        group = group or DEFAULT_GROUP
        tenant = self._namespace_param(namespace)
        params = {"dataId": data_id, "group": group}
        if tenant:
            params["tenant"] = tenant
        content = self._request("GET", "/nacos/v1/cs/configs", params=params)
        return {
            "data_id": data_id,
            "group": group,
            "namespace": tenant,
            "content": content,
        }

    def get_configs(
        self,
        data_ids: Optional[List[str]] = None,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        group = group or DEFAULT_GROUP
        tenant = self._namespace_param(namespace)
        resolved_ids = self._parse_data_ids(data_ids)
        results: List[Dict[str, Any]] = []
        for data_id in resolved_ids:
            try:
                results.append(self.get_config(data_id, group, tenant))
            except Exception as exc:
                results.append(
                    {
                        "data_id": data_id,
                        "group": group,
                        "namespace": tenant,
                        "error": str(exc),
                    }
                )
        return {
            "group": group,
            "namespace": tenant,
            "data_ids": resolved_ids,
            "configs": results,
        }

    def list_config_history(
        self,
        data_id: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        page_no: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        group = group or DEFAULT_GROUP
        tenant = self._namespace_param(namespace)
        base_params = {
            "dataId": data_id,
            "group": group,
            "pageNo": page_no,
            "pageSize": page_size,
        }
        attempts: List[Dict[str, Any]] = []
        variants: List[Tuple[str, Dict[str, Any]]] = []
        for endpoint in [
            "/nacos/v1/cs/history/list",
            "/nacos/v1/cs/history",
            "/nacos/v2/cs/history/list",
            "/nacos/v2/cs/history",
        ]:
            params = dict(base_params)
            if tenant:
                if "/v2/" in endpoint:
                    params["namespaceId"] = tenant
                else:
                    params["tenant"] = tenant
            variants.append((endpoint, params))
            if tenant:
                # Try the alternate namespace key as fallback.
                alt_params = dict(base_params)
                alt_params["namespaceId" if "tenant" in params else "tenant"] = tenant
                variants.append((endpoint, alt_params))

        last_payload: Dict[str, Any] = {}
        for endpoint, params in variants:
            try:
                response = self._request("GET", endpoint, params=params)
                payload = json.loads(response)
            except Exception as exc:
                attempts.append({"endpoint": endpoint, "params": params, "error": str(exc)})
                continue

            if isinstance(payload, dict):
                payload["history_endpoint"] = endpoint
                payload["history_params"] = params
                self._normalize_history_payload(payload)

                data_section = payload.get("data")
                page_items = payload.get("normalized_items") or payload.get("pageItems") or payload.get("items")
                if not page_items and isinstance(data_section, dict):
                    page_items = (
                        data_section.get("normalized_items")
                        or data_section.get("pageItems")
                        or data_section.get("items")
                    )

                total = None
                if isinstance(data_section, dict):
                    total = data_section.get("totalCount") or data_section.get("total")
                if total is None:
                    total = payload.get("totalCount") or payload.get("total")

                if page_items or (isinstance(total, int) and total > 0):
                    payload["history_attempts"] = attempts
                    return payload

            last_payload = payload if isinstance(payload, dict) else {"raw": payload}
            attempts.append({"endpoint": endpoint, "params": params, "result": "empty"})

        if isinstance(last_payload, dict):
            last_payload["history_attempts"] = attempts
        return last_payload

    def get_config_history_detail(
        self,
        data_id: str,
        group: Optional[str],
        namespace: Optional[str],
        nid: str,
    ) -> Dict[str, Any]:
        group = group or DEFAULT_GROUP
        tenant = self._namespace_param(namespace)
        params = {"dataId": data_id, "group": group, "nid": nid}
        if tenant:
            params["tenant"] = tenant
        response, endpoint = self._request_first_available(
            "GET",
            [
                "/nacos/v1/cs/history",
                "/nacos/v2/cs/history",
            ],
            params=params,
        )
        payload = json.loads(response)
        if isinstance(payload, dict):
            payload["history_endpoint"] = endpoint
        return payload

    def compare_config_history(
        self,
        data_id: str,
        group: Optional[str],
        namespace: Optional[str],
        nid_a: str,
        nid_b: str,
    ) -> Dict[str, Any]:
        detail_a = self.get_config_history_detail(data_id, group, namespace, nid_a)
        detail_b = self.get_config_history_detail(data_id, group, namespace, nid_b)
        content_a = (detail_a.get("content") or "").splitlines()
        content_b = (detail_b.get("content") or "").splitlines()
        diff = "\n".join(
            unified_diff(content_a, content_b, fromfile=f"nid:{nid_a}", tofile=f"nid:{nid_b}")
        )
        return {
            "data_id": data_id,
            "group": group or DEFAULT_GROUP,
            "namespace": self._namespace_param(namespace),
            "nid_a": nid_a,
            "nid_b": nid_b,
            "diff": diff,
        }

    def get_latest_history(
        self,
        data_id: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        history = self.list_config_history(
            data_id=data_id,
            group=group,
            namespace=namespace,
            page_no=1,
            page_size=page_size,
        )
        items = history.get("normalized_items") or history.get("pageItems") or history.get("items") or []
        if not items and isinstance(history.get("data"), dict):
            data_section = history.get("data")
            items = data_section.get("normalized_items") or data_section.get("pageItems") or data_section.get("items") or []
        latest = items[0] if items else None
        latest_nid = (
            str(latest.get("nid") or latest.get("id") or "") if isinstance(latest, dict) else ""
        )
        return {
            "data_id": data_id,
            "group": group or DEFAULT_GROUP,
            "namespace": self._namespace_param(namespace),
            "history": history,
            "latest": latest,
            "latest_nid": latest_nid,
        }

    def compare_latest_history(
        self,
        data_id: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        history = self.list_config_history(
            data_id=data_id,
            group=group,
            namespace=namespace,
            page_no=1,
            page_size=page_size,
        )
        items = history.get("normalized_items") or history.get("pageItems") or history.get("items") or []
        if not items and isinstance(history.get("data"), dict):
            data_section = history.get("data")
            items = data_section.get("normalized_items") or data_section.get("pageItems") or data_section.get("items") or []
        if len(items) < 2:
            return {
                "data_id": data_id,
                "group": group or DEFAULT_GROUP,
                "namespace": self._namespace_param(namespace),
                "error": "历史版本数量不足，无法自动对比",
                "history": history,
            }
        nid_a = str(items[0].get("nid") or items[0].get("id") or "")
        nid_b = str(items[1].get("nid") or items[1].get("id") or "")
        if not nid_a or not nid_b:
            return {
                "data_id": data_id,
                "group": group or DEFAULT_GROUP,
                "namespace": self._namespace_param(namespace),
                "error": "历史记录缺少 nid/id，无法自动对比",
                "history": history,
            }
        diff = self.compare_config_history(data_id, group, namespace, nid_a, nid_b)
        diff["history"] = history
        return diff

    def list_instances(
        self,
        service_name: str,
        group_name: Optional[str] = None,
        namespace: Optional[str] = None,
        registry_namespace: Optional[str] = None,
        healthy_only: bool = False,
    ) -> Dict[str, Any]:
        group_name = group_name or DEFAULT_GROUP
        namespace_id = self._namespace_param(registry_namespace or namespace)
        params = {
            "serviceName": service_name,
            "groupName": group_name,
        }
        if namespace_id:
            params["namespaceId"] = namespace_id
        response = self._request("GET", "/nacos/v1/ns/instance/list", params=params)
        payload = json.loads(response)
        if healthy_only:
            hosts = payload.get("hosts", [])
            payload["hosts"] = [host for host in hosts if host.get("healthy") is True]
        return payload

    def check_service_registration(
        self,
        service_name: str,
        group_name: Optional[str] = None,
        namespace: Optional[str] = None,
        registry_namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = self.list_instances(service_name, group_name, namespace, registry_namespace)
        hosts = payload.get("hosts", [])
        total = len(hosts)
        healthy = len([h for h in hosts if h.get("healthy") is True])
        return {
            "service_name": service_name,
            "group": group_name or DEFAULT_GROUP,
            "namespace": self._namespace_param(registry_namespace or namespace),
            "total_instances": total,
            "healthy_instances": healthy,
            "unhealthy_instances": total - healthy,
            "instances": hosts,
        }

    def collect_service_context(
        self,
        service_name: str,
        data_id: Optional[str] = None,
        data_ids: Optional[List[str]] = None,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        registry_namespace: Optional[str] = None,
        include_history: bool = False,
        history_page_size: int = 10,
        healthy_only: bool = False,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "service": self.check_service_registration(
                service_name, group, namespace, registry_namespace
            ),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        }
        if data_id:
            context["config"] = self.get_config(data_id, group, namespace)
            if include_history:
                context["config_history"] = self.list_config_history(
                    data_id=data_id,
                    group=group,
                    namespace=namespace,
                    page_size=history_page_size,
                )
        if data_ids:
            context["configs"] = self.get_configs(data_ids, group, namespace)
        if healthy_only:
            context["service"]["instances"] = [
                host for host in context["service"]["instances"] if host.get("healthy") is True
            ]
        return context


def get_config(
    data_id: str,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        return NacosClient(server_addr, username, password, namespace).get_config(data_id, group, namespace)
    except Exception as exc:
        return {"error": str(exc), "data_id": data_id, "group": group, "namespace": namespace}


def get_configs(
    data_ids: Optional[List[str]] = None,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        return NacosClient(server_addr, username, password, namespace).get_configs(data_ids, group, namespace)
    except Exception as exc:
        return {"error": str(exc), "data_ids": data_ids, "group": group, "namespace": namespace}


def list_config_history(
    data_id: str,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    page_no: int = 1,
    page_size: int = 20,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        return NacosClient(server_addr, username, password, namespace).list_config_history(
            data_id, group, namespace, page_no, page_size
        )
    except Exception as exc:
        return {"error": str(exc), "data_id": data_id, "group": group, "namespace": namespace}


def get_latest_history(
    data_id: str,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    page_size: int = 10,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        return NacosClient(server_addr, username, password, namespace).get_latest_history(
            data_id, group, namespace, page_size
        )
    except Exception as exc:
        return {"error": str(exc), "data_id": data_id, "group": group, "namespace": namespace}


def get_config_history_detail(
    data_id: str,
    nid: str,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        return NacosClient(server_addr, username, password, namespace).get_config_history_detail(
            data_id, group, namespace, nid
        )
    except Exception as exc:
        return {
            "error": str(exc),
            "data_id": data_id,
            "group": group,
            "namespace": namespace,
            "nid": nid,
        }


def compare_config_history(
    data_id: str,
    nid_a: str,
    nid_b: str,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        return NacosClient(server_addr, username, password, namespace).compare_config_history(
            data_id, group, namespace, nid_a, nid_b
        )
    except Exception as exc:
        return {
            "error": str(exc),
            "data_id": data_id,
            "group": group,
            "namespace": namespace,
            "nid_a": nid_a,
            "nid_b": nid_b,
        }


def compare_latest_history(
    data_id: str,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    page_size: int = 10,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        return NacosClient(server_addr, username, password, namespace).compare_latest_history(
            data_id, group, namespace, page_size
        )
    except Exception as exc:
        return {"error": str(exc), "data_id": data_id, "group": group, "namespace": namespace}


def list_instances(
    service_name: str,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    registry_namespace: Optional[str] = None,
    healthy_only: bool = False,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        registry_namespace = registry_namespace if registry_namespace is not None else DEFAULT_REGISTRY_NAMESPACE
        return NacosClient(server_addr, username, password, namespace).list_instances(
            service_name, group, namespace, registry_namespace, healthy_only
        )
    except Exception as exc:
        return {"error": str(exc), "service_name": service_name, "group": group, "namespace": namespace}


def check_service_registration(
    service_name: str,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    registry_namespace: Optional[str] = None,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        registry_namespace = registry_namespace if registry_namespace is not None else DEFAULT_REGISTRY_NAMESPACE
        return NacosClient(server_addr, username, password, namespace).check_service_registration(
            service_name, group, namespace, registry_namespace
        )
    except Exception as exc:
        return {"error": str(exc), "service_name": service_name, "group": group, "namespace": namespace}


def collect_service_context(
    service_name: str,
    data_id: Optional[str] = None,
    data_ids: Optional[List[str]] = None,
    group: Optional[str] = None,
    namespace: Optional[str] = None,
    registry_namespace: Optional[str] = None,
    include_history: bool = False,
    history_page_size: int = 10,
    healthy_only: bool = False,
    server_addr: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        registry_namespace = registry_namespace if registry_namespace is not None else DEFAULT_REGISTRY_NAMESPACE
        return NacosClient(server_addr, username, password, namespace).collect_service_context(
            service_name=service_name,
            data_id=data_id,
            data_ids=data_ids,
            group=group,
            namespace=namespace,
            registry_namespace=registry_namespace,
            include_history=include_history,
            history_page_size=history_page_size,
            healthy_only=healthy_only,
        )
    except Exception as exc:
        return {"error": str(exc), "service_name": service_name, "group": group, "namespace": namespace}


if FASTMCP_AVAILABLE:
    _configure_utf8_stdio()
    mcp = FastMCP("Nacos 配置与服务状态工具")

    @mcp.tool()
    def get_config_tool(
        data_id: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return get_config(data_id, group, namespace, server_addr, username, password)

    @mcp.tool()
    def get_configs_tool(
        data_ids: Optional[List[str]] = None,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return get_configs(data_ids, group, namespace, server_addr, username, password)

    @mcp.tool()
    def list_config_history_tool(
        data_id: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        page_no: int = 1,
        page_size: int = 20,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return list_config_history(data_id, group, namespace, page_no, page_size, server_addr, username, password)

    @mcp.tool()
    def get_latest_history_tool(
        data_id: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        page_size: int = 10,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return get_latest_history(data_id, group, namespace, page_size, server_addr, username, password)

    @mcp.tool()
    def get_config_history_detail_tool(
        data_id: str,
        nid: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return get_config_history_detail(data_id, nid, group, namespace, server_addr, username, password)

    @mcp.tool()
    def compare_latest_history_tool(
        data_id: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        page_size: int = 10,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return compare_latest_history(data_id, group, namespace, page_size, server_addr, username, password)

    @mcp.tool()
    def compare_config_history_tool(
        data_id: str,
        nid_a: str,
        nid_b: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return compare_config_history(data_id, nid_a, nid_b, group, namespace, server_addr, username, password)

    @mcp.tool()
    def list_instances_tool(
        service_name: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        registry_namespace: Optional[str] = None,
        healthy_only: bool = False,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return list_instances(
            service_name, group, namespace, registry_namespace, healthy_only, server_addr, username, password
        )

    @mcp.tool()
    def check_service_registration_tool(
        service_name: str,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        registry_namespace: Optional[str] = None,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return check_service_registration(
            service_name, group, namespace, registry_namespace, server_addr, username, password
        )

    @mcp.tool()
    def collect_service_context_tool(
        service_name: str,
        data_id: Optional[str] = None,
        data_ids: Optional[List[str]] = None,
        group: Optional[str] = None,
        namespace: Optional[str] = None,
        registry_namespace: Optional[str] = None,
        include_history: bool = False,
        history_page_size: int = 10,
        healthy_only: bool = False,
        server_addr: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        return collect_service_context(
            service_name=service_name,
            data_id=data_id,
            data_ids=data_ids,
            group=group,
            namespace=namespace,
            registry_namespace=registry_namespace,
            include_history=include_history,
            history_page_size=history_page_size,
            healthy_only=healthy_only,
            server_addr=server_addr,
            username=username,
            password=password,
        )


def main() -> None:
    if FastMCP is None:
        print("错误: 未安装 fastmcp 库")
        print("请运行: pip install fastmcp")
        return

    try:
        _configure_utf8_stdio()
        mcp.run()
    except Exception as exc:
        print(f"运行 FastMCP 服务器时出错: {exc}")


if __name__ == "__main__":
    main()
