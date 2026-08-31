"""
报告生成服务
使用 Jinja2 模板引擎生成 Markdown、HTML 和 PDF 格式的测试报告
"""
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import io

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound


# 定义默认百分位数
_DEFAULT_PERCENTILES = [50, 95, 99]


class ReportGenerator:
    """报告生成器 - 基于 Jinja2 模板引擎"""
    
    # 可用的预定义模板
    AVAILABLE_TEMPLATES = {
        "default": "default_report.md.j2",
        "minimal": "minimal_report.md.j2",
    }
    
    def __init__(self, template_dir: Optional[str] = None):
        template_path = template_dir or str(Path(__file__).parent / "templates" / "reports")
        self.template_dir = Path(template_path)
        self._ensure_template_dir()
        
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(default_for_string=True, default=True),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # 注册自定义过滤器
        self._jinja_env.filters['format_pct'] = self._filter_format_pct
    
    def _ensure_template_dir(self):
        """确保模板目录存在"""
        self.template_dir.mkdir(parents=True, exist_ok=True)
    
    # ---- 自定义 Jinja2 过滤器 ----
    
    @staticmethod
    def _filter_format_pct(value: float, decimals: int = 1) -> str:
        """格式化为百分比字符串"""
        return f"{value:.{decimals}f}%"
    
    # ---- 公共方法 ----
    
    def list_templates(self) -> List[str]:
        """列出所有可用的模板名称"""
        return list(self.AVAILABLE_TEMPLATES.keys())
    
    def generate_markdown(
        self,
        data: Dict[str, Any],
        template_name: str = "default",
    ) -> str:
        """
        使用 Jinja2 模板生成 Markdown 格式报告
        
        Args:
            data: 原始数据字典，包含 summary, results, model_stats 等
            template_name: 模板名称（default / minimal 或自定义文件名）
            
        Returns:
            Markdown 格式的报告字符串
        """
        # 1. 预处理数据，计算衍生指标
        context = self._build_template_context(data)
        
        # 2. 确定模板文件
        template_file = self.AVAILABLE_TEMPLATES.get(template_name, template_name)
        
        try:
            template = self._jinja_env.get_template(template_file)
            return template.render(**context)
        except TemplateNotFound:
            # 回退到默认模板
            template = self._jinja_env.get_template(self.AVAILABLE_TEMPLATES["default"])
            return template.render(**context)
    
    def _build_template_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建模板渲染上下文
        
        从原始数据计算所有模板变量，补全缺失字段
        """
        summary = data.get("summary", {})
        model_stats = data.get("model_stats", [])
        results = data.get("results", [])
        
        # 基础统计
        total = summary.get("total", len(results))
        success = summary.get("success", sum(1 for r in results if r.get("success")))
        success_rate = (success / total * 100) if total > 0 else 0
        
        # 收集TTFT和TPS值（用于百分位数计算）
        ttft_values = sorted(
            [r.get("ttft_seconds", 0) for r in results if r.get("success")],
        )
        tps_values = sorted(
            [r.get("tokens_per_second", 0) for r in results if r.get("success")],
        )
        
        # 计算百分位数
        ttft_percentiles = {}
        tps_percentiles = {}
        if ttft_values:
            ttft_percentiles = {
                f"p{p}": self._percentile(ttft_values, p) for p in _DEFAULT_PERCENTILES
            }
        if tps_values:
            tps_percentiles = {
                f"p{p}": self._percentile(tps_values, p) for p in _DEFAULT_PERCENTILES
            }
        
        # 性能亮点自动检测
        top_performers = []
        if model_stats:
            sorted_tps = sorted(model_stats, key=lambda x: x.get("avg_tps", 0), reverse=True)
            sorted_ttft = sorted(model_stats, key=lambda x: x.get("avg_ttft", float("inf")))
            if sorted_tps:
                top_performers.append({
                    "category": "最高吞吐量",
                    "model_name": sorted_tps[0].get("model_name", "Unknown"),
                    "value": f"{sorted_tps[0].get('avg_tps', 0):.2f} tokens/s",
                })
            if sorted_ttft:
                top_performers.append({
                    "category": "最快首Token",
                    "model_name": sorted_ttft[0].get("model_name", "Unknown"),
                    "value": f"{sorted_ttft[0].get('avg_ttft', 0):.3f}s",
                })
        
        # 失败详情
        failures = [
            r for r in results
            if not r.get("success") and r.get("error_message")
        ]
        
        # 模型排名表排序（按 avg_tps 降序）
        sorted_model_stats = sorted(
            model_stats,
            key=lambda x: x.get("avg_tps", 0),
            reverse=True,
        )
        
        # 构建上下文
        context = {
            # 基本标识
            "title": data.get("title", "模型速度测试报告"),
            "version": data.get("version", "2.0"),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            
            # 汇总数据
            "summary": summary,
            "test_case_name": data.get("test_case_name", summary.get("test_case_name", "N/A")),
            "folder_name": data.get("folder_name", summary.get("folder_name", "")),
            "success_rate": success_rate,
            
            # 模型统计
            "model_stats": sorted_model_stats,
            "top_performers": top_performers if top_performers else None,
            
            # 详细结果
            "results": results,
            "failures": failures if failures else None,
            
            # 百分位数
            "ttft_percentiles": ttft_percentiles,
            "tps_percentiles": tps_percentiles,
            
            # 可选字段
            "ttft_analysis": data.get("ttft_analysis"),
            "tps_analysis": data.get("tps_analysis"),
            "charts": data.get("charts"),
            "recommendations": data.get("recommendations"),
        }
        
        # 补全 summary 中可能缺失的字段
        summary.setdefault("group_id", "N/A")
        summary.setdefault("start_time", "N/A")
        summary.setdefault("total_tokens", 0)
        
        return context
    
    @staticmethod
    def _percentile(sorted_values: List[float], p: int) -> float:
        """计算百分位数（线性插值法）"""
        if not sorted_values:
            return 0.0
        n = len(sorted_values)
        rank = (p / 100.0) * (n - 1)
        lower = int(rank)
        upper = min(lower + 1, n - 1)
        weight = rank - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    
    # ---- HTML 生成 ----
    
    def generate_html(self, markdown_content: str) -> str:
        """
        Markdown 转 HTML（保留原有简单解析器，兼容 markdown 库）
        
        Args:
            markdown_content: Markdown 格式的报告内容
            
        Returns:
            HTML 片段
        """
        # 优先使用 markdown 库
        try:
            import markdown as md_lib
            return md_lib.markdown(markdown_content, extensions=["tables", "fenced_code"])
        except ImportError:
            pass
        
        # 回退到简单解析器
        return self._simple_md_to_html(markdown_content)
    
    def _simple_md_to_html(self, md: str) -> str:
        """简单的 Markdown → HTML 转换器"""
        html = md
        
        # 标题处理
        html = html.replace("# ", "<h1>")
        html = html.replace("\n## ", "</h1>\n<h2>")
        html = html.replace("\n### ", "</h2>\n<h3>")
        
        lines = html.split("\n")
        processed_lines = []
        for line in lines:
            if line.startswith("<h1>") and not line.endswith("</h1>"):
                processed_lines.append(line)
            elif line.startswith("<h2>") and not line.endswith("</h2>"):
                processed_lines.append(line + "</h2>")
            elif line.startswith("<h3>") and not line.endswith("</h3>"):
                processed_lines.append(line + "</h3>")
            elif line.startswith("---"):
                processed_lines.append("<hr/>")
            else:
                processed_lines.append(line)
        
        html = "\n".join(processed_lines)
        
        # 粗体处理（配对替换）
        parts = html.split("**")
        for i in range(1, len(parts) - 1, 2):
            parts[i] = f"<strong>{parts[i]}</strong>"
        html = "".join(parts)
        
        # 列表处理
        html_lines = html.split("\n")
        in_list = False
        new_lines = []
        for line in html_lines:
            stripped = line.strip()
            if stripped.startswith("- "):
                if not in_list:
                    in_list = True
                    new_lines.append("<ul>")
                new_lines.append(f"  <li>{stripped[2:]}</li>")
            else:
                if in_list:
                    in_list = False
                    new_lines.append("</ul>")
                new_lines.append(line)
        if in_list:
            new_lines.append("</ul>")
        
        html = "\n".join(new_lines)
        
        # 表格处理
        lines = html.split("\n")
        in_table = False
        new_lines = []
        header_processed = False
        for line in lines:
            if line.startswith("|") and "---" not in line:
                if not in_table:
                    in_table = True
                    new_lines.append('<table class="report-table">')
                    header_processed = False
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if not header_processed:
                    new_lines.append("<thead><tr>")
                    for cell in cells:
                        new_lines.append(f"<th>{cell}</th>")
                    new_lines.append("</tr></thead><tbody>")
                    header_processed = True
                elif cells and any(cells):
                    new_lines.append("<tr>")
                    for cell in cells:
                        if cell in ("✓", "✗"):
                            css_class = "success" if cell == "✓" else "error"
                            cell = f'<span class="status-icon {css_class}">{cell}</span>'
                        new_lines.append(f"<td>{cell}</td>")
                    new_lines.append("</tr>")
            else:
                if in_table:
                    in_table = False
                    if header_processed:
                        new_lines.append("</tbody>")
                    new_lines.append("</table>")
                new_lines.append(line)
        
        if in_table:
            if header_processed:
                new_lines.append("</tbody>")
            new_lines.append("</table>")
        
        return "\n".join(new_lines)
    
    def generate_full_html(
        self,
        markdown_content: str,
        title: str = "模型速度测试报告",
    ) -> str:
        """
        生成完整的 HTML 页面，包含样式
        
        Args:
            markdown_content: Markdown 格式的报告内容
            title: 页面标题
            
        Returns:
            完整的 HTML 页面
        """
        body_html = self.generate_html(markdown_content)
        generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return _generate_full_html_template(title, generated_at, body_html)
    
    # ---- PDF 生成 ----
    
    def generate_pdf(
        self,
        group_id: str,
        template_name: str = "default",
    ) -> bytes:
        """
        生成 PDF 报告
        
        Args:
            group_id: 测试组 ID
            template_name: 模板名称
            
        Returns:
            PDF 文件的字节数据
        """
        # 获取数据
        summary, results, formatted_stats = self._fetch_group_data(group_id)
        
        # 生成 Markdown
        md_content = self.generate_markdown(
            {
                "summary": summary,
                "results": results,
                "model_stats": formatted_stats,
            },
            template_name=template_name,
        )
        
        # 生成完整 HTML
        html_content = self.generate_full_html(md_content)
        
        # HTML → PDF
        try:
            from weasyprint import HTML
            pdf_buffer = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            return pdf_buffer.getvalue()
        except ImportError:
            raise ImportError(
                "weasyprint 未安装。请运行: pip install weasyprint>=60.0\n"
                "或者查看 README 了解如何安装系统依赖。"
            )
    
    # ---- 数据获取辅助 ----
    
    def _fetch_group_data(self, group_id: str) -> Tuple[Dict, List, List]:
        """
        从数据库获取测试组数据
        
        Returns:
            (summary, results, formatted_stats)
        """
        try:
            from ..src.database import get_database
            db = get_database()
            
            summary_data = db.get_group_summary(group_id)
            if not summary_data:
                raise ValueError(f"测试组 {group_id} 不存在")
            
            group_info = summary_data.get("group", {})
            model_stats = summary_data.get("model_stats", [])
            results = db.get_results(group_id)
            
            # 计算统计数据
            total = len(results)
            success = sum(1 for r in results if r.get("success"))
            
            ttft_vals = [r.get("ttft_seconds", 0) for r in results if r.get("ttft_seconds")]
            tps_vals = [r.get("tokens_per_second", 0) for r in results if r.get("tokens_per_second")]
            token_vals = [r.get("output_tokens", 0) for r in results if r.get("output_tokens")]
            
            summary = {
                "group_id": group_id,
                "start_time": group_info.get("start_time", "N/A"),
                "total": total,
                "success": success,
                "avg_ttft": sum(ttft_vals) / len(ttft_vals) if ttft_vals else 0,
                "min_ttft": min(ttft_vals) if ttft_vals else 0,
                "max_ttft": max(ttft_vals) if ttft_vals else 0,
                "avg_tps": sum(tps_vals) / len(tps_vals) if tps_vals else 0,
                "peak_tps": max(tps_vals) if tps_vals else 0,
                "avg_tokens": sum(token_vals) / len(token_vals) if token_vals else 0,
                "total_tokens": sum(token_vals),
            }
            
            # 格式化 model_stats
            formatted_stats = []
            for stat in model_stats:
                total_count = stat.get("total", 0)
                formatted_stats.append({
                    "model_name": stat.get("model_name", "Unknown"),
                    "count": total_count,
                    "success_count": stat.get("success_count", 0),
                    "avg_ttft": stat.get("avg_ttft", 0),
                    "avg_tps": stat.get("avg_tokens_per_second", 0),
                    "avg_tokens": (
                        stat.get("total_output_tokens", 0) / total_count
                        if total_count > 0 else 0
                    ),
                })
            
            return summary, results, formatted_stats
            
        except ImportError:
            # 数据库模块不可用时的回退
            return (
                {
                    "group_id": group_id,
                    "start_time": datetime.now().isoformat(),
                    "total": 0,
                    "success": 0,
                    "avg_ttft": 0,
                    "avg_tps": 0,
                    "avg_tokens": 0,
                    "total_tokens": 0,
                },
                [],
                [],
            )
    
    def _fetch_markdown_data(self, group_id: str) -> str:
        """获取某个组的 Markdown 报告数据"""
        summary, results, formatted_stats = self._fetch_group_data(group_id)
        return self.generate_markdown({
            "summary": summary,
            "results": results,
            "model_stats": formatted_stats,
        })
    
    def _fetch_html_data(self, group_id: str) -> str:
        """获取某个组的完整 HTML 报告数据"""
        md = self._fetch_markdown_data(group_id)
        return self.generate_full_html(md)


# ---- 便捷函数 ----

def generate_report(
    group_id: str,
    format: str = "pdf",
    template_name: str = "default",
) -> bytes:
    """
    快速生成报告的便捷函数
    
    Args:
        group_id: 测试组 ID
        format: 报告格式 ('pdf', 'html', 'markdown')
        template_name: 模板名称
        
    Returns:
        报告内容的字节数据
    """
    generator = ReportGenerator()
    
    if format == "pdf":
        return generator.generate_pdf(group_id, template_name=template_name)
    elif format == "html":
        return generator._fetch_html_data(group_id).encode("utf-8")
    elif format == "markdown":
        return generator._fetch_markdown_data(group_id).encode("utf-8")
    else:
        raise ValueError(f"不支持的格式: {format}")


# ---- 内部 HTML 模板辅助函数 ----


def _generate_full_html_template(title: str, generated_at: str, body_html: str) -> str:
    """
    生成完整的 HTML 页面模板（PDF 打印优化版）
    
    特性：
    - A4 纸张尺寸，2cm 页边距
    - 封面页（页面居中、无页眉页脚）
    - 运行页眉（标题 + 报告类型）
    - 运行页脚（页码 + 生成时间）
    - 中文排版字体栈（PingFang SC / Microsoft YaHei / Noto Sans SC）
    - 统计卡片组件
    - 分页控制（page-break-before / page-break-inside）
    - 打印友好的表格样式（深色表头、斑马纹）
    """
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        /* ========== 打印页面设置 ========== */
        @page {{
            size: A4;
            margin: 2cm 1.8cm 2.5cm 1.8cm;
            @top-center {{
                content: element(pageHeader);
            }}
            @bottom-center {{
                content: element(pageFooter);
            }}
        }}
        
        @page cover {{
            @top-center {{
                content: none;
            }}
            @bottom-center {{
                content: none;
            }}
        }}
        
        /* ========== 基础重置 ========== */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Segoe UI", sans-serif;
            font-size: 12pt;
            line-height: 1.8;
            color: #2c3e50;
            background: #fff;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        
        /* ========== 封面页 ========== */
        .cover-page {{
            page: cover;
            page-break-after: always;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            text-align: center;
            padding: 40px;
        }}
        
        .cover-page .logo {{
            font-size: 56pt;
            margin-bottom: 24px;
        }}
        
        .cover-page h1 {{
            font-size: 32pt;
            color: #1a1a2e;
            margin-bottom: 16px;
            font-weight: 700;
            letter-spacing: 2px;
            border: none;
            padding: 0;
        }}
        
        .cover-page .subtitle {{
            font-size: 16pt;
            color: #7f8c8d;
            margin-bottom: 48px;
            font-weight: 300;
        }}
        
        .cover-page .divider {{
            width: 120px;
            height: 3px;
            background: linear-gradient(90deg, #3498db, #9b59b6);
            margin: 32px auto;
            border-radius: 2px;
        }}
        
        .cover-page .meta-line {{
            font-size: 11pt;
            color: #95a5a6;
            margin: 8px 0;
        }}
        
        /* ========== 运行页眉页脚 ========== */
        .page-header {{
            position: running(pageHeader);
            font-size: 9pt;
            color: #95a5a6;
            text-align: center;
            padding-bottom: 8px;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        .page-footer {{
            position: running(pageFooter);
            font-size: 9pt;
            color: #95a5a6;
            text-align: center;
            padding-top: 8px;
            border-top: 1px solid #ecf0f1;
        }}
        
        .page-footer .page-number::after {{
            content: counter(page);
        }}
        
        /* ========== 内容容器 ========== */
        .container {{
            max-width: 100%;
        }}
        
        /* ========== 标题层级 ========== */
        h1 {{
            font-size: 20pt;
            color: #1a1a2e;
            margin: 20pt 0 10pt;
            padding-bottom: 6pt;
            border-bottom: 2.5px solid #3498db;
            page-break-after: avoid;
        }}
        
        h2 {{
            font-size: 15pt;
            color: #2c3e50;
            margin: 18pt 0 8pt;
            padding-left: 10pt;
            border-left: 4px solid #3498db;
            page-break-after: avoid;
        }}
        
        h3 {{
            font-size: 13pt;
            color: #34495e;
            margin: 14pt 0 6pt;
            page-break-after: avoid;
        }}
        
        /* ========== 统计卡片 ========== */
        .summary-cards {{
            display: flex;
            flex-wrap: wrap;
            gap: 10pt;
            margin: 14pt 0 20pt;
            page-break-inside: avoid;
        }}
        
        .stat-card {{
            flex: 1;
            min-width: 110pt;
            padding: 12pt 14pt;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 6pt;
            border: 1px solid #dee2e6;
            text-align: center;
        }}
        
        .stat-card .stat-label {{
            font-size: 8pt;
            color: #7f8c8d;
            margin-bottom: 3pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .stat-card .stat-value {{
            font-size: 18pt;
            font-weight: 700;
            color: #2c3e50;
        }}
        
        .stat-card .stat-unit {{
            font-size: 8pt;
            color: #95a5a6;
        }}
        
        .stat-card.highlight {{
            background: linear-gradient(135deg, #e8f4fd 0%, #d4e9f9 100%);
            border-color: #3498db;
        }}
        
        .stat-card.highlight .stat-value {{
            color: #2980b9;
        }}
        
        /* ========== 表格 ========== */
        .report-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 14pt 0;
            font-size: 9.5pt;
            page-break-inside: avoid;
        }}
        
        .report-table thead {{
            display: table-header-group;
        }}
        
        .report-table th {{
            padding: 8pt 10pt;
            text-align: left;
            background: #2c3e50;
            color: #fff;
            font-weight: 600;
            font-size: 9.5pt;
            letter-spacing: 0.3px;
        }}
        
        .report-table td {{
            padding: 7pt 10pt;
            border-bottom: 1px solid #ecf0f1;
            vertical-align: middle;
        }}
        
        .report-table tbody tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        
        .report-table tbody tr:hover {{
            background: #e8f4fd;
        }}
        
        .report-table .num-cell {{
            text-align: right;
            font-family: "SF Mono", "Consolas", "Menlo", monospace;
            font-size: 9pt;
        }}
        
        /* ========== 状态标签 ========== */
        .status-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 8pt;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}
        
        .status-badge.success {{
            background: #d5f5e3;
            color: #1e8449;
        }}
        
        .status-badge.error {{
            background: #fadbd8;
            color: #c0392b;
        }}
        
        .status-badge.warning {{
            background: #fef9e7;
            color: #b7950b;
        }}
        
        /* ========== 状态图标 ========== */
        .status-icon {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        .status-icon.success {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-icon.error {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        /* ========== 列表 ========== */
        ul {{
            margin: 10pt 0 10pt 18pt;
            list-style: none;
        }}
        
        li {{
            margin: 5pt 0;
            padding-left: 14pt;
            position: relative;
        }}
        
        li::before {{
            content: "▸";
            position: absolute;
            left: 0;
            color: #3498db;
            font-size: 8pt;
        }}
        
        /* ========== 分隔线 ========== */
        hr {{
            border: none;
            border-top: 1px solid #ecf0f1;
            margin: 20pt 0;
        }}
        
        /* ========== 提示框 ========== */
        .note-box {{
            padding: 10pt 14pt;
            background: #fef9e7;
            border-left: 4px solid #f1c40f;
            border-radius: 4px;
            margin: 14pt 0;
            font-size: 9.5pt;
            color: #7d6608;
            page-break-inside: avoid;
        }}
        
        /* ========== 分页控制 ========== */
        .page-break {{
            page-break-before: always;
        }}
        
        .no-break {{
            page-break-inside: avoid;
        }}
        
        /* ========== 脚注 ========== */
        .footer {{
            margin-top: 28pt;
            padding-top: 14pt;
            border-top: 1px solid #ecf0f1;
            color: #95a5a6;
            font-size: 9pt;
            text-align: center;
        }}
    </style>
</head>
<body>
    <!-- 运行页眉 -->
    <div class="page-header">
        {title} — 模型性能测试报告
    </div>

    <!-- 运行页脚 -->
    <div class="page-footer">
        模型速度测试系统 &nbsp;|&nbsp; 第 <span class="page-number"></span> 页 &nbsp;|&nbsp; 生成时间: {generated_at}
    </div>

    <!-- 封面页 -->
    <div class="cover-page">
        <div class="logo">&#9889;</div>
        <h1>{title}</h1>
        <div class="subtitle">模型推理性能测试报告</div>
        <div class="divider"></div>
        <p class="meta-line">报告引擎: Model Speed Test v2.0</p>
        <p class="meta-line">生成时间: {generated_at}</p>
    </div>

    <!-- 正文内容 -->
    <div class="container">
        {body_html}
        <div class="footer no-break">
            <p>— 报告结束 —</p>
        </div>
    </div>
</body>
</html>
""".format(
        title=title,
        generated_at=generated_at,
        body_html=body_html,
    )
