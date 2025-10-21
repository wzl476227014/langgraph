"""
文件上传工具模块
提供PDF和Excel文件上传和处理功能
"""

import os
import uuid
import hashlib
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path
from ..utils.config import get_config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 尝试导入所需的库
try:
    import pypdf
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("pypdf库未安装，PDF处理功能将不可用")

try:
    import openpyxl
    import pandas as pd
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    logger.warning("openpyxl或pandas库未安装，Excel处理功能将不可用")


class FileUploadTool:
    """文件上传工具"""
    
    def __init__(self):
        """初始化文件上传工具"""
        self.config = get_config()
        self.file_upload_config = self.config.get_tool_config("file_upload")
        self.pdf_config = self.config.get_tool_config("pdf_processing")
        self.excel_config = self.config.get_tool_config("excel_processing")
        
        self.enabled = self.file_upload_config.get("enabled", True)
        self.max_file_size = self.file_upload_config.get("max_file_size", 10485760)  # 10MB
        self.allowed_types = self.file_upload_config.get("allowed_types", ["pdf", "xlsx", "xls"])
        self.upload_directory = self.file_upload_config.get("upload_directory", "uploads")
        self.temp_directory = self.file_upload_config.get("temp_directory", "temp")
        
        # 创建必要的目录
        self._create_directories()
        
        logger.info("文件上传工具初始化完成", agent_name="FileUploadTool")
    
    def _create_directories(self):
        """创建必要的目录"""
        try:
            os.makedirs(self.upload_directory, exist_ok=True)
            os.makedirs(self.temp_directory, exist_ok=True)
            logger.info(f"创建目录: {self.upload_directory}, {self.temp_directory}", agent_name="FileUploadTool")
        except Exception as e:
            logger.error(f"创建目录失败: {str(e)}", agent_name="FileUploadTool")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行文件上传任务
        
        Args:
            input_data: 输入数据，包含文件路径或文件信息
            
        Returns:
            处理结果字典
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "文件上传工具未启用",
                "result": None
            }
        
        task = input_data.get("task", "")
        file_path = input_data.get("file_path", "")
        operation = input_data.get("operation", "upload")
        
        if not task:
            return {
                "success": False,
                "error": "任务不能为空",
                "result": None
            }
        
        if not file_path and operation != "list":
            return {
                "success": False,
                "error": "文件路径不能为空",
                "result": None
            }
        
        try:
            logger.info(f"开始文件处理任务: {task}", agent_name="FileUploadTool")
            
            # 根据操作类型选择处理方法
            if operation == "upload":
                result = self._upload_file(file_path, task)
            elif operation == "process":
                result = self._process_file(file_path, task)
            elif operation == "validate":
                result = self._validate_file(file_path, task)
            elif operation == "list":
                result = self._list_files(task)
            elif operation == "remove":
                result = self._remove_file(file_path, task)
            else:
                result = self._default_operation(file_path, task, operation)
            
            processed_result = {
                "success": True,
                "task": task,
                "operation": operation,
                "result": result,
                "processed_at": datetime.now().isoformat(),
                "metadata": {
                    "file_path": file_path,
                    "operation": operation,
                    "tool_version": "1.0.0"
                }
            }
            
            logger.info(f"文件处理任务完成: {task}", agent_name="FileUploadTool")
            
            return processed_result
            
        except Exception as e:
            error_msg = f"文件处理失败: {str(e)}"
            logger.error(error_msg, agent_name="FileUploadTool")
            
            return {
                "success": False,
                "error": error_msg,
                "task": task,
                "result": None
            }
    
    def _upload_file(self, file_path: str, task: str) -> Dict[str, Any]:
        """上传文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 验证文件
        validation_result = self._validate_file(file_path, task)
        if not validation_result["valid"]:
            raise ValueError(f"文件验证失败: {validation_result['error']}")
        
        # 生成文件ID和目标路径
        file_id = str(uuid.uuid4())
        file_name = os.path.basename(file_path)
        file_extension = file_name.split('.')[-1].lower()
        target_file_name = f"{file_id}.{file_extension}"
        target_path = os.path.join(self.upload_directory, target_file_name)
        
        # 复制文件到上传目录
        import shutil
        shutil.copy2(file_path, target_path)
        
        # 生成文件信息
        file_info = {
            "file_id": file_id,
            "original_name": file_name,
            "file_path": target_path,
            "file_type": file_extension,
            "file_size": os.path.getsize(target_path),
            "upload_time": datetime.now().isoformat(),
            "task": task,
            "status": "uploaded"
        }
        
        # 处理文件内容
        processing_result = self._process_file_content(target_path, file_extension)
        file_info.update(processing_result)
        
        return file_info
    
    def _process_file(self, file_path: str, task: str) -> Dict[str, Any]:
        """处理文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        file_extension = os.path.basename(file_path).split('.')[-1].lower()
        
        return self._process_file_content(file_path, file_extension)
    
    def _validate_file(self, file_path: str, task: str) -> Dict[str, Any]:
        """验证文件"""
        if not os.path.exists(file_path):
            return {
                "valid": False,
                "error": "文件不存在",
                "file_info": None
            }
        
        file_name = os.path.basename(file_path)
        file_extension = file_name.split('.')[-1].lower()
        file_size = os.path.getsize(file_path)
        
        # 检查文件类型
        if file_extension not in self.allowed_types:
            return {
                "valid": False,
                "error": f"不支持的文件类型: {file_extension}",
                "file_info": None
            }
        
        # 检查文件大小
        if file_size > self.max_file_size:
            return {
                "valid": False,
                "error": f"文件大小超过限制: {file_size} > {self.max_file_size}",
                "file_info": None
            }
        
        # 检查文件是否可读
        if not os.access(file_path, os.R_OK):
            return {
                "valid": False,
                "error": "文件不可读",
                "file_info": None
            }
        
        file_info = {
            "file_name": file_name,
            "file_type": file_extension,
            "file_size": file_size,
            "is_readable": True,
            "validation_time": datetime.now().isoformat()
        }
        
        return {
            "valid": True,
            "error": None,
            "file_info": file_info
        }
    
    def _list_files(self, task: str) -> Dict[str, Any]:
        """列出文件"""
        files = []
        
        if os.path.exists(self.upload_directory):
            for file_name in os.listdir(self.upload_directory):
                file_path = os.path.join(self.upload_directory, file_name)
                if os.path.isfile(file_path):
                    file_stat = os.stat(file_path)
                    file_extension = file_name.split('.')[-1].lower()
                    
                    file_info = {
                        "file_name": file_name,
                        "file_path": file_path,
                        "file_type": file_extension,
                        "file_size": file_stat.st_size,
                        "created_time": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                        "modified_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    }
                    files.append(file_info)
        
        return {
            "files": files,
            "total_count": len(files),
            "directory": self.upload_directory
        }
    
    def _remove_file(self, file_path: str, task: str) -> Dict[str, Any]:
        """删除文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 安全检查：确保文件在上传目录中
        if not file_path.startswith(self.upload_directory):
            raise ValueError("只能删除上传目录中的文件")
        
        os.remove(file_path)
        
        return {
            "removed_file": file_path,
            "removed_time": datetime.now().isoformat(),
            "status": "removed"
        }
    
    def _default_operation(self, file_path: str, task: str, operation: str) -> Dict[str, Any]:
        """默认操作"""
        return {
            "operation": operation,
            "file_path": file_path,
            "task": task,
            "message": f"执行默认操作: {operation}",
            "status": "completed"
        }
    
    def _process_file_content(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """处理文件内容"""
        if file_type == "pdf":
            return self._process_pdf_file(file_path)
        elif file_type in ["xlsx", "xls"]:
            return self._process_excel_file(file_path)
        else:
            return {
                "content_type": "unknown",
                "processing_status": "skipped",
                "message": f"不支持的文件类型: {file_type}"
            }
    
    def _process_pdf_file(self, file_path: str) -> Dict[str, Any]:
        """处理PDF文件"""
        if not PDF_AVAILABLE:
            return {
                "content_type": "pdf",
                "processing_status": "failed",
                "error": "PDF处理库未安装"
            }
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                
                # 提取基本信息
                info = {
                    "content_type": "pdf",
                    "processing_status": "completed",
                    "page_count": len(pdf_reader.pages),
                    "file_info": {
                        "title": pdf_reader.metadata.get('/Title', ''),
                        "author": pdf_reader.metadata.get('/Author', ''),
                        "creator": pdf_reader.metadata.get('/Creator', ''),
                        "producer": pdf_reader.metadata.get('/Producer', ''),
                        "creation_date": pdf_reader.metadata.get('/CreationDate', '')
                    }
                }
                
                # 提取文本内容
                text_content = ""
                max_pages = self.pdf_config.get("max_pages", 100)
                
                for i, page in enumerate(pdf_reader.pages):
                    if i >= max_pages:
                        break
                    
                    try:
                        page_text = page.extract_text()
                        text_content += page_text + "\n\n"
                    except Exception as e:
                        logger.warning(f"提取第{i+1}页文本失败: {str(e)}", agent_name="FileUploadTool")
                        continue
                
                info["text_content"] = text_content
                info["text_length"] = len(text_content)
                info["extracted_pages"] = min(len(pdf_reader.pages), max_pages)
                
                # 分析文本内容
                if text_content:
                    content_analysis = self._analyze_text_content(text_content)
                    info["content_analysis"] = content_analysis
                
                return info
                
        except Exception as e:
            logger.error(f"处理PDF文件失败: {str(e)}", agent_name="FileUploadTool")
            return {
                "content_type": "pdf",
                "processing_status": "failed",
                "error": str(e)
            }
    
    def _process_excel_file(self, file_path: str) -> Dict[str, Any]:
        """处理Excel文件"""
        if not EXCEL_AVAILABLE:
            return {
                "content_type": "excel",
                "processing_status": "failed",
                "error": "Excel处理库未安装"
            }
        
        try:
            # 使用pandas读取Excel文件
            excel_data = pd.read_excel(file_path, sheet_name=None)
            
            info = {
                "content_type": "excel",
                "processing_status": "completed",
                "sheet_count": len(excel_data),
                "sheets": {}
            }
            
            max_rows = self.excel_config.get("max_rows", 10000)
            max_sheets = self.excel_config.get("max_sheets", 50)
            
            for sheet_name, df in excel_data.items():
                if len(info["sheets"]) >= max_sheets:
                    break
                
                # 限制行数
                df_limited = df.head(max_rows)
                
                sheet_info = {
                    "sheet_name": sheet_name,
                    "row_count": len(df_limited),
                    "column_count": len(df_limited.columns),
                    "columns": list(df_limited.columns),
                    "data_types": df_limited.dtypes.to_dict(),
                    "sample_data": df_limited.head(10).to_dict('records'),
                    "summary_stats": {}
                }
                
                # 生成统计信息
                try:
                    numeric_columns = df_limited.select_dtypes(include=['number']).columns
                    if len(numeric_columns) > 0:
                        sheet_info["summary_stats"] = df_limited[numeric_columns].describe().to_dict()
                except Exception as e:
                    logger.warning(f"生成统计信息失败: {str(e)}", agent_name="FileUploadTool")
                
                info["sheets"][sheet_name] = sheet_info
            
            return info
            
        except Exception as e:
            logger.error(f"处理Excel文件失败: {str(e)}", agent_name="FileUploadTool")
            return {
                "content_type": "excel",
                "processing_status": "failed",
                "error": str(e)
            }
    
    def _analyze_text_content(self, text: str) -> Dict[str, Any]:
        """分析文本内容"""
        if not text:
            return {}
        
        # 基本统计
        analysis = {
            "character_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.split('\n')),
            "paragraph_count": len([p for p in text.split('\n\n') if p.strip()]),
            "language": self._detect_language(text),
            "sentiment": self._analyze_sentiment(text),
            "keywords": self._extract_keywords(text),
            "topics": self._extract_topics(text)
        }
        
        return analysis
    
    def _detect_language(self, text: str) -> str:
        """检测文本语言"""
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len([c for c in text if c.isalpha()])
        
        if chinese_chars > english_chars:
            return "zh-CN"
        elif english_chars > 0:
            return "en"
        else:
            return "unknown"
    
    def _analyze_sentiment(self, text: str) -> str:
        """分析情感倾向"""
        positive_words = ["好", "优秀", "成功", "喜欢", "满意", "棒", "赞", "good", "great", "excellent", "love", "like"]
        negative_words = ["坏", "差", "失败", "讨厌", "不满", "糟", "bad", "terrible", "hate", "dislike", "fail"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        import re
        
        # 简单的关键词提取
        words = re.findall(r'\b[\w\u4e00-\u9fff]{2,}\b', text)
        word_freq = {}
        
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # 返回频率最高的词作为关键词
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:10]]
    
    def _extract_topics(self, text: str) -> List[str]:
        """提取主题"""
        import re
        
        words = re.findall(r'\b[\w\u4e00-\u9fff]+\b', text)
        word_freq = {}
        
        for word in words:
            if len(word) > 1:  # 忽略单字符
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 返回频率最高的词作为主题
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:5]]
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": "FileUploadTool",
            "description": "文件上传工具，提供PDF和Excel文件上传和处理功能",
            "version": "1.0.0",
            "enabled": self.enabled,
            "max_file_size": self.max_file_size,
            "allowed_types": self.allowed_types,
            "upload_directory": self.upload_directory,
            "pdf_available": PDF_AVAILABLE,
            "excel_available": EXCEL_AVAILABLE,
            "supported_operations": ["upload", "process", "validate", "list", "remove"],
            "capabilities": [
                "PDF文件上传和文本提取",
                "Excel文件上传和数据分析",
                "文件验证和类型检查",
                "文件内容分析和关键词提取",
                "多语言支持（中文、英文）"
            ]
        }
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        if not isinstance(input_data, dict):
            return False
        
        task = input_data.get("task", "")
        operation = input_data.get("operation", "")
        
        if not task or not isinstance(task, str):
            return False
        
        if not isinstance(operation, str):
            return False
        
        if operation != "list":
            file_path = input_data.get("file_path", "")
            if not file_path or not isinstance(file_path, str):
                return False
        
        return True
    
    def enable_tool(self) -> None:
        """启用工具"""
        self.enabled = True
        logger.info("文件上传工具已启用", agent_name="FileUploadTool")
    
    def disable_tool(self) -> None:
        """禁用工具"""
        self.enabled = False
        logger.info("文件上传工具已禁用", agent_name="FileUploadTool")
    
    def cleanup_temp_files(self) -> None:
        """清理临时文件"""
        try:
            if os.path.exists(self.temp_directory):
                for file_name in os.listdir(self.temp_directory):
                    file_path = os.path.join(self.temp_directory, file_name)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                logger.info("临时文件清理完成", agent_name="FileUploadTool")
        except Exception as e:
            logger.error(f"清理临时文件失败: {str(e)}", agent_name="FileUploadTool")
