/**
 * ECharts 按需引入模块
 *
 * 统一注册所需图表类型/组件，History.vue 等直接从这里 import { echarts }，
 * 避免 import * as echarts from 'echarts' 全量打包（~1MB）。
 */
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart, RadarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'

// 注册（幂等，重复调用无副作用）
echarts.use([
  CanvasRenderer,
  LineChart,
  BarChart,
  PieChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
])

export { echarts }
export type { ECharts } from 'echarts/core'
