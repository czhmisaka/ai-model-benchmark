#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "feat(ui): 全面移除浏览器原生模态框（21处），替换为自定义 AppDialog

新增基础设施：
- composables/useDialog.ts: 全局对话框 composable（Promise 风格 confirm/prompt）
- components/common/AppDialog.vue: 统一深色主题对话框（确认/输入两用，
  支持 danger 红色按钮、Enter 确认、Esc 取消、输入自动聚焦）

替换明细（21处原生调用清零）：
- Dashboard.vue 9处：新建/重命名文件夹、文件夹选择器、删除模型/用例/文件夹/记录、模式切换
- TestSetManagerModal 6处：新建/重命名/删除文件夹、用例删除/移动、序号选择器
- Settings.vue 2处：保存反馈改为按钮文案变化，重置确认改 AppDialog
- History.vue 1处：删除测试记录确认
- ReportPreviewModal 2处：alert 改为组件内 toast"
echo EXIT=$?
