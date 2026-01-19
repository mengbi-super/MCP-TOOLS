#!/usr/bin/env python3
"""
Nacos MCP 服务使用示例
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from mcp_services.nacos.tool import NacosClient


def example_check_service():
    client = NacosClient(server_addr="http://127.0.0.1:8848")
    result = client.check_service_registration("your-service-name")
    print("服务注册状态:")
    print(result)


def example_compare_config():
    client = NacosClient(server_addr="http://127.0.0.1:8848")
    diff = client.compare_config_history(
        data_id="your-data-id",
        group="DEFAULT_GROUP",
        namespace=None,
        nid_a="1",
        nid_b="2",
    )
    print("配置差异:")
    print(diff["diff"])


if __name__ == "__main__":
    example_check_service()
    example_compare_config()
