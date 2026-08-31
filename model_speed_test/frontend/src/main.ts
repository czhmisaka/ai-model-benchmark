import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/variables.scss'
import ECharts from 'vue-echarts'
import { echarts } from './utils/echarts'

const app = createApp(App)

app.use(router)
app.component('v-chart', ECharts)

// 确保 echarts 树摇后仍注册（vue-echarts 内部使用同一实例）
void echarts

app.mount('#app')
