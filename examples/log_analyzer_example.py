#!/usr/bin/env python3
"""
日志分析工具使用示例

演示如何使用 LogAnalyzer 工具分析日志并检测代码缺陷。
"""

import sys
from pathlib import Path

# 添加 src 目录到路径
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from mcp_services.log_analyzer.tool import LogAnalyzer

DEFAULT_LOGBACK_CONFIG = str(
    ROOT_DIR
    / "src"
    / "mcp_services"
    / "log_analyzer"
    / "resources"
    / "logback-spring.xml"
)


def example_analyze_logs():
    """示例：分析错误日志"""
    print("=" * 60)
    print("示例 1: 分析错误日志")
    print("=" * 60)
    
    analyzer = LogAnalyzer(DEFAULT_LOGBACK_CONFIG)
    
    # 分析错误日志
    result = analyzer.analyze_logs(log_level="error", max_lines=500)
    
    print(f"\n总共发现 {result['total_defects']} 个潜在缺陷")
    print(f"分析的日志文件: {result['log_files_analyzed']}")
    print(f"分析时间: {result['analysis_time']}")
    
    # 显示前 5 个缺陷
    print("\n前 5 个缺陷详情:")
    for i, defect in enumerate(result['defects'][:5], 1):
        print(f"\n缺陷 {i}:")
        print(f"  类型: {defect['defect_type']}")
        print(f"  严重程度: {defect['severity']}")
        print(f"  修复建议: {defect['suggestion']}")
        print(f"  日志行: {defect['log_line'][:80]}...")


def example_get_config():
    """示例：获取 logback 配置"""
    print("\n" + "=" * 60)
    print("示例 2: 获取 Logback 配置")
    print("=" * 60)
    
    analyzer = LogAnalyzer(DEFAULT_LOGBACK_CONFIG)
    
    print("\nLogback 配置信息:")
    print(f"  应用名称: {analyzer.app_name}")
    print(f"  日志路径: {analyzer.log_path}")
    print(f"  完整配置: {analyzer.config}")


def example_auto_fix():
    """示例：自动修复建议"""
    print("\n" + "=" * 60)
    print("示例 3: 生成自动修复建议")
    print("=" * 60)
    
    analyzer = LogAnalyzer()
    
    # 模拟一个缺陷
    defect_info = {
        "defect_type": "空指针异常",
        "pattern": r"NullPointerException",
        "log_line": "java.lang.NullPointerException: null",
        "severity": "high"
    }
    
    fix_result = analyzer.auto_fix_code(defect_info)
    
    print(f"\n缺陷类型: {fix_result['defect']['defect_type']}")
    print(f"修复状态: {fix_result['status']}")
    
    if fix_result['fixes']:
        print("\n修复建议:")
        for fix in fix_result['fixes']:
            print(f"  描述: {fix['description']}")
            print(f"  修复前: {fix['before']}")
            print(f"  修复后: {fix['after']}")


def example_search_logs():
    """示例：搜索日志"""
    print("\n" + "=" * 60)
    print("示例 4: 搜索日志关键词")
    print("=" * 60)
    
    analyzer = LogAnalyzer(DEFAULT_LOGBACK_CONFIG)
    
    # 搜索关键词
    keyword = "Exception"
    log_files = [
        f"{analyzer.log_path}/{analyzer.app_name}/log_error.log",
        f"{analyzer.log_path}/{analyzer.app_name}/all.log"
    ]
    
    matches = []
    for log_file in log_files:
        lines = analyzer._read_log_file(log_file, max_lines=100)
        for line_num, line in enumerate(lines, 1):
            if keyword.lower() in line.lower():
                matches.append({
                    "file": log_file,
                    "line_number": line_num,
                    "content": line.strip()
                })
    
    print(f"\n搜索关键词: '{keyword}'")
    print(f"找到 {len(matches)} 个匹配结果")
    
    if matches:
        print("\n前 3 个匹配结果:")
        for match in matches[:3]:
            print(f"  文件: {match['file']}")
            print(f"  行号: {match['line_number']}")
            print(f"  内容: {match['content'][:80]}...")


if __name__ == "__main__":
    print("日志分析工具使用示例\n")
    
    try:
        example_get_config()
        example_analyze_logs()
        example_auto_fix()
        example_search_logs()
    except Exception as e:
        print(f"\n错误: {e}")
        print("提示: 请确保 logback-spring.xml 文件存在，并且日志文件路径正确")
