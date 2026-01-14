# MCP 日志分析工具

一个基于 FastMCP 的 Model Context Protocol (MCP) 工具，用于分析 logback 配置的日志文件，检测代码缺陷并生成修复建议。

## ✨ 功能特性

- 🔍 **智能日志分析**：自动提取异常信息，不限于预定义模式
- 📊 **堆栈跟踪过滤**：保留应用包下的堆栈信息，过滤底层框架信息
- 🎯 **缺陷检测**：自动识别异常类型并推断严重程度
- 🔧 **自动修复建议**：生成代码修复建议
- 🌐 **跨平台支持**：支持 Windows、Linux、Mac
- ⚙️ **灵活配置**：支持环境变量、配置文件、命令行参数多种配置方式
- 🚀 **Token 优化**：智能提取关键信息，减少 token 消耗

## 📦 安装

### 从 PyPI 安装（推荐）

```bash
pip install mcp-logback-analyzer
```

### 从私有 PyPI 安装

```bash
pip install -i http://your-server:8080/simple/ mcp-logback-analyzer
```

### 从源码安装

```bash
git clone https://github.com/yourusername/mcp-logback-analyzer.git
cd mcp-logback-analyzer
pip install -e .
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install mcp-logback-analyzer
```

### 2. 配置 Cursor MCP

编辑 Cursor 的 MCP 配置文件（参考 `cursor-mcp-config-example.json`）：

```json
{
  "mcpServers": {
    "log-analyzer": {
      "command": "python",
      "args": ["-m", "tools.log_analyzer_tool"],
      "cwd": "${workspaceFolder}",
      "env": {
        "LOGBACK_CONFIG_PATH": "${workspaceFolder}/src/resource/logback-spring.xml",
        "SPRING_APPLICATION_NAME": "your-app-name",
        "APP_PACKAGE": "com.example.yourpackage"
      }
    }
  }
}
```

### 3. 使用工具

在 Cursor 中，你可以直接使用以下命令：

- `analyze_logs` - 分析日志文件，检测代码缺陷
- `search_logs` - 在日志中搜索关键词
- `get_logback_config` - 获取 logback 配置信息
- `auto_fix_defect` - 根据缺陷信息生成修复建议

## 📖 文档

详细文档请参考：[完整文档.md](完整文档.md)

## 🔧 配置说明

### 环境变量

- `LOGBACK_CONFIG_PATH` - logback 配置文件路径
- `SPRING_APPLICATION_NAME` - 应用名称
- `APP_PACKAGE` - 应用包名（用于过滤堆栈跟踪）
- `ERROR_LOG_PATH` - 错误日志文件路径
- `WARN_LOG_PATH` - 警告日志文件路径
- `ALL_LOG_PATH` - 全部日志文件路径

### 配置优先级

1. 方法参数
2. 环境变量
3. logback 配置
4. 默认值

## 📝 使用示例

### 分析错误日志

```python
from tools.log_analyzer_tool import LogAnalyzer

analyzer = LogAnalyzer()
result = analyzer.analyze_logs(log_level="error", max_lines=1000)

print(f"发现 {result['total_defects']} 个缺陷")
for defect in result['defects']:
    print(f"类型: {defect['defect_type']}, 严重程度: {defect['severity']}")
```

### 搜索日志

```python
result = analyzer.search_logs(keyword="NullPointerException", log_level="error")
print(f"找到 {result['total_matches']} 个匹配结果")
```

## 🛠️ 开发

### 本地开发

```bash
# 克隆仓库
git clone https://github.com/yourusername/mcp-logback-analyzer.git
cd mcp-logback-analyzer

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

### 构建包

```bash
# 安装构建工具
pip install build twine

# 构建
python -m build
```

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请提交 Issue 或联系：your.email@example.com

---

更多信息请查看 [完整文档.md](完整文档.md)
