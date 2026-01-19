# Nacos MCP 使用指南

一个基于 FastMCP 的 Model Context Protocol (MCP) 工具，用于读取 Nacos 配置、查看历史版本、对比变更以及检查服务注册状态，兼容 Nacos 2.4.x。

---

## 📋 目录

1. [功能特点](#功能特点)
2. [快速开始](#快速开始)
3. [在 Cursor 中集成](#在-cursor-中集成)
4. [工具功能](#工具功能)
5. [使用示例](#使用示例)
6. [常见问题](#常见问题)

---

## 功能特点

### 核心能力

- 📄 **配置读取**：按 Data ID 获取单个配置或批量读取多个配置
- 🧭 **历史追溯**：列出配置历史、获取详情、自动对比最近两版
- ✅ **服务状态检查**：查看服务实例、健康状态、注册情况
- 🧩 **上下文汇总**：一次性聚合配置、历史与服务状态信息
- 🔐 **鉴权支持**：支持用户名密码登录，自动管理 token
- 🧰 **兼容 Nacos 2.4.x**：对接口版本差异做兜底处理

### 配置灵活性

工具支持多种配置方式，按优先级自动选择：

1. **方法参数**（调用时直接传入）
2. **环境变量**（Cursor MCP 配置或系统环境变量）
3. **默认值**（工具内置）

---

## 快速开始

### 环境准备

#### Python 版本要求

- **Python 3.8 或更高版本**（推荐 Python 3.9+）
- 支持 Windows、Linux、Mac 操作系统

#### 检查 Python 环境

```bash
# 检查 Python 版本
python --version
# 或
py --version
```

#### 检查 pip 是否可用

```bash
# 检查 pip 版本
pip --version
# 或
py -m pip --version
```

### 安装

#### 从 PyPI 安装（默认）

```bash
pip install mcp-nacos-helper
```

#### 使用国内镜像源（可选）

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mcp-nacos-helper
```

---

## 在 Cursor 中集成

示例配置见：`configs/cursor-mcp-config-example.json`

推荐在 `env` 中补充：

- `PYTHONUTF8=1`
- `PYTHONIOENCODING=utf-8`

**PyPI 安装模式示例**：

```json
{
  "mcpServers": {
    "nacos-helper-pypi": {
      "command": "py",
      "args": [
        "-m",
        "mcp_services.nacos.tool"
      ],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "NACOS_SERVER_ADDR": "http://127.0.0.1:8848",
        "NACOS_NAMESPACE": "sae-dev",
        "NACOS_GROUP": "DEFAULT_GROUP",
        "NACOS_USERNAME": "nacos",
        "NACOS_PASSWORD": "nacos",
        "NACOS_TIMEOUT": "5",
        "NACOS_DATA_IDS": "application.yml,bootstrap.yml",
        "NACOS_REGISTRY_NAMESPACE": "sae-registry"
      }
    }
  }
}
```

**说明**：
- `NACOS_NAMESPACE`：配置读取命名空间
- `NACOS_REGISTRY_NAMESPACE`：服务注册查询命名空间（可选）
- `PYTHONUTF8`/`PYTHONIOENCODING`：避免中文乱码

---

## 工具功能

工具提供以下能力（文字说明）：

- **配置读取**：读取单个或多个配置
- **历史追溯**：列出历史、获取详情、对比最近两版
- **服务状态检查**：查看实例与健康状态
- **上下文汇总**：聚合配置、历史、服务状态

---

## 使用示例

示例均为“自然语言调用”，适合在 Cursor 中直接提问：

```
读取 cdc-major-disease-service.yml 的配置
对比 cdc-major-disease-service.yml 最近两版历史
检查 CDC-MAJOR-DISEASE-SERVICE 是否已注册
```

---

## 常见问题

### 1) 历史接口提示需要 nid

工具已自动处理，直接使用“获取最新历史”或“对比最近两版”的能力即可。

### 2) 历史返回 0，但控制台有数据

多为 namespace 参数或接口版本差异导致，请检查：

- `NACOS_NAMESPACE`
- `NACOS_REGISTRY_NAMESPACE`

### 3) 中文输出乱码

在环境变量中添加：

- `PYTHONUTF8=1`
- `PYTHONIOENCODING=utf-8`
