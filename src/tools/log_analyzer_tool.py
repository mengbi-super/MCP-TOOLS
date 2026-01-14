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
    "src/resource/logback-spring.xml"
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
                - 如果环境变量不存在，使用默认路径 "src/resource/logback-spring.xml"
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
        else:
            return self._get_default_log_path(log_level)
    
    def _parse_logback_config(self) -> Dict[str, Any]:
        """解析 logback-spring.xml 配置文件"""
        config = {}
        try:
            if not os.path.exists(self.logback_config_path):
                return config
            
            tree = ET.parse(self.logback_config_path)
            root = tree.getroot()
            
            # 提取 contextName
            context_name = root.find("contextName")
            if context_name is not None:
                config["app_name"] = context_name.text
            
            # 提取属性
            for prop in root.findall(".//property"):
                name = prop.get("name", "")
                value = prop.get("value", "")
                
                if name == "logging.path":
                    config["log_path"] = value
                elif name == "spring.application.name":
                    config["app_name"] = value
            
            # 提取日志文件路径
            appenders = []
            for appender in root.findall(".//appender"):
                appender_name = appender.get("name", "")
                file_elem = appender.find("file")
                if file_elem is not None:
                    file_path = file_elem.text
                    if file_path:
                        appenders.append({
                            "name": appender_name,
                            "file": file_path
                        })
            
            config["appenders"] = appenders
            
        except Exception as e:
            print(f"解析 logback 配置时出错: {e}")
        
        return config
    
    def _read_log_file(self, file_path: str, max_lines: int = 1000) -> List[str]:
        """
        读取日志文件
        
        Args:
            file_path: 日志文件路径
            max_lines: 最大读取行数
        
        Returns:
            日志行列表
        """
        lines = []
        try:
            # 展开变量
            expanded_path = file_path.replace("${logging.path}", self.log_path)
            expanded_path = expanded_path.replace("${spring.application.name}", self.app_name)
            
            # 转换路径格式（如果是 Linux 路径在 Windows 上）
            expanded_path = self._convert_path_for_platform(expanded_path)
            
            # 检查文件是否存在
            if not os.path.exists(expanded_path):
                # 尝试原始路径（如果不同）
                if expanded_path != file_path:
                    original_path = self._convert_path_for_platform(file_path)
                    if os.path.exists(original_path):
                        expanded_path = original_path
                    else:
                        return lines
                else:
                    return lines
            
            with open(expanded_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-max_lines:]  # 只读取最后 N 行
        except Exception as e:
            # 只在调试模式下打印错误
            if os.getenv("LOG_ANALYZER_DEBUG"):
                print(f"读取日志文件 {file_path} 时出错: {e}")
        
        return lines
    
    def _validate_log_path(self, log_path: str) -> Dict[str, Any]:
        """
        验证日志路径是否存在，并提供建议
        
        Args:
            log_path: 日志文件路径
        
        Returns:
            验证结果字典
        """
        result = {
            "exists": False,
            "path": log_path,
            "suggestions": []
        }
        
        if not log_path:
            return result
        
        # 检查文件是否存在
        file_exists = os.path.exists(log_path)
        
        # 在 Windows 上，检查是否是 Linux 路径格式
        is_linux_path_on_windows = False
        if os.name == 'nt':  # Windows
            # 检测 Linux 路径格式（以 / 开头但不是 // 开头的 UNC 路径）
            if log_path.startswith('/') and not log_path.startswith('//'):
                # 检查是否是典型的 Linux 路径（如 /data/logs, /var/log 等）
                linux_path_patterns = ['/data/', '/var/', '/tmp/', '/usr/', '/opt/']
                if any(log_path.startswith(pattern) for pattern in linux_path_patterns):
                    is_linux_path_on_windows = True
        
        # 如果文件存在，但可能是 Windows 误解析的 Linux 路径，仍然提示
        if file_exists and not is_linux_path_on_windows:
            result["exists"] = True
            return result
        
        # 文件不存在或检测到 Linux 路径在 Windows 上
        if is_linux_path_on_windows:
            result["suggestions"].append(
                "检测到 Linux 路径格式（/data/logs），在 Windows 上可能不存在。"
            )
            result["suggestions"].append(
                "建议：使用环境变量 ERROR_LOG_PATH 指定 Windows 路径，"
                "例如：D:\\logs\\error.log 或使用相对路径 logs\\error.log"
            )
        elif not file_exists:
            result["suggestions"].append(
                f"日志文件不存在：{log_path}"
            )
            result["suggestions"].append(
                "建议：检查路径是否正确，或使用环境变量配置日志文件路径"
            )
        
        return result
    
    def _extract_exception_info(self, log_line: str) -> Optional[Dict[str, Any]]:
        """
        智能提取异常信息（不限于预定义模式）
        
        Args:
            log_line: 日志行
        
        Returns:
            异常信息字典，如果未找到异常则返回 None
        """
        if not log_line:
            return None
        
        # 提取关键信息
        key_info = self._extract_key_info(log_line, max_length=200)
        
        # 检测异常类型（使用更通用的模式）
        # 匹配 Java 异常：ExceptionName: message
        exception_match = re.search(r'(\w+Exception|\w+Error)(?:\s*:\s*|\s+)(.+?)(?:\s+at\s+|\s*$)', log_line, re.IGNORECASE)
        if exception_match:
            exception_type = exception_match.group(1)
            exception_message = exception_match.group(2).strip()[:100]  # 限制消息长度
            
            # 根据异常类型推断严重程度
            severity = self._infer_severity(exception_type)
            
            return {
                "key_info": key_info,
                "exception_type": exception_type,
                "exception_message": exception_message,
                "severity": severity,
                "pattern": exception_type
            }
        
        # 检测其他错误模式（如 "Error:", "Failed:", "denied" 等）
        error_patterns = [
            (r'Error:\s*(.+?)(?:\s+at\s+|\s*$)', "错误", "high"),
            (r'Failed\s+to\s+(.+?)(?:\s+at\s+|\s*$)', "操作失败", "medium"),
            (r'denied|refused|rejected', "拒绝访问", "medium"),
            (r'timeout|timed out', "超时", "medium"),
        ]
        
        for pattern, error_type, default_severity in error_patterns:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if match:
                return {
                    "key_info": key_info,
                    "exception_type": error_type,
                    "exception_message": match.group(1) if match.groups() else "",
                    "severity": default_severity,
                    "pattern": pattern
                }
        
        return None
    
    def _infer_severity(self, exception_type: str) -> str:
        """
        根据异常类型推断严重程度
        
        Args:
            exception_type: 异常类型名称
        
        Returns:
            严重程度 (critical, high, medium)
        """
        exception_type_lower = exception_type.lower()
        
        # Critical 级别
        if any(keyword in exception_type_lower for keyword in ['outofmemory', 'stackoverflow', 'outofmemoryerror', 'stackoverflowerror']):
            return "critical"
        
        # High 级别
        if any(keyword in exception_type_lower for keyword in ['nullpointer', 'indexoutofbounds', 'classnotfound', 'methodnotfound', 'nosuchelement', 'illegalstate']):
            return "high"
        
        # Medium 级别（默认）
        return "medium"
    
    def _extract_key_info(self, log_line: str, max_length: int = 200) -> str:
        """
        提取日志行的关键信息，去除冗余内容
        
        Args:
            log_line: 原始日志行
            max_length: 最大长度限制
        
        Returns:
            精简后的日志内容
        """
        if not log_line:
            return ""
        
        # 移除常见的冗余前缀（时间戳、PID、线程ID等）
        # 匹配类似 "2025-11-08 15:12:41.792 ERROR 39744 TID: N/A app_id:xxx --- [thread] logger :" 的前缀
        cleaned = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s+\w+\s+\d+\s+[^\s]+\s+[^\s]+\s+---\s+\[[^\]]+\]\s+[^\s]+\s*:\s*', '', log_line)
        
        # 如果清理后为空，使用原始行
        if not cleaned.strip():
            cleaned = log_line
        
        # 提取异常信息（Exception后面的内容通常是关键）
        exception_match = re.search(r'(Exception|Error|Failed|Timeout|denied)[^:]*:?\s*(.+?)(?:\s+at\s+|\s*$)', cleaned, re.IGNORECASE)
        if exception_match:
            cleaned = exception_match.group(0).strip()
        
        # 处理堆栈跟踪：保留应用包下的堆栈信息，过滤底层框架信息
        if 'at ' in cleaned:
            # 分割异常信息和堆栈跟踪
            parts = cleaned.split('at ')
            exception_part = parts[0].strip()
            stack_trace = 'at ' + 'at '.join(parts[1:]) if len(parts) > 1 else ""
            
            if stack_trace:
                # 过滤堆栈跟踪，只保留应用包下的信息
                filtered_stack = self._filter_stack_trace(stack_trace)
                if filtered_stack:
                    cleaned = exception_part + " " + filtered_stack
                else:
                    # 如果没有应用包的堆栈信息，只保留异常信息
                    cleaned = exception_part
        
        # 限制长度
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + "..."
        
        return cleaned.strip()
    
    def _filter_stack_trace(self, stack_trace: str) -> str:
        """
        过滤堆栈跟踪，只保留应用包下的堆栈信息，移除底层框架信息
        
        Args:
            stack_trace: 堆栈跟踪字符串
        
        Returns:
            过滤后的堆栈跟踪（只包含应用包下的信息）
        """
        if not stack_trace:
            return ""
        
        # 常见的框架包前缀（需要过滤掉）
        framework_packages = [
            'java.', 'javax.', 'sun.', 'com.sun.',
            'org.springframework.', 'org.apache.', 'org.hibernate.',
            'ch.qos.logback.', 'org.slf4j.', 'com.zaxxer.',
            'com.alibaba.', 'io.netty.', 'reactor.',
            'org.mybatis.', 'com.baomidou.', 'com.mysql.',
            'oracle.', 'com.microsoft.', 'com.ibm.'
        ]
        
        lines = stack_trace.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line or not line.startswith('at '):
                continue
            
            # 检查是否是应用包的堆栈信息
            is_app_package = False
            
            if self.app_package:
                # 如果配置了应用包名，检查是否属于应用包
                # 堆栈格式：at com.example.Service.method(Service.java:123)
                if self.app_package in line:
                    is_app_package = True
            else:
                # 如果没有配置包名，过滤掉明显的框架包
                is_framework = any(line.startswith(f'at {pkg}') for pkg in framework_packages)
                if not is_framework:
                    # 不是框架包，可能是应用代码
                    is_app_package = True
            
            if is_app_package:
                filtered_lines.append(line)
        
        # 如果找到了应用包的堆栈信息，返回（最多保留3层）
        if filtered_lines:
            return '\n'.join(filtered_lines[:3])
        
        return ""
    
    def _get_error_patterns(self) -> List[tuple]:
        """
        获取错误模式列表
        
        支持从环境变量读取自定义模式（JSON 格式），格式：
        ERROR_PATTERNS='[{"pattern": "正则表达式", "description": "描述", "severity": "critical|high|medium"}]'
        
        Returns:
            错误模式列表，每个元素为 (pattern, description, severity) 元组
        """
        # 默认错误模式
        default_patterns = [
            (r"NullPointerException", "空指针异常", "high"),
            (r"IndexOutOfBoundsException", "数组越界异常", "high"),
            (r"SQLException|DatabaseException", "数据库异常", "high"),
            (r"Connection.*refused|Connection.*timeout", "连接异常", "medium"),
            (r"OutOfMemoryError", "内存溢出", "critical"),
            (r"StackOverflowError", "栈溢出", "critical"),
            (r"ClassNotFoundException", "类未找到", "high"),
            (r"MethodNotFoundException", "方法未找到", "high"),
            (r"TimeoutException|ReadTimeout|ConnectTimeout", "超时异常", "medium"),
            (r"FileNotFoundException", "文件未找到", "medium"),
            (r"Permission denied|Access denied", "权限拒绝", "medium"),
        ]
        
        # 尝试从环境变量读取自定义模式
        custom_patterns_json = os.getenv("ERROR_PATTERNS")
        if custom_patterns_json:
            try:
                import json
                custom_patterns = json.loads(custom_patterns_json)
                # 转换为元组列表
                custom_patterns_list = [
                    (item["pattern"], item["description"], item.get("severity", "medium"))
                    for item in custom_patterns
                    if "pattern" in item and "description" in item
                ]
                # 合并默认模式和自定义模式（自定义模式优先，去重）
                patterns_dict = {}
                for pattern, desc, severity in default_patterns:
                    patterns_dict[pattern] = (pattern, desc, severity)
                for pattern, desc, severity in custom_patterns_list:
                    patterns_dict[pattern] = (pattern, desc, severity)
                return list(patterns_dict.values())
            except Exception as e:
                # 如果解析失败，使用默认模式
                if os.getenv("LOG_ANALYZER_DEBUG"):
                    print(f"解析自定义错误模式失败: {e}，使用默认模式")
        
        return default_patterns
    
    def _is_relevant_log_line(self, line: str) -> bool:
        """
        判断日志行是否相关（过滤无关信息）
        
        Args:
            line: 日志行
        
        Returns:
            是否相关
        """
        if not line or len(line.strip()) < 10:
            return False
        
        # 过滤掉明显的无关信息
        irrelevant_patterns = [
            r'^\s*$',  # 空行
            r'DEBUG\s+.*',  # DEBUG 级别日志（通常不重要）
            r'INFO\s+.*启动',  # 启动信息
            r'INFO\s+.*关闭',  # 关闭信息
            r'INFO\s+.*连接',  # 普通连接信息
        ]
        
        for pattern in irrelevant_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return False
        
        return True
    
    def analyze_logs(
        self,
        log_level: str = "error",
        max_lines: int = 1000,
        error_log_path: Optional[str] = None,
        warn_log_path: Optional[str] = None,
        all_log_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析日志文件，检测代码缺陷
        
        Args:
            log_level: 日志级别 (error, warn, all)
            max_lines: 最大读取行数
            error_log_path: 错误日志文件路径（可选，覆盖初始化时的配置）
            warn_log_path: 警告日志文件路径（可选，覆盖初始化时的配置）
            all_log_path: 全部日志文件路径（可选，覆盖初始化时的配置）
        
        Returns:
            包含缺陷信息的字典
        """
        defects = []
        # 确定日志文件路径（优先级：方法参数 > 实例配置 > logback 配置）
        log_file = None
        if log_level == "error":
            log_file = error_log_path or self.error_log_path
        elif log_level == "warn":
            log_file = warn_log_path or self.warn_log_path
        else:  # all
            log_file = all_log_path or self.all_log_path
        
        # 如果外部配置都没有，从 logback 配置中读取
        if log_file is None:
            log_file = self._get_log_file_path(log_level)
        
        log_files = [log_file]
        
        all_log_lines = []
        for log_file in log_files:
            lines = self._read_log_file(log_file, max_lines)
            all_log_lines.extend(lines)
        
        # 分析日志行 - 智能分析模式：自动提取所有异常信息，交给大模型分析
        for line_num, line in enumerate(all_log_lines, 1):
            # 过滤无关日志行
            if not self._is_relevant_log_line(line):
                continue
            
            # 检测是否包含异常信息（自动识别所有异常类型，不限于预定义模式）
            exception_info = self._extract_exception_info(line)
            if exception_info:
                defects.append({
                    "line_number": line_num,
                    "log_line": exception_info["key_info"],
                    "defect_type": exception_info["exception_type"],
                    "severity": exception_info["severity"],
                    "pattern": exception_info.get("pattern", ""),
                    "exception_message": exception_info.get("exception_message", ""),
                    "suggestion": None  # 让大模型分析生成建议
                })
        
        # 按严重程度排序，优先返回严重的问题
        defects.sort(key=lambda x: {"critical": 0, "high": 1, "medium": 2}.get(x["severity"], 3))
        
        # 限制返回数量，避免消耗太多token（最多返回50个）
        max_defects = 50
        defects_limited = defects[:max_defects]
        
        # 验证日志文件路径
        path_validation = self._validate_log_path(log_files[0] if log_files else "")
        warnings = []
        if path_validation["suggestions"]:
            # 直接使用验证结果中的建议（已经包含了路径信息）
            warnings.extend(path_validation["suggestions"][:2])  # 只添加前2个建议
        
        return {
            "total_defects": len(defects),
            "defects": defects_limited,
            "log_files_analyzed": log_files,
            "analysis_time": datetime.now().isoformat(),
            "note": f"显示前 {min(max_defects, len(defects))} 个缺陷（按严重程度排序）" if len(defects) > max_defects else None,
            "warnings": warnings if warnings else None
        }
    
    def _generate_fix_suggestion(self, pattern: str, log_line: str) -> str:
        """根据错误模式生成修复建议"""
        suggestions = {
            r"NullPointerException": "添加空值检查，使用 Optional 或空值判断",
            r"IndexOutOfBoundsException": "检查数组/列表边界，确保索引在有效范围内",
            r"SQLException|DatabaseException": "检查 SQL 语句、数据库连接和事务处理",
            r"Connection.*refused|Connection.*timeout": "检查网络连接、服务是否启动、超时配置",
            r"OutOfMemoryError": "增加 JVM 堆内存或优化内存使用",
            r"StackOverflowError": "检查递归调用深度，优化算法",
            r"ClassNotFoundException": "检查类路径配置和依赖项",
            r"MethodNotFoundException": "检查方法名和方法签名",
            r"TimeoutException|ReadTimeout|ConnectTimeout": "增加超时时间或优化处理逻辑",
            r"FileNotFoundException": "检查文件路径和文件是否存在",
            r"Permission denied|Access denied": "检查文件/目录权限",
        }
        
        for key, suggestion in suggestions.items():
            if re.search(key, pattern, re.IGNORECASE):
                return suggestion
        
        return "检查代码逻辑和异常处理"
    
    def auto_fix_code(self, defect_info: Dict[str, Any], source_code_path: Optional[str] = None) -> Dict[str, Any]:
        """根据缺陷信息自动修复代码"""
        fixes = []
        defect_type = defect_info.get("defect_type", "")
        pattern = defect_info.get("pattern", "")
        
        # 这里可以根据缺陷类型生成具体的修复代码
        # 由于需要分析源代码，这里提供修复建议和模板
        
        fix_templates = {
            "空指针异常": {
                "before": "obj.method()",
                "after": "if obj is not None:\n    obj.method()",
                "description": "添加空值检查"
            },
            "数组越界异常": {
                "before": "arr[index]",
                "after": "if 0 <= index < len(arr):\n    arr[index]",
                "description": "添加边界检查"
            },
            "数据库异常": {
                "before": "cursor.execute(sql)",
                "after": "try:\n    cursor.execute(sql)\nexcept SQLException as e:\n    logger.error(f'数据库操作失败: {e}')\n    raise",
                "description": "添加异常处理"
            }
        }
        
        for key, template in fix_templates.items():
            if key in defect_type:
                fixes.append(template)
                break
        
        return {
            "defect": defect_info,
            "fixes": fixes,
            "status": "suggested" if fixes else "manual_review_required"
        }


# 创建 FastMCP 服务器
if FASTMCP_AVAILABLE:
    mcp = FastMCP("日志检索和分析工具")
    
    @mcp.tool()
    def analyze_logs(
        log_level: str = "error",
        max_lines: int = 1000,
        logback_config: Optional[str] = None,
        error_log_path: Optional[str] = None,
        warn_log_path: Optional[str] = None,
        all_log_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析日志文件，检测代码缺陷
        
        Args:
            log_level: 日志级别 (error, warn, all)
            max_lines: 最大读取行数
            logback_config: logback 配置文件路径（可选）
                - 如果为 None，使用环境变量 LOGBACK_CONFIG_PATH 或默认路径
            error_log_path: 错误日志文件路径（可选）
                - 如果为 None，从 logback 配置中读取
            warn_log_path: 警告日志文件路径（可选）
                - 如果为 None，从 logback 配置中读取
            all_log_path: 全部日志文件路径（可选）
                - 如果为 None，从 logback 配置中读取
        
        Returns:
            包含缺陷信息的字典
        """
        analyzer = LogAnalyzer(
            logback_config_path=logback_config,
            error_log_path=error_log_path,
            warn_log_path=warn_log_path,
            all_log_path=all_log_path
        )
        return analyzer.analyze_logs(log_level, max_lines)
    
    @mcp.tool()
    def get_logback_config(logback_config: Optional[str] = None) -> Dict[str, Any]:
        """
        获取 logback 配置信息
        
        Args:
            logback_config: logback 配置文件路径（可选）
                - 如果为 None，使用环境变量 LOGBACK_CONFIG_PATH 或默认路径
        
        Returns:
            配置信息字典
        """
        analyzer = LogAnalyzer(logback_config)
        return analyzer.config
    
    @mcp.tool()
    def auto_fix_defect(
        defect_info: Dict[str, Any],
        source_code_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        根据缺陷信息自动生成修复建议
        
        Args:
            defect_info: 缺陷信息字典
            source_code_path: 源代码文件路径（可选）
        
        Returns:
            修复建议字典
        """
        analyzer = LogAnalyzer()
        return analyzer.auto_fix_code(defect_info, source_code_path)
    
    @mcp.tool()
    def search_logs(
        keyword: str,
        log_level: str = "all",
        max_lines: int = 1000,
        logback_config: Optional[str] = None,
        error_log_path: Optional[str] = None,
        warn_log_path: Optional[str] = None,
        all_log_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        在日志中搜索关键词
        
        Args:
            keyword: 搜索关键词
            log_level: 日志级别 (error, warn, all)
            max_lines: 最大读取行数
            logback_config: logback 配置文件路径（可选）
                - 如果为 None，使用环境变量 LOGBACK_CONFIG_PATH 或默认路径
            error_log_path: 错误日志文件路径（可选）
                - 如果为 None，从 logback 配置中读取
            warn_log_path: 警告日志文件路径（可选）
                - 如果为 None，从 logback 配置中读取
            all_log_path: 全部日志文件路径（可选）
                - 如果为 None，从 logback 配置中读取
        
        Returns:
            包含匹配结果的字典
        """
        analyzer = LogAnalyzer(
            logback_config_path=logback_config,
            error_log_path=error_log_path,
            warn_log_path=warn_log_path,
            all_log_path=all_log_path
        )
        
        # 获取日志文件路径（优先级：方法参数 > 实例配置 > logback 配置）
        log_file = None
        if log_level == "error":
            log_file = error_log_path
        elif log_level == "warn":
            log_file = warn_log_path
        else:  # all
            log_file = all_log_path
        
        # 如果外部配置没有，从 logback 配置中读取
        if log_file is None:
            log_file = analyzer._get_log_file_path(log_level)
        
        log_files = [log_file]
        
        matches = []
        for log_file in log_files:
            lines = analyzer._read_log_file(log_file, max_lines)
            for line_num, line in enumerate(lines, 1):
                # 过滤无关日志行
                if not analyzer._is_relevant_log_line(line):
                    continue
                    
                if keyword.lower() in line.lower():
                    # 提取关键信息，减少token消耗
                    key_info = analyzer._extract_key_info(line, max_length=150)
                    
                    matches.append({
                        "file": log_file,
                        "line_number": line_num,
                        "content": key_info  # 使用精简后的日志内容
                    })
        
        # 限制返回数量，避免消耗太多token（最多返回30个）
        max_matches = 30
        matches_limited = matches[:max_matches]
        
        # 验证日志文件路径
        path_validation = analyzer._validate_log_path(log_file)
        warnings = []
        if path_validation["suggestions"]:
            # 直接使用验证结果中的建议（已经包含了路径信息）
            warnings.extend(path_validation["suggestions"][:2])  # 只添加前2个建议
        
        return {
            "keyword": keyword,
            "total_matches": len(matches),
            "matches": matches_limited,
            "search_time": datetime.now().isoformat(),
            "note": f"显示前 {min(max_matches, len(matches))} 个匹配结果" if len(matches) > max_matches else None,
            "warnings": warnings if warnings else None
        }


def main():
    """主函数 - 用于测试"""
    if FastMCP is None:
        print("错误: 未安装 fastmcp 库")
        print("请运行: pip install fastmcp")
        return
    
    # 测试日志分析器
    analyzer = LogAnalyzer()
    print("Logback 配置:")
    print(analyzer.config)
    print("\n" + "="*50 + "\n")
    
    # 分析日志
    result = analyzer.analyze_logs("error", 100)
    print(f"发现 {result['total_defects']} 个缺陷")
    for defect in result['defects'][:5]:  # 只显示前5个
        print(f"\n缺陷类型: {defect['defect_type']}")
        print(f"严重程度: {defect['severity']}")
        print(f"修复建议: {defect['suggestion']}")
        print(f"日志行: {defect['log_line'][:100]}...")


if __name__ == "__main__":
    if FASTMCP_AVAILABLE:
        # 运行 FastMCP 服务器
        try:
            mcp.run()
        except Exception as e:
            print(f"运行 FastMCP 服务器时出错: {e}")
            print("切换到测试模式...")
            main()
    else:
        # 运行测试
        main()
