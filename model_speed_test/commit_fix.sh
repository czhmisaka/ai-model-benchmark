#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "fix(ui): 修复侧边栏拖拽失效 + 测试集管理主题适配与功能增强

【侧边栏拖拽失效修复（回归）】
- 批次A死代码清理误删了 onDrag 的宽度更新逻辑（sidebarWidth.value = ...）
- 恢复完整实现：宽度跟随鼠标 + 最小/最大宽度限制 + 折叠状态最小值

【测试集管理修复与增强】
- 主题适配：管理弹窗为白底设计，内嵌 TreeView 使用深色主题浅色文字导致不可见；
  在弹窗容器局部覆盖 --gray-*/--primary 为白底可读的深色值
- 子文件夹创建：TreeView 右键'新建子文件夹'现在正确透传 parent_id
  （原链路断裂：一律创建根级文件夹）
- 主界面'新建文件夹'按钮直连创建逻辑（原来是打开管理弹窗，体验不一致）
- 文件夹重命名 prompt 预填当前名称
- 后端创建文件夹加同级同名防重（实测生效）
- 工具栏/emit 类型签名适配（vue-tsc 0 错误）"
echo EXIT=$?
