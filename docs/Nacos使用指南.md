# Nacos MCP 服务使用指南

本服务基于 Nacos OpenAPI，兼容 Nacos 2.4.x，用于读取配置、对比历史版本、检查服务注册状态。

## 环境变量

- `NACOS_SERVER_ADDR`: Nacos 地址（例如 `http://127.0.0.1:8848`）
- `NACOS_NAMESPACE`: 命名空间 ID（可选）
- `NACOS_GROUP`: 配置/服务分组（默认 `DEFAULT_GROUP`）
- `NACOS_USERNAME`: 用户名（可选）
- `NACOS_PASSWORD`: 密码（可选）
- `NACOS_TIMEOUT`: 请求超时时间（秒，默认 `5`）
- `NACOS_DATA_IDS`: 需要读取的配置列表（逗号分隔）

## MCP 工具列表

- `get_config_tool`：读取配置内容
- `get_configs_tool`：批量读取多个配置
- `get_latest_history_tool`：自动获取最新历史版本（无需 nid）
- `list_config_history_tool`：查询配置历史
- `get_config_history_detail_tool`：获取配置历史详情
- `compare_latest_history_tool`：自动对比最近两版历史（无需 nid）
- `compare_config_history_tool`：对比两个历史版本
- `list_instances_tool`：列出服务实例
- `check_service_registration_tool`：检查服务注册状态
- `collect_service_context_tool`：汇总服务状态与配置（适合关联分析）

## 典型用法

```
检查服务是否正常注册
对比某个配置的两个历史版本
拉取配置并查看最近的变更记录
批量读取指定的 yml 配置
```
