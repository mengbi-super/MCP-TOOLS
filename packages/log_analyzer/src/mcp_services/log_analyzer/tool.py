#!/usr/bin/env python3
"""
日志检索和分析工具

使用 fastmcp 创建，能够分析 logback-spring.xml 配置的日志文件，
检测代码缺陷并自动修复。
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# 从环境变量读取默认配置路径
DEFAULT_LOGBACK_CONFIG = os.getenv(
    "LOGBACK_CONFIG_PATH",
    str(Path(__file__).resolve().parent / "resources" / "logback-spring.xml"),
)

# 从环境变量读取日志文件路径
DEFAULT_ERROR_LOG_PATH = os.getenv("ERROR_LOG_PATH", None)
DEFAULT_WARN_LOG_PATH = os.getenv("WARN_LOG_PATH", None)
DEFAULT_ALL_LOG_PATH = os.getenv("ALL_LOG_PATH", None)

# 从环境变量读取应用包名（用于过滤堆栈跟踪）
DEFAULT_APP_PACKAGE = os.getenv("APP_PACKAGE", None)

try:
    from fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    # 如果 fastmcp 不可用，使用基础实现
    FastMCP = None
    FASTMCP_AVAILABLE = False


class LogAnalyzer:
    """日志分析器"""
    
    def __init__(
        self,
        logback_config_path: Optional[str] = None,
        error_log_path: Optional[str] = None,
        warn_log_path: Optional[str] = None,
        all_log_path: Optional[str] = None
    ):
        """
        初始化日志分析器
        
        Args:
            logback_config_path: logback 配置文件路径
                - 如果为 None，优先使用环境变量 LOGBACK_CONFIG_PATH
                - 如果环境变量不存在，使用默认路径 "mcp_services/log_analyzer/resources/logback-spring.xml"
            error_log_path: 错误日志文件路径（可选）
                - 如果为 None，优先使用环境变量 ERROR_LOG_PATH
                - 如果环境变量不存在，从 logback 配置中读取
            warn_log_path: 警告日志文件路径（可选）
                - 如果为 None，优先使用环境变量 WARN_LOG_PATH
                - 如果环境变量不存在，从 logback 配置中读取
            all_log_path: 全部日志文件路径（可选）
                - 如果为 None，优先使用环境变量 ALL_LOG_PATH
                - 如果环境变量不存在，从 logback 配置中读取
        """
        if logback_config_path is None:
            logback_config_path = DEFAULT_LOGBACK_CONFIG
        self.logback_config_path = logback_config_path
        self.config = self._parse_logback_config()
        
        # 获取配置中的日志路径
        config_log_path = self.config.get("log_path")
        
        # 如果配置中有路径，在 Windows 上需要转换 Linux 路径格式
        if config_log_path:
            self.log_path = self._convert_path_for_platform(config_log_path)
        else:
            # 默认日志路径：Windows 使用磁盘根目录下的 /data/logs，Linux 使用 /data/logs
            default_log_path = self._get_default_log_path_for_platform()
            self.log_path = default_log_path
        
        # 获取应用名称，优先从配置中读取，如果配置中没有则尝试从环境变量或项目路径推断
        app_name = self.config.get("app_name")
        if not app_name:
            # 尝试从环境变量获取
            app_name = os.getenv("SPRING_APPLICATION_NAME") or os.getenv("APP_NAME")
            if not app_name:
                # 尝试从当前工作目录推断（取目录名）
                try:
                    current_dir = os.getcwd()
                    # 获取最后一级目录名作为应用名称
                    app_name = os.path.basename(os.path.normpath(current_dir))
                    # 如果目录名是常见的项目根目录名，尝试获取上一级
                    if app_name in ["src", "target", "build", "dist", "bin"]:
                        parent_dir = os.path.dirname(os.path.normpath(current_dir))
                        app_name = os.path.basename(parent_dir) if parent_dir else "unknown-app"
                except Exception:
                    app_name = "unknown-app"
        
        self.app_name = app_name or "unknown-app"
        
        # 获取应用包名（用于过滤堆栈跟踪，只保留应用包下的堆栈信息）
        # 优先级：环境变量 > 从应用名称推断 > None
        app_package = DEFAULT_APP_PACKAGE
        if not app_package:
            # 尝试从应用名称推断包名（常见模式：应用名 -> 包名）
            # 例如：cdc-major-disease-service -> com.cdc.major.disease.service 或 cdc.major.disease.service
            if app_name and app_name != "unknown-app":
                # 将应用名称转换为可能的包名格式
                # 移除常见后缀（-service, -api 等）
                name_without_suffix = re.sub(r'[-_](service|api|app|web|core)$', '', app_name, flags=re.IGNORECASE)
                # 将连字符或下划线替换为点，转换为包名格式
                potential_package = name_without_suffix.replace('-', '.').replace('_', '.')
                # 如果看起来像包名（包含点），则使用
                if '.' in potential_package:
                    app_package = potential_package
        self.app_package = app_package
        
        # 存储外部配置的日志文件路径（优先级：参数 > 环境变量 > None）
        self.error_log_path = error_log_path or DEFAULT_ERROR_LOG_PATH
        self.warn_log_path = warn_log_path or DEFAULT_WARN_LOG_PATH
        self.all_log_path = all_log_path or DEFAULT_ALL_LOG_PATH
    
    def _get_default_log_path_for_platform(self) -> str:
        """
        获取平台默认日志路径
        
        Returns:
            默认日志路径
        """
        if os.name == 'nt':  # Windows
            # 获取当前工作目录的磁盘盘符
            current_dir = os.getcwd()
            drive = os.path.splitdrive(current_dir)[0]  # 例如：D:
            # 使用 os.path.join 确保路径格式正确
            # 注意：drive 需要以反斜杠结尾，或使用 os.sep
            # 转换为 D:\data\logs
            return os.path.join(drive + os.sep, "data", "logs")
        else:  # Linux/Mac
            return "/data/logs"
    
    def _convert_path_for_platform(self, path: str) -> str:
        """
        将路径转换为当前平台格式
        
        Args:
            path: 原始路径（可能是 Linux 格式）
        
        Returns:
            转换后的路径
        """
        if not path:
            return path
        
        # 如果是 Windows 平台，且路径是 Linux 格式（以 / 开头但不是 //）
        if os.name == 'nt' and path.startswith('/') and not path.startswith('//'):
            # 获取当前工作目录的磁盘盘符
            current_dir = os.getcwd()
            drive = os.path.splitdrive(current_dir)[0]  # 例如：D:
            
            # 将 Linux 路径转换为 Windows 路径
            # /data/logs -> D:\data\logs
            # 移除开头的 /，然后分割路径组件
            path_parts = path.lstrip('/').split('/')
            # 使用 os.path.join 确保路径格式正确
            # 注意：drive 需要以反斜杠结尾，或使用 os.sep
            windows_path = os.path.join(drive + os.sep, *path_parts)
            return windows_path
        
        return path
    
    def _get_default_log_path(self, log_level: str) -> str:
        """
        获取默认日志文件路径（从 logback 配置中读取）
        
        Args:
            log_level: 日志级别 (error, warn, all)
        
        Returns:
            日志文件路径
        """
        if log_level == "error":
            return f"{self.log_path}/{self.app_name}/log_error.log"
        elif log_level == "warn":
            return f"{self.log_path}/{self.app_name}/log_warn.log"
        else:
            return f"{self.log_path}/{self.app_name}/all.log"
    
    def _get_log_file_path(self, log_level: str) -> str:
        """
        获取日志文件路径（优先使用外部配置，否则从 logback 读取）
        
        Args:
            log_level: 日志级别 (error, warn, all)
        
        Returns:
            日志文件路径
        """
        if log_level == "error" and self.error_log_path:
            return self.error_log_path
        elif log_level == "warn" and self.warn_log_path:
            return self.warn_log_path
        elif log_level == "all" and self.all_log_path:
            return self.all_log_path
        
        return self._get_default_log_path(log_level)
    
    def _parse_logback_config(self) -> Dict[str, Any]:
        """
        解析 logback 配置文件
        
        Returns:
            解析后的配置信息
        """
        try:
            tree = ET.parse(self.logback_config_path)
            root = tree.getroot()
            
            # 获取日志路径
            log_path_elem = root.find(".//property[@name='logging.path']")
            log_path = log_path_elem.get("value") if log_path_elem is not None else None
            
            # 获取应用名称
            app_name_elem = root.find(".//property[@name='spring.application.name']")
            app_name = app_name_elem.get("value") if app_name_elem is not None else None
            
            # 获取日志文件路径
            error_log_elem = root.find(".//appender[@name='error-file']/file")
            warn_log_elem = root.find(".//appender[@name='warn-file']/file")
            all_log_elem = root.find(".//appender[@name='file']/file")
            
            error_log_path = error_log_elem.text if error_log_elem is not None else None
            warn_log_path = warn_log_elem.text if warn_log_elem is not None else None
            all_log_path = all_log_elem.text if all_log_elem is not None else None
            
            return {
                "log_path": log_path,
                "app_name": app_name,
                "error_log_path": error_log_path,
                "warn_log_path": warn_log_path,
                "all_log_path": all_log_path
            }
        except Exception as e:
            print(f"解析 logback 配置文件时出错: {e}")
            return {}
    
    def _parse_log_entry(self, line: str) -> Optional[Dict[str, Any]]:
        """
        解析单行日志
        
        Args:
            line: 日志行
        
        Returns:
            解析后的日志条目
        """
        # 示例日志格式: 2023-05-01 10:30:45.123 ERROR [thread] com.example.Class - Message
        log_pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+(\w+)\s+\S+\s+app_id:(\S+)\s+---\s+\[(.*?)\]\s+(.+?)\s+:\s+(.*)"
        match = re.match(log_pattern, line)
        
        if match:
            timestamp, level, app_id, thread, logger, message = match.groups()
            return {
                "timestamp": timestamp,
                "level": level,
                "app_id": app_id,
                "thread": thread,
                "logger": logger,
                "message": message
            }
        
        return None
    
    def _extract_error_details(self, message: str, app_package: Optional[str]) -> Dict[str, Any]:
        """
        从错误消息中提取详细信息
        
        Args:
            message: 错误消息
            app_package: 应用包名（用于过滤堆栈）
        
        Returns:
            提取的错误详情
        """
        details = {
            "error_type": None,
            "error_message": None,
            "stack_trace": [],
            "app_stack_trace": []
        }
        
        lines = message.split("\\n")
        if not lines:
            return details
        
        # 第一行通常包含错误类型和消息
        first_line = lines[0]
        error_match = re.match(r"(\w+(?:\.\w+)*(?:Exception|Error)):?\s*(.*)", first_line)
        if error_match:
            details["error_type"] = error_match.group(1)
            details["error_message"] = error_match.group(2)
        
        # 提取堆栈跟踪
        stack_trace = []
        app_stack_trace = []
        for line in lines:
            line = line.strip()
            if line.startswith("at "):
                stack_trace.append(line)
                # 如果指定了应用包名，只保留应用包下的堆栈
                if app_package and app_package in line:
                    app_stack_trace.append(line)
        
        details["stack_trace"] = stack_trace
        details["app_stack_trace"] = app_stack_trace
        
        return details
    
    def _analyze_error_logs(self, log_lines: List[str]) -> Dict[str, Any]:
        """
        分析错误日志
        
        Args:
            log_lines: 日志行列表
        
        Returns:
            分析结果
        """
        errors = []
        current_error = None
        
        for line in log_lines:
            log_entry = self._parse_log_entry(line)
            
            if log_entry and log_entry["level"] == "ERROR":
                # 如果已有错误，先保存
                if current_error:
                    errors.append(current_error)
                
                # 新错误
                current_error = {
                    "timestamp": log_entry["timestamp"],
                    "message": log_entry["message"],
                    "details": self._extract_error_details(log_entry["message"], self.app_package)
                }
            elif current_error:
                # 追加堆栈信息
                current_error["message"] += "\\n" + line
                current_error["details"] = self._extract_error_details(current_error["message"], self.app_package)
        
        # 保存最后一个错误
        if current_error:
            errors.append(current_error)
        
        return {
            "error_count": len(errors),
            "errors": errors
        }
    
    def _analyze_warn_logs(self, log_lines: List[str]) -> Dict[str, Any]:
        """
        分析警告日志
        
        Args:
            log_lines: 日志行列表
        
        Returns:
            分析结果
        """
        warnings = []
        
        for line in log_lines:
            log_entry = self._parse_log_entry(line)
            
            if log_entry and log_entry["level"] == "WARN":
                warnings.append({
                    "timestamp": log_entry["timestamp"],
                    "message": log_entry["message"]
                })
        
        return {
            "warning_count": len(warnings),
            "warnings": warnings
        }
    
    def _search_logs(self, log_lines: List[str], keyword: str) -> Dict[str, Any]:
        """
        搜索日志中的关键词
        
        Args:
            log_lines: 日志行列表
            keyword: 关键词
        
        Returns:
            搜索结果
        """
        matches = []
        
        for line in log_lines:
            if keyword in line:
                matches.append(line)
        
        return {
            "keyword": keyword,
            "match_count": len(matches),
            "matches": matches
        }
    
    def analyze(self) -> Dict[str, Any]:
        """
        分析日志
        
        Returns:
            分析结果
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "app_name": self.app_name,
            "log_path": self.log_path,
        }
        
        # 分析错误日志
        error_log_path = self._get_log_file_path("error")
        if os.path.exists(error_log_path):
            with open(error_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_lines = f.readlines()
                results["error_logs"] = self._analyze_error_logs(log_lines)
        else:
            results["error_logs"] = {"error": f"错误日志文件不存在: {error_log_path}"}
        
        # 分析警告日志
        warn_log_path = self._get_log_file_path("warn")
        if os.path.exists(warn_log_path):
            with open(warn_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_lines = f.readlines()
                results["warn_logs"] = self._analyze_warn_logs(log_lines)
        else:
            results["warn_logs"] = {"error": f"警告日志文件不存在: {warn_log_path}"}
        
        return results
    
    def search_logs(self, keyword: str) -> Dict[str, Any]:
        """
        搜索日志
        
        Args:
            keyword: 关键词
        
        Returns:
            搜索结果
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "app_name": self.app_name,
            "log_path": self.log_path,
        }
        
        # 搜索错误日志
        error_log_path = self._get_log_file_path("error")
        if os.path.exists(error_log_path):
            with open(error_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_lines = f.readlines()
                results["error_logs"] = self._search_logs(log_lines, keyword)
        else:
            results["error_logs"] = {"error": f"错误日志文件不存在: {error_log_path}"}
        
        # 搜索警告日志
        warn_log_path = self._get_log_file_path("warn")
        if os.path.exists(warn_log_path):
            with open(warn_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_lines = f.readlines()
                results["warn_logs"] = self._search_logs(log_lines, keyword)
        else:
            results["warn_logs"] = {"error": f"警告日志文件不存在: {warn_log_path}"}
        
        return results
    
    def get_logback_config(self) -> Dict[str, Any]:
        """
        获取 logback 配置信息
        
        Returns:
            配置信息
        """
        return self.config
    
    def auto_fix_defect(self, error_type: str, error_message: str) -> Dict[str, Any]:
        """
        自动修复缺陷（示例实现）
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
        
        Returns:
            修复建议
        """
        # 这里只是示例，实际实现需要根据具体业务逻辑
        suggestions = [
            "检查配置文件中的参数设置",
            "确认数据库连接是否正常",
            "查看相关服务是否启动",
            "检查代码逻辑是否存在空指针"
        ]
        
        return {
            "error_type": error_type,
            "error_message": error_message,
            "suggestions": suggestions
        }


def analyze_logs(
    logback_config_path: Optional[str] = None,
    error_log_path: Optional[str] = None,
    warn_log_path: Optional[str] = None,
    all_log_path: Optional[str] = None,
) -> Dict[str, Any]:
    analyzer = LogAnalyzer(logback_config_path, error_log_path, warn_log_path, all_log_path)
    return analyzer.analyze()


def search_logs(
    keyword: str,
    logback_config_path: Optional[str] = None,
    error_log_path: Optional[str] = None,
    warn_log_path: Optional[str] = None,
    all_log_path: Optional[str] = None,
) -> Dict[str, Any]:
    analyzer = LogAnalyzer(logback_config_path, error_log_path, warn_log_path, all_log_path)
    return analyzer.search_logs(keyword)


def get_logback_config(logback_config_path: Optional[str] = None) -> Dict[str, Any]:
    analyzer = LogAnalyzer(logback_config_path)
    return analyzer.get_logback_config()


def auto_fix_defect(error_type: str, error_message: str) -> Dict[str, Any]:
    analyzer = LogAnalyzer()
    return analyzer.auto_fix_defect(error_type, error_message)


if FASTMCP_AVAILABLE:
    mcp = FastMCP("日志检索和分析工具")

    @mcp.tool()
    def analyze_logs_tool(
        logback_config_path: Optional[str] = None,
        error_log_path: Optional[str] = None,
        warn_log_path: Optional[str] = None,
        all_log_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return analyze_logs(logback_config_path, error_log_path, warn_log_path, all_log_path)

    @mcp.tool()
    def search_logs_tool(
        keyword: str,
        logback_config_path: Optional[str] = None,
        error_log_path: Optional[str] = None,
        warn_log_path: Optional[str] = None,
        all_log_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return search_logs(keyword, logback_config_path, error_log_path, warn_log_path, all_log_path)

    @mcp.tool()
    def get_logback_config_tool(logback_config_path: Optional[str] = None) -> Dict[str, Any]:
        return get_logback_config(logback_config_path)

    @mcp.tool()
    def auto_fix_defect_tool(error_type: str, error_message: str) -> Dict[str, Any]:
        return auto_fix_defect(error_type, error_message)


def main() -> None:
    if FastMCP is None:
        print("错误: 未安装 fastmcp 库")
        print("请运行: pip install fastmcp")
        return

    try:
        mcp.run()
    except Exception as exc:
        print(f"运行 FastMCP 服务器时出错: {exc}")


if __name__ == "__main__":
    main()
