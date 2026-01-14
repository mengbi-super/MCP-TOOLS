"""
MCP 日志分析工具 - 打包配置
"""
from setuptools import setup, find_packages

setup(
    name="mcp-logback-analyzer",
    version="1.0.2",
    description="日志检索和分析工具 - 基于 FastMCP 的 MCP 工具",
    long_description=open("使用指南.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="mengbi",
    author_email="mengbi1014@gmail.com",
    url="https://github.com/mengbi-super/MCP-TOOLS",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "resource": ["*.xml"],
    },
    install_requires=[
        "fastmcp>=0.9.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "mcp-log-analyzer=tools.log_analyzer_tool:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
