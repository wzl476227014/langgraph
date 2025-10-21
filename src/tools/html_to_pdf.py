"""
HTML转PDF工具模块
用于将HTML文件或目录中的HTML文件批量转换为PDF
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import argparse
from datetime import datetime

# PDF生成库
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False
    print("警告: pdfkit未安装，尝试使用weasyprint")

try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    print("警告: weasyprint未安装")

# 如果都没有，尝试使用playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("警告: playwright未安装")

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HtmlToPdfConverter:
    """HTML转PDF转换器"""
    
    def __init__(self, method: str = "auto", options: Dict[str, Any] = None):
        """
        初始化转换器
        
        Args:
            method: 转换方法 ("pdfkit", "weasyprint", "playwright", "auto")
            options: 转换选项
        """
        self.method = self._select_method(method)
        self.options = options or {}
        
        # 默认PDF选项
        self.pdf_options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'enable-local-file-access': None,
            'no-outline': False
        }
        
        # 如果是16:9的PPT，使用特殊设置
        if self.options.get('ppt_mode'):
            self.pdf_options.update({
                'page-width': '297mm',  # A4横向宽度
                'page-height': '167mm',  # 16:9比例高度
                'margin-top': '10mm',
                'margin-right': '10mm',
                'margin-bottom': '10mm',
                'margin-left': '10mm',
            })
        
        self.pdf_options.update(self.options.get('pdf_options', {}))
        
    def _select_method(self, method: str) -> str:
        """选择可用的转换方法"""
        if method == "auto":
            if PDFKIT_AVAILABLE:
                return "pdfkit"
            elif WEASYPRINT_AVAILABLE:
                return "weasyprint"
            elif PLAYWRIGHT_AVAILABLE:
                return "playwright"
            else:
                raise RuntimeError(
                    "没有可用的PDF转换库。请安装以下任一库：\n"
                    "1. pip install pdfkit (需要安装wkhtmltopdf)\n"
                    "2. pip install weasyprint\n"
                    "3. pip install playwright && playwright install chromium"
                )
        
        # 检查指定方法是否可用
        if method == "pdfkit" and not PDFKIT_AVAILABLE:
            raise RuntimeError("pdfkit未安装: pip install pdfkit")
        elif method == "weasyprint" and not WEASYPRINT_AVAILABLE:
            raise RuntimeError("weasyprint未安装: pip install weasyprint")
        elif method == "playwright" and not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright未安装: pip install playwright && playwright install chromium")
        
        return method
    
    def convert_html_to_pdf(self, html_path: str, pdf_path: str = None) -> bool:
        """
        将单个HTML文件转换为PDF
        
        Args:
            html_path: HTML文件路径
            pdf_path: 输出PDF路径（可选，默认同名PDF）
            
        Returns:
            转换是否成功
        """
        html_path = Path(html_path)
        
        if not html_path.exists():
            logger.error(f"HTML文件不存在: {html_path}")
            return False
        
        # 默认PDF路径
        if pdf_path is None:
            pdf_path = html_path.with_suffix('.pdf')
        else:
            pdf_path = Path(pdf_path)
        
        # 确保输出目录存在
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if self.method == "pdfkit":
                return self._convert_with_pdfkit(str(html_path), str(pdf_path))
            elif self.method == "weasyprint":
                return self._convert_with_weasyprint(str(html_path), str(pdf_path))
            elif self.method == "playwright":
                return self._convert_with_playwright(str(html_path), str(pdf_path))
            else:
                logger.error(f"未知的转换方法: {self.method}")
                return False
        except Exception as e:
            logger.error(f"转换失败 {html_path} -> {pdf_path}: {str(e)}")
            return False
    
    def _convert_with_pdfkit(self, html_path: str, pdf_path: str) -> bool:
        """使用pdfkit转换"""
        try:
            # 读取HTML内容
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 添加base标签以支持相对路径
            if '<base' not in html_content:
                base_path = Path(html_path).parent.as_uri()
                html_content = html_content.replace('<head>', f'<head>\n<base href="{base_path}/">')
            
            # 转换为PDF
            pdfkit.from_string(html_content, pdf_path, options=self.pdf_options)
            logger.info(f"✅ 成功转换: {Path(html_path).name} -> {Path(pdf_path).name}")
            return True
        except Exception as e:
            logger.error(f"pdfkit转换失败: {str(e)}")
            return False
    
    def _convert_with_weasyprint(self, html_path: str, pdf_path: str) -> bool:
        """使用weasyprint转换"""
        try:
            # 创建HTML文档
            html = weasyprint.HTML(filename=html_path)
            
            # 转换为PDF
            html.write_pdf(pdf_path)
            logger.info(f"✅ 成功转换: {Path(html_path).name} -> {Path(pdf_path).name}")
            return True
        except Exception as e:
            logger.error(f"weasyprint转换失败: {str(e)}")
            return False
    
    def _convert_with_playwright(self, html_path: str, pdf_path: str) -> bool:
        """使用playwright转换"""
        try:
            with sync_playwright() as p:
                # 启动浏览器
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 加载HTML文件
                file_url = Path(html_path).as_uri()
                page.goto(file_url)
                
                # 等待页面加载完成
                page.wait_for_load_state("networkidle")
                
                # 生成PDF
                pdf_options = {
                    'path': pdf_path,
                    'format': 'A4',
                    'print_background': True,
                    'margin': {
                        'top': self.pdf_options.get('margin-top', '20mm'),
                        'bottom': self.pdf_options.get('margin-bottom', '20mm'),
                        'left': self.pdf_options.get('margin-left', '20mm'),
                        'right': self.pdf_options.get('margin-right', '20mm'),
                    }
                }
                
                # 如果是PPT模式，调整尺寸
                if self.options.get('ppt_mode'):
                    pdf_options['format'] = 'A4'
                    pdf_options['landscape'] = True
                
                page.pdf(**pdf_options)
                
                # 关闭浏览器
                browser.close()
                
            logger.info(f"✅ 成功转换: {Path(html_path).name} -> {Path(pdf_path).name}")
            return True
        except Exception as e:
            logger.error(f"playwright转换失败: {str(e)}")
            return False
    
    def convert_directory(self, input_dir: str, output_dir: str = None, 
                         pattern: str = "*.html", merge: bool = False) -> Dict[str, Any]:
        """
        批量转换目录中的HTML文件
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录（可选，默认同目录）
            pattern: 文件匹配模式
            merge: 是否合并为单个PDF
            
        Returns:
            转换结果统计
        """
        input_path = Path(input_dir)
        
        if not input_path.exists() or not input_path.is_dir():
            logger.error(f"输入目录不存在: {input_dir}")
            return {"success": 0, "failed": 0, "files": []}
        
        # 默认输出目录
        if output_dir is None:
            output_path = input_path / "pdf_output"
        else:
            output_path = Path(output_dir)
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 查找HTML文件
        html_files = sorted(input_path.glob(pattern))
        
        if not html_files:
            logger.warning(f"未找到匹配的HTML文件: {pattern}")
            return {"success": 0, "failed": 0, "files": []}
        
        logger.info(f"找到 {len(html_files)} 个HTML文件")
        
        if merge:
            # 合并为单个PDF
            return self._merge_to_single_pdf(html_files, output_path)
        else:
            # 分别转换
            return self._convert_separately(html_files, output_path)
    
    def _convert_separately(self, html_files: List[Path], output_path: Path) -> Dict[str, Any]:
        """分别转换每个HTML文件"""
        results = {"success": 0, "failed": 0, "files": []}
        
        for html_file in html_files:
            pdf_file = output_path / html_file.with_suffix('.pdf').name
            
            if self.convert_html_to_pdf(str(html_file), str(pdf_file)):
                results["success"] += 1
                results["files"].append(str(pdf_file))
            else:
                results["failed"] += 1
        
        return results
    
    def _merge_to_single_pdf(self, html_files: List[Path], output_path: Path) -> Dict[str, Any]:
        """合并多个HTML为单个PDF"""
        # 需要PyPDF2库来合并
        try:
            import PyPDF2
        except ImportError:
            logger.error("需要安装PyPDF2来合并PDF: pip install PyPDF2")
            return {"success": 0, "failed": len(html_files), "files": []}
        
        # 先转换为单独的PDF
        temp_pdfs = []
        for html_file in html_files:
            temp_pdf = output_path / f"temp_{html_file.stem}.pdf"
            if self.convert_html_to_pdf(str(html_file), str(temp_pdf)):
                temp_pdfs.append(temp_pdf)
        
        if not temp_pdfs:
            return {"success": 0, "failed": len(html_files), "files": []}
        
        # 合并PDF
        try:
            merger = PyPDF2.PdfMerger()
            
            for pdf_file in temp_pdfs:
                merger.append(str(pdf_file))
            
            # 输出合并的PDF
            merged_pdf = output_path / f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            merger.write(str(merged_pdf))
            merger.close()
            
            # 清理临时文件
            for pdf_file in temp_pdfs:
                pdf_file.unlink()
            
            logger.info(f"✅ 成功合并 {len(temp_pdfs)} 个PDF文件: {merged_pdf}")
            
            return {
                "success": len(temp_pdfs),
                "failed": len(html_files) - len(temp_pdfs),
                "files": [str(merged_pdf)]
            }
        except Exception as e:
            logger.error(f"合并PDF失败: {str(e)}")
            return {"success": 0, "failed": len(html_files), "files": []}


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="HTML转PDF工具")
    parser.add_argument("input", help="输入HTML文件或目录路径")
    parser.add_argument("-o", "--output", help="输出PDF文件或目录路径")
    parser.add_argument("-m", "--method", 
                       choices=["pdfkit", "weasyprint", "playwright", "auto"],
                       default="auto",
                       help="转换方法")
    parser.add_argument("-p", "--pattern", default="*.html", 
                       help="文件匹配模式（用于目录转换）")
    parser.add_argument("--merge", action="store_true",
                       help="合并多个HTML为单个PDF")
    parser.add_argument("--ppt", action="store_true",
                       help="PPT模式（16:9比例）")
    parser.add_argument("--landscape", action="store_true",
                       help="横向打印")
    
    args = parser.parse_args()
    
    # 配置选项
    options = {}
    if args.ppt:
        options['ppt_mode'] = True
    
    pdf_options = {}
    if args.landscape:
        pdf_options['orientation'] = 'Landscape'
    
    if pdf_options:
        options['pdf_options'] = pdf_options
    
    # 创建转换器
    converter = HtmlToPdfConverter(method=args.method, options=options)
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        # 单文件转换
        success = converter.convert_html_to_pdf(str(input_path), args.output)
        if success:
            print(f"✅ 转换成功: {args.output or input_path.with_suffix('.pdf')}")
        else:
            print("❌ 转换失败")
            sys.exit(1)
    elif input_path.is_dir():
        # 目录批量转换
        results = converter.convert_directory(
            str(input_path), 
            args.output,
            args.pattern,
            args.merge
        )
        
        print(f"\n转换完成:")
        print(f"  成功: {results['success']}")
        print(f"  失败: {results['failed']}")
        
        if results['files']:
            print(f"\n生成的PDF文件:")
            for pdf_file in results['files']:
                print(f"  - {pdf_file}")
    else:
        print(f"❌ 输入路径不存在: {input_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()