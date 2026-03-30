<template>
  <div id="app">
    <Dashboard />
  </div>
</template>

<script setup lang="ts">
import Dashboard from './views/Dashboard.vue'
</script>

<style lang="scss">
*{
  user-select: auto !important;
}
:root {
  // 深色模式专业配色方案 - 橙色主调
  // 背景：使用深夜蓝而非纯黑，更柔和护眼
  --black: #0f172a;      // 深夜蓝
  --gray-900: #1e293b;   // 深蓝灰
  --gray-800: #334155;   // 中蓝灰
  --gray-700: #475569;   // 浅蓝灰
  --gray-600: #64748b;   // 蓝灰色
  --gray-500: #94a3b8;   // 冷灰
  --gray-400: #cbd5e1;   // 浅灰蓝
  --gray-300: #e2e8f0;   // 极浅灰
  --gray-200: #f1f5f9;   // 浅白
  --gray-100: #f8fafc;   // 近白
  --white: #ffffff;
  
  // 主色调 - 橙色 (Orange)，活力专业
  --primary: #f97316;         // Orange 500
  --primary-dim: rgba(249, 115, 22, 0.15);
  --primary-light: #fb923c;   // Orange 400
  --primary-dark: #ea580c;   // Orange 600
  
  // 强调色 - 橙色系
  --accent-red: #f43f5e;      // Rose 500 - 柔和红
  --accent-yellow: #f59e0b;   // Amber 500
  --accent-cyan: #06b6d4;    // Cyan 500
  --accent-green: #10b981;    // Emerald 500
  --accent-purple: #8b5cf6;   // Violet 500
  --accent-pink: #ec4899;     // Pink 500
  --accent-orange: #f97316;   // Orange 500
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--black);
  color: var(--gray-100);
  min-height: 100vh;
  overflow: hidden;
}

#app {
  min-height: 100vh;
  width: 100%;
}

/* 滚动条样式 */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--gray-600); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--gray-500); }

/* Toast 样式 */
.toast { 
  position: fixed; 
  top: 80px; 
  left: 20px; 
  background: var(--gray-800); 
  border: 1px solid var(--gray-600); 
  color: var(--white); 
  padding: 12px 20px; 
  border-radius: 8px; 
  font-size: 0.85rem; 
  z-index: 1000; 
  transform: translateX(-120%); 
  transition: transform 0.3s; 
}
.toast.show { transform: translateX(0); }
.toast.success { border-color: var(--accent-green); }
.toast.error { border-color: var(--accent-red); }

/* Modal 遮罩 */
.modal-overlay { 
  position: fixed; 
  inset: 0; 
  background: rgba(0,0,0,0.8); 
  display: none; 
  align-items: center; 
  justify-content: center; 
  z-index: 100; 
}
.modal-overlay.show { display: flex; }

@keyframes spin { 
  to { transform: rotate(360deg); } 
}

@keyframes blink { 0%,50%{opacity:1} 51%,100%{opacity:0} }

@keyframes pulse { 
  0%,100%{opacity:1} 50%{opacity:0.5} 
}
</style>·