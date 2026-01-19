# MCP 工具集合

基于 FastMCP 的 Model Context Protocol (MCP) 工具集合，提供日志分析与 Nacos 配置/服务状态检查能力。

## ✨ MCP 服务

- log-analyzer
- nacos-helper

## 📦 安装

### 从 PyPI 安装（推荐）

```bash
pip install mcp-logback-analyzer
pip install mcp-nacos-helper
```

### 使用国内镜像源（国内用户推荐）

如果无法访问 PyPI 或下载速度慢，可以使用国内镜像源：

```bash
# 清华大学镜像（推荐）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mcp-logback-analyzer
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple mcp-nacos-helper

# 阿里云镜像
pip install -i https://mirrors.aliyun.com/pypi/simple/ mcp-logback-analyzer
pip install -i https://mirrors.aliyun.com/pypi/simple/ mcp-nacos-helper

# 腾讯云镜像
pip install -i https://mirrors.cloud.tencent.com/pypi/simple mcp-logback-analyzer
pip install -i https://mirrors.cloud.tencent.com/pypi/simple mcp-nacos-helper
```

### 从私有 PyPI 安装

```bash
pip install -i http://your-server:8080/simple/ mcp-logback-analyzer
pip install -i http://your-server:8080/simple/ mcp-nacos-helper
```

### 从源码安装

```bash
git clone https://github.com/mengbi-super/MCP-TOOLS.git
cd MCP-TOOLS
pip install -r requirements.txt
```

## 🚀 快速开始

安装后请分别参考各组件的使用说明与配置示例。

## 📖 文档

详细文档请参考：

- [packages/log_analyzer/README.md](packages/log_analyzer/README.md)
- [packages/nacos_helper/README.md](packages/nacos_helper/README.md)

## 🛠️ 开发

### 本地开发

```bash
# 克隆仓库
git clone https://github.com/mengbi-super/MCP-TOOLS.git
cd MCP-TOOLS

# 安装开发依赖
pip install -e "packages/log_analyzer[dev]"
pip install -e "packages/nacos_helper[dev]"

# 运行测试
pytest
```

### 构建包

```bash
# 安装构建工具
pip install build twine

# 构建
cd packages/log_analyzer
python -m build

cd ../nacos_helper
python -m build
```

### 发布到 PyPI

```bash
# 在仓库根目录执行
py scripts/upload_to_pypi.py packages/log_analyzer
py scripts/upload_to_pypi.py packages/nacos_helper
```

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请提交 Issue 或联系：[mengbi1014@gmail.com](mailto:mengbi1014@gmail.com)

---

更多信息请查看 [packages/log_analyzer/README.md](packages/log_analyzer/README.md)
