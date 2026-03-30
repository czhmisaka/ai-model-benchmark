# 报告生成与数据可视化能力增强 - 开发计划

## 一、功能概览

| 模块 | 功能 | 优先级 |
|------|------|--------|
| 报告导出 | PDF 报告导出 | P0 |
| 报告导出 | Excel 多 Sheet 导出 | P0 |
| 数据可视化 | 实时性能图表 | P1 |
| 数据可视化 | 报告预览模态框 | P1 |
| 报告生成 | Markdown 模板系统 | P2 |
| 数据可视化 | 图表导出 PNG | P2 |

---

## 二、PDF 报告导出功能

### 2.1 后端实现

**新增文件**: `model_speed_test/web/report_generator.py`

```python
"""
报告生成服务
"""
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import json

class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, template_dir: str = None):
        self.template_dir = template_dir or "templates/reports"
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
    
    def generate_markdown(self, data: Dict[str, Any]) -> str:
        """生成 Markdown 格式报告"""
        # 概览统计
        summary = data.get("summary", {})
        model_stats = data.get("model_stats", [])
        results = data.get("results", [])
        
        md = f"""# 模型速度测试报告

## 概览
- **测试组 ID**: {summary.get('group_id', 'N/A')}
- **测试时间**: {summary.get('start_time', 'N/A')}
- **总测试数**: {summary.get('total', 0)}
- **成功数**: {summary.get('success', 0)}
- **成功率**: {summary.get('success_rate', 0):.1f}%
- **平均 TTFT**: {summary.get('avg_ttft', 0):.3f}s
- **平均 TPS**: {summary.get('avg_tps', 0):.2f} tokens/s

## 模型排名

"""
        # 按性能排序
        for i, stat in enumerate(model_stats[:5], 1):
            md += f"""### {i}. {stat['model_name']}
- 测试次数: {stat['count']}
- 平均 TTFT: {stat['avg_ttft']:.3f}s
- 平均 TPS: {stat['avg_tps']:.2f} tokens/s
- 成功率: {stat['success_rate']:.1f}%

"""
        
        # 详细数据表
        md += """## 详细数据

| 模型 | 轮次 | TTFT | TPS | Tokens | 状态 |
|------|------|------|-----|--------|------|
"""
        for r in results:
            md += f"| {r['model_name']} | {r['round']} | {r['ttft']:.3f}s | {r['tps']:.2f} | {r['tokens']} | {'✓' if r['success'] else '✗'} |\n"
        
        return md
    
    def generate_html(self, markdown_content: str) -> str:
        """Markdown 转 HTML"""
        # 简单的 Markdown → HTML 转换
        html = markdown_content
        
        # 标题
        html = html.replace('# ', '<h1>').replace('\n', '</h1>\n', 1)
        html = html.replace('## ', '<h2>').replace('##', '</h2>\n<h2>')
        html = html.replace('### ', '<h3>').replace('###', '</h3>\n<h3>')
        
        # 粗体
        html = html.replace('**', '<strong>', 1)
        html = html.replace('**', '</strong>', 1)
        
        # 表格
        lines = html.split('\n')
        in_table = False
        new_lines = []
        
        for line in lines:
            if line.startswith('|'):
                if not in_table:
                    in_table = True
                    new_lines.append('<table class="report-table">')
                
                if '---' in line:
                    continue
                
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if all(cells):
                    new_lines.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
            else:
                if in_table:
                    in_table = False
                    new_lines.append('</table>')
                new_lines.append(line)
        
        if in_table:
            new_lines.append('</table>')
        
        return '\n'.join(new_lines)
    
    def generate_pdf(self, group_id: str) -> bytes:
        """生成 PDF 报告"""
        # 1. 获取测试数据
        from src.database import get_database
        db = get_database()
        
        results = db.get_results(group_id)
        summary = db.get_group_summary(group_id)
        
        # 2. 生成 Markdown
        md_content = self.generate_markdown({
            "summary": summary,
            "results": results
        })
        
        # 3. Markdown → HTML
        html_content = self.generate_html(md_content)
        
        # 4. HTML → PDF (使用 weasyprint)
        from weasyprint import HTML
        pdf_buffer = HTML(string=html_content).write_pdf()
        
        return pdf_buffer
```

**修改文件**: `model_speed_test/web/app.py`

```python
from .report_generator import ReportGenerator

@app.get("/api/history/{group_id}/report/pdf")
async def generate_pdf_report(group_id: str):
    """生成 PDF 格式的测试报告"""
    generator = ReportGenerator()
    
    try:
        pdf_buffer = generator.generate_pdf(group_id)
        
        return StreamingResponse(
            io.BytesIO(pdf_buffer),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=report_{group_id}.pdf"
            }
        )
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### 2.2 前端实现

**修改文件**: `model_speed_test/frontend/src/views/History.vue`

```vue
<template>
  <!-- 在每个历史项的操作区域添加导出按钮 -->
  <div class="item-actions">
    <button @click="viewCharts(item)" class="btn-chart">📊 图表</button>
    <button @click="exportPDF(item.group_id)" class="btn-export">📄 PDF</button>
    <button @click="exportExcel(item.group_id)" class="btn-export">📊 Excel</button>
    <button @click="viewDetail(item)">详情</button>
    <button @click="deleteItem(item)" class="btn-delete">删除</button>
  </div>
</template>

<script setup>
// 导出 PDF
async function exportPDF(groupId: string) {
  try {
    window.open(`/api/history/${groupId}/report/pdf`, '_blank')
    showToast('PDF 报告生成中...', 'success')
  } catch (e) {
    showToast('导出失败', 'error')
  }
}

// 导出 Excel
async function exportExcel(groupId: string) {
  try {
    window.open(`/api/history/${groupId}/report/excel`, '_blank')
    showToast('Excel 导出中...', 'success')
  } catch (e) {
    showToast('导出失败', 'error')
  }
}
</script>
```

---

## 三、Excel 多 Sheet 导出功能

### 3.1 后端实现

**新增文件**: `model_speed_test/web/excel_exporter.py`

```python
"""
Excel 报告导出
"""
import io
from typing import Dict, Any, List
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

class ExcelExporter:
    """Excel 报告导出器"""
    
    def __init__(self):
        self.header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        self.header_font = Font(bold=True, color="FFFFFF")
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
    
    def export(self, data: Dict[str, Any]) -> bytes:
        """导出多 Sheet Excel"""
        wb = Workbook()
        
        # 移除默认 sheet
        wb.remove(wb.active)
        
        # Sheet 1: 汇总统计
        self._create_summary_sheet(wb, data.get('summary', {}))
        
        # Sheet 2: 模型对比
        self._create_model_comparison_sheet(wb, data.get('model_stats', []))
        
        # Sheet 3: 详细数据
        self._create_detail_sheet(wb, data.get('results', []))
        
        # Sheet 4: 图表数据
        self._create_chart_data_sheet(wb, data.get('chart_data', {}))
        
        # 保存到 buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def _create_summary_sheet(self, wb: Workbook, summary: Dict[str, Any]):
        """汇总统计 Sheet"""
        ws = wb.create_sheet("汇总统计")
        
        # 标题
        ws['A1'] = '模型速度测试 - 汇总统计'
        ws['A1'].font = Font(size=16, bold=True)
        ws.merge_cells('A1:D1')
        
        # 统计数据
        stats = [
            ('测试组 ID', summary.get('group_id', '')),
            ('总测试数', summary.get('total', 0)),
            ('成功数', summary.get('success', 0)),
            ('失败数', summary.get('failed', 0)),
            ('成功率', f"{summary.get('success_rate', 0):.1f}%"),
            ('平均 TTFT', f"{summary.get('avg_ttft', 0):.3f}s"),
            ('平均 TPS', f"{summary.get('avg_tps', 0):.2f} tokens/s"),
            ('平均 Tokens', summary.get('avg_tokens', 0)),
        ]
        
        for i, (label, value) in enumerate(stats, 3):
            ws[f'A{i}'] = label
            ws[f'B{i}'] = value
            ws[f'A{i}'].font = Font(bold=True)
        
        # 设置列宽
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 20
    
    def _create_model_comparison_sheet(self, wb: Workbook, model_stats: List[Dict]):
        """模型对比 Sheet"""
        ws = wb.create_sheet("模型对比")
        
        # 表头
        headers = ['排名', '模型名称', '测试次数', '成功数', '成功率', '平均 TTFT', '平均 TPS', '平均 Tokens']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = Alignment(horizontal='center')
            cell.border = self.border
        
        # 数据行
        for row, stat in enumerate(model_stats, 2):
            ws.cell(row=row, column=1, value=row-1)
            ws.cell(row=row, column=2, value=stat.get('model_name', ''))
            ws.cell(row=row, column=3, value=stat.get('count', 0))
            ws.cell(row=row, column=4, value=stat.get('success', 0))
            ws.cell(row=row, column=5, value=f"{stat.get('success_rate', 0):.1f}%")
            ws.cell(row=row, column=6, value=f"{stat.get('avg_ttft', 0):.3f}")
            ws.cell(row=row, column=7, value=f"{stat.get('avg_tps', 0):.2f}")
            ws.cell(row=row, column=8, value=stat.get('avg_tokens', 0))
            
            # 边框
            for col in range(1, 9):
                ws.cell(row=row, column=col).border = self.border
        
        # 设置列宽
        for col, width in enumerate([8, 20, 12, 12, 12, 15, 15, 15], 1):
            ws.column_dimensions[get_column_letter(col)].width = width
    
    def _create_detail_sheet(self, wb: Workbook, results: List[Dict]):
        """详细数据 Sheet"""
        ws = wb.create_sheet("详细数据")
        
        # 表头
        headers = ['时间戳', '模型', '测试用例', '轮次', 'TTFT(s)', 'TPS', 'Tokens', 'Think Tokens', 'Answer Tokens', '状态']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = Alignment(horizontal='center')
        
        # 数据行
        for row, r in enumerate(results, 2):
            ws.cell(row=row, column=1, value=r.get('timestamp', ''))
            ws.cell(row=row, column=2, value=r.get('model_name', ''))
            ws.cell(row=row, column=3, value=r.get('case_name', ''))
            ws.cell(row=row, column=4, value=r.get('round', 0))
            ws.cell(row=row, column=5, value=r.get('ttft_seconds', 0))
            ws.cell(row=row, column=6, value=r.get('tokens_per_second', 0))
            ws.cell(row=row, column=7, value=r.get('output_tokens', 0))
            ws.cell(row=row, column=8, value=r.get('think_tokens', 0))
            ws.cell(row=row, column=9, value=r.get('answer_tokens', 0))
            ws.cell(row=row, column=10, value='成功' if r.get('success') else '失败')
            
            # 状态颜色
            status_cell = ws.cell(row=row, column=10)
            if r.get('success'):
                status_cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            else:
                status_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    
    def _create_chart_data_sheet(self, wb: Workbook, chart_data: Dict):
        """图表数据 Sheet"""
        ws = wb.create_sheet("图表数据")
        
        # TTFT 趋势
        ws['A1'] = 'TTFT 趋势'
        ws['A1'].font = Font(bold=True)
        
        headers = ['轮次'] + list(chart_data.get('models', {}).keys())
        for col, header in enumerate(headers, 1):
            ws.cell(row=2, column=col, value=header)
            ws.cell(row=2, column=col).font = Font(bold=True)
        
        trend_data = chart_data.get('ttft_trend', {})
        for row_idx, (round_num, values) in enumerate(trend_data.items(), 3):
            ws.cell(row=row_idx, column=1, value=round_num)
            for col_idx, model in enumerate(headers[1:], 2):
                ws.cell(row=row_idx, column=col_idx, value=values.get(model, 0))
```

**修改文件**: `model_speed_test/web/app.py`

```python
from .excel_exporter import ExcelExporter

@app.get("/api/history/{group_id}/report/excel")
async def generate_excel_report(group_id: str):
    """生成 Excel 格式的测试报告"""
    exporter = ExcelExporter()
    
    try:
        # 获取数据
        db = get_database()
        results = db.get_results(group_id)
        summary = db.get_group_summary(group_id)
        model_stats = db.get_model_stats(group_id)
        
        # 导出 Excel
        excel_buffer = exporter.export({
            "summary": summary,
            "results": results,
            "model_stats": model_stats,
            "chart_data": {}  # TODO: 生成图表数据
        })
        
        return StreamingResponse(
            io.BytesIO(excel_buffer),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=report_{group_id}.xlsx"
            }
        )
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## 四、实时性能图表

### 4.1 前端实现

**修改文件**: `model_speed_test/frontend/src/views/TestRun.vue`

```vue
<template>
  <!-- 在测试运行时显示实时图表 -->
  <div class="realtime-chart-section" v-if="testRunning || results.length > 0">
    <div class="chart-tabs">
      <button 
        v-for="tab in chartTabs" 
        :key="tab.id"
        :class="{ active: activeChartTab === tab.id }"
        @click="activeChartTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>
    
    <!-- TTFT 实时柱状图 -->
    <div v-show="activeChartTab === 'ttft'" ref="ttftChartRef" class="chart-container"></div>
    
    <!-- TPS 趋势折线图 -->
    <div v-show="activeChartTab === 'tps'" ref="tpsChartRef" class="chart-container"></div>
    
    <!-- 成功率仪表盘 -->
    <div v-show="activeChartTab === 'success'" ref="successChartRef" class="chart-container gauge-container"></div>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { ref, watch, onMounted } from 'vue'

const ttftChartRef = ref<HTMLElement | null>(null)
const tpsChartRef = ref<HTMLElement | null>(null)
const successChartRef = ref<HTMLElement | null>(null)

let ttftChart: echarts.ECharts | null = null
let tpsChart: echarts.ECharts | null = null
let successChart: echarts.ECharts | null = null

const chartTabs = [
  { id: 'ttft', label: '首Token时间' },
  { id: 'tps', label: '生成速度' },
  { id: 'success', label: '成功率' }
]

const activeChartTab = ref('ttft')

// 初始化图表
function initCharts() {
  // TTFT 柱状图
  if (ttftChartRef.value) {
    ttftChart = echarts.init(ttftChartRef.value)
    ttftChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value', name: 'TTFT (ms)' },
      series: [{
        type: 'bar',
        data: [],
        itemStyle: { color: '#FF4500' }
      }]
    })
  }
  
  // TPS 折线图
  if (tpsChartRef.value) {
    tpsChart = echarts.init(tpsChartRef.value)
    tpsChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value', name: 'TPS' },
      series: [{
        type: 'line',
        data: [],
        smooth: true,
        lineStyle: { color: '#48DBFB' }
      }]
    })
  }
  
  // 成功率仪表盘
  if (successChartRef.value) {
    successChart = echarts.init(successChartRef.value)
    successChart.setOption({
      series: [{
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.6, '#EF4444'],
              [0.8, '#F59E0B'],
              [1, '#22C55E']
            ]
          }
        },
        pointer: { length: '60%' },
        detail: { formatter: '{value}%', fontSize: 24 },
        data: [{ value: 0 }]
      }]
    })
  }
}

// 更新图表数据
function updateCharts(data: any) {
  // 更新 TTFT
  if (ttftChart) {
    const xData = ttftChart.getOption().xAxis[0].data || []
    const yData = ttftChart.getOption().series[0].data || []
    
    xData.push(`R${xData.length + 1}`)
    yData.push((data.ttft_seconds || 0) * 1000)
    
    ttftChart.setOption({
      xAxis: { data: xData },
      series: [{ data: yData }]
    })
  }
  
  // 更新 TPS
  if (tpsChart) {
    const xData = tpsChart.getOption().xAxis[0].data || []
    const yData = tpsChart.getOption().series[0].data || []
    
    xData.push(`R${xData.length + 1}`)
    yData.push(data.tokens_per_second || 0)
    
    tpsChart.setOption({
      xAxis: { data: xData },
      series: [{ data: yData }]
    })
  }
  
  // 更新成功率
  if (successChart) {
    const successCount = results.value.filter((r: any) => r.success).length
    const rate = results.value.length > 0 ? (successCount / results.value.length) * 100 : 0
    
    successChart.setOption({
      series: [{ data: [{ value: rate.toFixed(1) }] }]
    })
  }
}

// SSE 事件处理
function handleEvent(event: any) {
  if (event.type === 'complete') {
    updateCharts(event.data)
  }
}

// 监听测试结果变化
watch(results, () => {
  if (results.value.length > 0) {
    updateCharts(results.value[results.value.length - 1])
  }
})

onMounted(() => {
  initCharts()
})
</script>
```

---

## 五、报告预览模态框

### 5.1 新增组件

**新增文件**: `model_speed_test/frontend/src/components/ReportPreviewModal.vue`

```vue
<template>
  <div class="modal-overlay" v-if="visible" @click.self="close">
    <div class="report-preview-modal">
      <div class="modal-header">
        <h3>📊 报告预览</h3>
        <div class="header-actions">
          <button @click="exportPDF" class="btn-action">📄 PDF</button>
          <button @click="exportMarkdown" class="btn-action">📝 Markdown</button>
          <button @click="exportExcel" class="btn-action">📊 Excel</button>
          <button @click="copyLink" class="btn-action">🔗 分享</button>
          <button @click="close" class="btn-close">✕</button>
        </div>
      </div>
      
      <div class="modal-body">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading">
          <div class="spinner"></div>
          <span>加载报告中...</span>
        </div>
        
        <!-- 报告内容 -->
        <div v-else class="report-content markdown-body" v-html="renderedContent"></div>
      </div>
      
      <!-- 统计概览 -->
      <div class="modal-footer" v-if="!loading">
        <div class="stat-item">
          <span class="stat-label">总测试数</span>
          <span class="stat-value">{{ stats.total }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">成功率</span>
          <span class="stat-value">{{ stats.successRate }}%</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">平均 TTFT</span>
          <span class="stat-value">{{ stats.avgTtft }}ms</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">平均 TPS</span>
          <span class="stat-value">{{ stats.avgTps }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  groupId: string
}>()

const emit = defineEmits(['close', 'export'])

const loading = ref(false)
const renderedContent = ref('')
const stats = ref({
  total: 0,
  successRate: 0,
  avgTtft: 0,
  avgTps: 0
})

// 加载报告内容
async function loadReport() {
  if (!props.groupId) return
  
  loading.value = true
  
  try {
    // 获取 Markdown 内容
    const res = await fetch(`/api/history/${props.groupId}/report/markdown`)
    const data = await res.json()
    
    if (data.success) {
      renderedContent.value = markdownToHtml(data.content)
      
      // 解析统计数据
      stats.value = {
        total: data.stats.total || 0,
        successRate: data.stats.successRate || 0,
        avgTtft: data.stats.avgTtft || 0,
        avgTps: data.stats.avgTps || 0
      }
    }
  } catch (e) {
    console.error('加载报告失败:', e)
  } finally {
    loading.value = false
  }
}

// Markdown 转 HTML
function markdownToHtml(md: string): string {
  // 简单的 Markdown 渲染
  let html = md
  
  // 标题
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  
  // 粗体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  
  // 表格
  const tableRegex = /\|(.+)\|[\r\n]+\|[\s|-]+\|[\r\n]+((?:\|.+\|[\r\n]*)+)/g
  html = html.replace(tableRegex, (match, header, body) => {
    const headers = header.split('|').filter(c => c.trim())
    const rows = body.trim().split('\n').map(row => 
      row.split('|').filter(c => c.trim())
    )
    
    let table = '<table class="report-table"><thead><tr>'
    headers.forEach(h => table += `<th>${h.trim()}</th>`)
    table += '</tr></thead><tbody>'
    rows.forEach(row => {
      table += '<tr>'
      row.forEach(cell => table += `<td>${cell.trim()}</td>`)
      table += '</tr>'
    })
    table += '</tbody></table>'
    
    return table
  })
  
  // 列表
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
  
  return html
}

// 导出操作
function exportPDF() {
  window.open(`/api/history/${props.groupId}/report/pdf`, '_blank')
}

function exportMarkdown() {
  const link = document.createElement('a')
  link.href = `/api/history/${props.groupId}/report/markdown`
  link.download = `report_${props.groupId}.md`
  link.click()
}

function exportExcel() {
  window.open(`/api/history/${props.groupId}/report/excel`, '_blank')
}

function copyLink() {
  const url = `${window.location.origin}/report/${props.groupId}`
  navigator.clipboard.writeText(url)
  alert('分享链接已复制到剪贴板')
}

function close() {
  emit('close')
}

// 监听显示状态
watch(() => props.visible, (val) => {
  if (val) {
    loadReport()
  }
})
</script>

<style lang="scss" scoped>
.report-preview-modal {
  width: 900px;
  max-width: 95vw;
  max-height: 90vh;
  background: white;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--gray-200);
  
  h3 {
    font-size: 18px;
    font-weight: 600;
  }
}

.header-actions {
  display: flex;
  gap: 8px;
}

.btn-action {
  padding: 6px 12px;
  border: 1px solid var(--gray-300);
  background: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--gray-100);
  border-radius: 6px;
  cursor: pointer;
  
  &:hover {
    background: var(--gray-200);
  }
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 300px;
  color: var(--gray-500);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--gray-200);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.report-content {
  line-height: 1.6;
  
  :deep(h1) {
    font-size: 24px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--gray-300);
  }
  
  :deep(h2) {
    font-size: 18px;
    margin: 20px 0 12px;
    color: var(--gray-800);
  }
  
  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    
    th, td {
      padding: 10px 12px;
      border: 1px solid var(--gray-200);
      text-align: left;
    }
    
    th {
      background: var(--gray-100);
      font-weight: 600;
    }
    
    tr:nth-child(even) {
      background: var(--gray-50);
    }
  }
}

.modal-footer {
  display: flex;
  gap: 24px;
  padding: 16px 20px;
  border-top: 1px solid var(--gray-200);
  background: var(--gray-50);
}

.stat-item {
  text-align: center;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--primary);
}
</style>
```

### 5.2 后端接口

**修改文件**: `model_speed_test/web/app.py`

```python
from .report_generator import ReportGenerator

@app.get("/api/history/{group_id}/report/markdown")
async def get_markdown_report(group_id: str):
    """获取 Markdown 格式的报告内容"""
    generator = ReportGenerator()
    
    try:
        # 获取数据
        db = get_database()
        results = db.get_results(group_id)
        summary = db.get_group_summary(group_id)
        
        # 生成 Markdown
        content = generator.generate_markdown({
            "summary": summary,
            "results": results
        })
        
        # 计算统计
        success_count = sum(1 for r in results if r.get('success'))
        avg_ttft = sum(r.get('ttft_seconds', 0) for r in results) / len(results) if results else 0
        avg_tps = sum(r.get('tokens_per_second', 0) for r in results) / len(results) if results else 0
        
        return {
            "success": True,
            "content": content,
            "stats": {
                "total": len(results),
                "successRate": (success_count / len(results) * 100) if results else 0,
                "avgTtft": round(avg_ttft * 1000, 2),  # 转为 ms
                "avgTps": round(avg_tps, 2)
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## 六、图表导出 PNG 功能

### 6.1 前端实现

**修改文件**: `model_speed_test/frontend/src/views/History.vue`

```vue
<template>
  <div class="charts-section" v-if="selectedGroup">
    <!-- 图表卡片头部 -->
    <div class="chart-card" v-for="chart in charts" :key="chart.id">
      <div class="chart-header">
        <h3 class="chart-title">{{ chart.title }}</h3>
        <button @click="exportChartPng(chart.id)" class="btn-export-img">
          📷 导出图片
        </button>
      </div>
      <div :ref="el => chartRefs[chart.id] = el" class="chart-container"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
const chartRefs = reactive<Record<string, HTMLElement | null>>({})

// 导出图表为 PNG
function exportChartPng(chartId: string) {
  const chartContainer = chartRefs[chartId]
  if (!chartContainer) return
  
  let chart: echarts.ECharts | null = null
  
  switch (chartId) {
    case 'trend':
      chart = trendChart
      break
    case 'compare':
      chart = compareChart
      break
    case 'dist':
      chart = distChart
      break
  }
  
  if (!chart) return
  
  // 获取图片 URL
  const url = chart.getDataURL({
    type: 'png',
    pixelRatio: 2,  // 2倍清晰度
    backgroundColor: '#ffffff'
  })
  
  // 下载图片
  const link = document.createElement('a')
  link.href = url
  link.download = `chart_${chartId}_${Date.now()}.png`
  link.click()
}
</script>
```

---

## 七、Markdown 模板系统

### 7.1 目录结构

```
model_speed_test/
├── templates/
│   └── reports/
│       ├── __init__.py
│       ├── base.html              # 基础 HTML 模板
│       ├── section_summary.html    # 汇总部分
│       ├── section_metrics.html    # 指标部分
│       ├── section_charts.html     # 图表部分
│       └── section_table.html      # 表格部分
```

### 7.2 模板文件

**templates/reports/base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            padding: 40px;
        }
        
        .report-header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #FF4500;
        }
        
        .report-header h1 {
            font-size: 28px;
            color: #1a1a1a;
            margin-bottom: 10px;
        }
        
        .report-header .meta {
            color: #666;
            font-size: 14px;
        }
        
        .section {
            margin-bottom: 30px;
        }
        
        .section-title {
            font-size: 18px;
            color: #FF4500;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 28px;
            font-weight: 600;
            color: #FF4500;
        }
        
        .stat-label {
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        
        th {
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .success {
            color: #22C55E;
        }
        
        .failure {
            color: #EF4444;
        }
    </style>
</head>
<body>
    <div class="report-header">
        <h1>{{ title }}</h1>
        <div class="meta">
            <span>测试组 ID: {{ group_id }}</span> |
            <span>生成时间: {{ generated_at }}</span>
        </div>
    </div>
    
    {% block content %}{% endblock %}
</body>
</html>
```

**templates/reports/section_summary.html**

```html
{% extends "base.html" %}

{% block content %}
<div class="section">
    <h2 class="section-title">📊 测试概览</h2>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">总测试数</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ stats.success_rate }}%</div>
            <div class="stat-label">成功率</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ stats.avg_ttft }}ms</div>
            <div class="stat-label">平均 TTFT</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ stats.avg_tps }}</div>
            <div class="stat-label">平均 TPS</div>
        </div>
    </div>
</div>

<div class="section">
    <h2 class="section-title">🏆 模型排名</h2>
    
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>模型</th>
                <th>测试次数</th>
                <th>成功率</th>
                <th>平均 TTFT</th>
                <th>平均 TPS</th>
            </tr>
        </thead>
        <tbody>
            {% for model in model_ranking %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>{{ model.name }}</td>
                <td>{{ model.count }}</td>
                <td class="{{ 'success' if model.success_rate >= 90 else '' }}">
                    {{ model.success_rate }}%
                </td>
                <td>{{ model.avg_ttft }}ms</td>
                <td>{{ model.avg_tps }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

### 7.3 模板服务

**新增文件**: `model_speed_test/web/template_service.py`

```python
"""
报告模板服务
"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from typing import Dict, Any

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "reports"

class TemplateService:
    """模板服务"""
    
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    def render_report(self, data: Dict[str, Any], template_name: str = 'section_summary.html') -> str:
        """渲染报告模板"""
        template = self.env.get_template(template_name)
        
        return template.render(
            title=data.get('title', '模型速度测试报告'),
            group_id=data.get('group_id', ''),
            generated_at=data.get('generated_at', ''),
            stats=data.get('stats', {}),
            model_ranking=data.get('model_ranking', []),
            **data
        )
    
    def render_to_pdf(self, data: Dict[str, Any], output_path: str):
        """渲染并生成 PDF"""
        from weasyprint import HTML
        
        html_content = self.render_report(data)
        HTML(string=html_content).write_pdf(output_path)
```

---

## 八、依赖更新

### 8.1 Python 依赖

**修改文件**: `model_speed_test/requirements.txt`

```txt
# 新增依赖
weasyprint>=60.0
openpyxl>=3.1.0
jinja2>=3.1.0
pandas>=2.0.0
```

### 8.2 前端依赖

**修改文件**: `model_speed_test/frontend/package.json`

```json
{
  "dependencies": {
    // 现有依赖...
  },
  "scripts": {
    // 现有脚本...
  }
}
```

---

## 九、API 端点汇总

| 端点 | 方法 | 功能 | 返回格式 |
|------|------|------|----------|
| `/api/history/{id}/report/pdf` | GET | PDF 报告 | application/pdf |
| `/api/history/{id}/report/excel` | GET | Excel 报告 | .xlsx |
| `/api/history/{id}/report/markdown` | GET | Markdown 内容 | JSON |
| `/api/history/{id}/report/preview` | GET | HTML 预览 | text/html |

---

## 十、文件清单

### 新增文件

- `model_speed_test/web/report_generator.py` - 报告生成服务
- `model_speed_test/web/excel_exporter.py` - Excel 导出服务
- `model_speed_test/web/template_service.py` - 模板服务
- `model_speed_test/frontend/src/components/ReportPreviewModal.vue` - 报告预览组件
- `model_speed_test/templates/reports/base.html` - 基础模板
- `model_speed_test/templates/reports/section_summary.html` - 汇总部分模板
- `model_speed_test/templates/reports/section_metrics.html` - 指标部分模板
- `model_speed_test/templates/reports/section_table.html` - 表格部分模板

### 修改文件

- `model_speed_test/web/app.py` - 新增 API 端点
- `model_speed_test/frontend/src/views/History.vue` - 新增导出按钮、图表导出
- `model_speed_test/frontend/src/views/TestRun.vue` - 新增实时图表
- `model_speed_test/requirements.txt` - 新增依赖
- `model_speed_test/frontend/package.json` - 新增依赖
