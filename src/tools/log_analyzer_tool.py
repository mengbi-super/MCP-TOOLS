#!/usr/bin/env python3
"""
日志检索和分析工具（兼容入口）
"""

from mcp_services.log_analyzer.tool import (  # noqa: F401
    LogAnalyzer,
    analyze_logs,
    get_logback_config,
    auto_fix_defect,
    search_logs,
    main,
)

__all__ = [
    "LogAnalyzer",
    "analyze_logs",
    "get_logback_config",
    "auto_fix_defect",
    "search_logs",
    "main",
]


if __name__ == "__main__":
    main()
