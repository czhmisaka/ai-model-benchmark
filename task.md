<!--
 * @Date: 2026-05-25 09:52
 * @LastEditors: CZH
 * @LastEditTime: 2026-05-25 10:45
 * @FilePath: /模型速度测试/task.md
-->

# 测试集文件夹管理功能 — 实施计划 v2

> 审查日期：2026-05-25  
> 审查结论：方案总体可行，经过两轮审查（设计方案审查 + 业务关联审查），已覆盖全部风险点。

---

## 🔍 审查发现的设计空白（已补充进本计划）

| # | 空白点 | 影响 | 解决方案 |
|---|--------|------|----------|
| 1 | TreeView 在 Dashboard 中的**交互流程**未定义 | 开发时需临时决策，可能反复 | §3.1 详述：TreeView 直接替换现有 Test Cases 列，原有 `toggleCase` / `selectedCases` 逻辑改写为 flatten 后代计算 |
| 2 | 文件夹选中后的**全选联动**未设计 | 树形勾选是最大复杂度来源 | §3.1.2 定义三级联动：全选→后代选中、部分后代→indeterminate、搜索展开父路径 |
| 3 | 选中后 `StartConfigModal` 如何**按文件夹展示**未定 | 用户体验断裂 | §3.3 补充：弹窗按文件夹分组展示选中的用例 |
| 4 | 数据存储方式（DB vs JSON）未明确 | 架构不清晰 | §1.3 确认：使用 SQLite config.db，新增 test_case_folders 表 |
| 5 | API 端点风格需与现有 RESTful 一致 | 原方案用全 POST，与现有 GET/PUT/DELETE 模式冲突 | §2.1 改为 RESTful 对标 models/test-cases |

---

## 🔬 第二轮审查：业务关联断裂点（全部已补充）

| # | 断裂点 | 影响范围 | 严重程度 | 解决方案 |
|---|--------|----------|:--:|------|
| 6 | **ModelCaseModal 缺少 folder 选择器** — 新增/编辑用例时无法指定所属文件夹 | 用户创建用例后必须去管理弹窗手动移动，体验断裂 | 🔴 高 | §3.6：在 ModelCaseModal 表单中新增 `folder_id` 下拉选择器 |
| 7 | **报告生成器同名用例合并风险** — `report_generator.py` 按 `test_case_name` 分组统计，不同文件夹下同名用例的指标会被错误合并 | 报告数据失真，影响评测结论 | 🔴 高 | §9.4：报告分组维度加入 `folder_id`，模板上下文增加 `folder_name` |
| 8 | **Excel 导出丢失文件夹上下文** — `excel_exporter.py` 纯平铺输出，无法按文件夹层级展示 | 导出结果丧失组织结构，阅读体验差 | 🟡 中 | §2.2：Excel 测试用例列追加 `所属文件夹` |
| 9 | **历史记录同名用例混淆** — `History.vue` 依赖 `test_case_name` 展示，同名用例无法区分来源 | 用户无法判断历史任务中同名用例来自哪个文件夹 | 🟡 中 | §9.5：任务执行时记录 `folder_id`，History 展示追加文件夹标签 |
| 10 | **scheduler 测试执行记录无 folder 上下文** — `scheduler.py` 接收 selectedCases 列表执行，测试结果中不保存 folder 信息 | 后续按文件夹复盘测试结果时无法回溯 | 🟡 中 | §2.2：执行结果持久化时追加 `folder_id` / `folder_name` |

---

## 📦 一、数据结构设计

### 1.1 新增数据库表
**文件：`model_speed_test/migrations/add_test_case_folders.py`**

```sql
CREATE TABLE IF NOT EXISTS test_case_folders (
    folder_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT,              -- 父文件夹 ID（NULL 表示根目录）
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES test_case_folders(folder_id) ON DELETE CASCADE
);

-- test_cases 表新增字段
ALTER TABLE test_cases ADD COLUMN folder_id TEXT;
```

### 1.2 字段说明
| 字段 | 类型 | 说明 |
|------|------|------|
| folder_id | TEXT | 文件夹唯一标识（UUID） |
| name | TEXT | 文件夹名称 |
| parent_id | TEXT | 父文件夹 ID（NULL = 根目录） |
| folder_id (test_cases) | TEXT | 测试用例所属文件夹（NULL = 未分类） |

### 1.3 存储方式
- 使用现有 SQLite `results/config.db`
- 与 models / test_cases / system_config 表共存
- 不引入新的存储文件

---

## 🔌 二、后端 API 设计（RESTful，与现有风格一致）

### 2.1 新增端点（文件：`model_speed_test/web/app.py`）

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/config/test-case-folders` | 获取所有文件夹（树形结构） |
| POST | `/config/test-case-folders` | 创建新文件夹 |
| PUT | `/config/test-case-folders/{folder_id}` | 更新文件夹（重命名、移动） |
| DELETE | `/config/test-case-folders/{folder_id}` | 删除文件夹（子文件夹级联删除，用例回退 NULL） |

### 2.2 现有端点修改

| 位置 | 改动 |
|------|------|
| `get_config` — test_cases 查询 | SELECT 增加 `folder_id` 字段 |
| `get_config` — 返回结构 | 追加 `folders` 字段（树形结构） |
| `add_test_case` — INSERT | 增加 `folder_id` |
| `update_test_case` — UPDATE | 增加 `folder_id` |

### 2.3 API 响应格式

**GET /config/test-case-folders 返回：**
```json
{
  "folders": [
    {
      "folder_id": "f_001",
      "name": "数学推理",
      "parent_id": null,
      "sort_order": 0,
      "children": [
        {
          "folder_id": "f_002",
          "name": "几何",
          "parent_id": "f_001",
          "sort_order": 0,
          "children": []
        }
      ]
    }
  ]
}
```

### 2.4 关键逻辑说明

**PUT 移动文件夹的循环检测：**
```
从目标 parent_id 向上递归回溯，若路径中包含自身 folder_id 则拒绝操作
```

**DELETE 级联策略：**
```
1. 递归收集所有子文件夹 ID
2. 将所有受影响文件夹下的 test_cases 的 folder_id 置为 NULL
3. 删除所有子文件夹记录
4. 删除目标文件夹记录
```

---

## 🎨 三、前端组件设计

### 3.1 Dashboard.vue 改造（核心变更）

#### 3.1.1 结构变化
```
改造前：左侧列 → 平铺的 Test Cases 列表（v-for caseItem）
改造后：左侧列 → <TreeView> 组件（递归树形 + 勾选）
```

#### 3.1.2 选中逻辑改写

| 原逻辑 | 新逻辑 |
|--------|--------|
| `toggleCase(id)` — 简单 toggle Set | `toggleCase(id)` — 若为文件夹则 flatten 后代全部 toggle |
| `selectedCases` — 平铺 Set | `selectedCases` — 保持平铺 Set，但在 toggle 文件夹时批量操作 |
| `selectAllCases` — 全选 test_cases 数组 | `selectAllCases` — 改为"根目录全选"，包含未分类用例 + 根文件夹下所有 |
| 无 indeterminate | 文件夹节点：全选后代 → ✓；部分后代 → ■（indeterminate）；无后代或无选中 → □ |
| 无搜索联动 | 搜索时自动展开匹配用例的父路径（逐层 parent_id 回溯） |

#### 3.1.3 交互流程
```
1. 用户点击左侧列用例 / 文件夹 → toggle 选中状态
2. 点击 [Start] → 打开 StartConfigModal（§3.3），按文件夹分组显示已选用例
3. 确认启动 → 发送 POST /test/start，selectedCases 平铺传递（不变）
4. 点击 [🔧管理] → 打开 TestSetManagerModal（§3.4）
```

---

### 3.2 TreeView 组件设计

#### 3.2.1 组件拆分
| 组件 | 文件 | 职责 |
|------|------|------|
| TreeView | `components/dashboard/TreeView.vue` | 容器：搜索、拖拽指示线、事件管理 |
| TreeItem | `components/dashboard/TreeItem.vue` | 递归子组件：渲染单个节点 + 递归渲染子节点 |

#### 3.2.2 TreeView Props
```ts
interface TreeViewProps {
  folders: TreeNode[]           // 树形文件夹数据
  testCases: TestCase[]        // 所有测试用例（含 folder_id）
  selectedIds: Set<string>     // 选中 ID 集合
  searchQuery: string          // 搜索关键词
}
```

#### 3.2.3 TreeView Emits
```ts
interface TreeViewEmits {
  'toggle-select': [id: string]   // 切换选中
  'select-all': []                // 全选
  'deselect-all': []              // 取消全选
}
```

#### 3.2.4 TreeItem 核心逻辑
```
1. 若是文件夹节点：
   - 渲染自身 checkbox（checked / indeterminate / unchecked）
   - 递归渲染 children
2. 若是用例节点：
   - 渲染 checkbox（checked / unchecked）
   - 显示用例名称
3. 被搜索匹配到的节点：高亮名称 + 自动展开父路径
```

#### 3.2.5 拖拽支持
- **源**：测试用例项（draggable）
- **目标**：文件夹或根目录区域
- **视觉反馈**：目标文件夹高亮边框 + 放置位置蓝色指示线
- **实现**：使用 HTML5 Drag & Drop API，dragstart 记录 caseId，dragover 高亮目标，drop 调用 API PUT /config/test-cases/{id}/move

---

### 3.3 StartConfigModal 改造

**原有**：弹窗只配置测试轮数/并发/间隔/名称  
**新增**：弹窗顶部追加"已选测试用例"预览区，按文件夹分组：

```
┌─ 测试启动配置 ──────────────────────┐
│                                     │
│  已选测试用例 (3)                    │
│  ┌─ 📁 数学推理 (2)                 │
│  │   ☑ GSM8K-Math                  │
│  │   ☑ Math-Basic                  │
│  ├─ 📁 代码生成 (1)                 │
│  │   ☑ Python-Sort                 │
│  └─ 未分类 (0)                      │
│                                     │
│  测试轮数: [___]  并发: [___]       │
│  ...                                │
│            [取消]  [确认启动]         │
└─────────────────────────────────────┘
```

- 该区域只读预览，不可在此修改选中
- 支持折叠/展开文件夹
- 数据来源：Dashboard 的 `selectedCases` + `folders` 树形结构

---

### 3.4 TestSetManagerModal（新增弹窗）

| 文件 | 功能 |
|------|------|
| `components/dashboard/modals/TestSetManagerModal.vue` | 测试集管理弹窗主容器 |

**功能布局**：
```
┌─ 测试集管理 ────────────────────────┐
│  [🔍 搜索...]  [+ 新建文件夹]        │
│ ┌──────────────┬──────────────────┐ │
│ │ 🌳 TreeView  │ 📋 详情面板       │ │
│ │              │                  │ │
│ │ (文件夹+用例)│ 选中项详情        │ │
│ │              │ - 名称           │ │
│ │              │ - 所属文件夹     │ │
│ │              │ - 用例预览       │ │
│ └──────────────┴──────────────────┘ │
│              [确定]  [取消]          │
└─────────────────────────────────────┘
```

**TreeView 右键菜单项**：
- 文件夹右键：`新建子文件夹` / `重命名` / `删除` / `展开全部` / `折叠全部`
- 用例右键：`打开编辑` / `移动到…` / `删除`
- 空区域右键：`新建文件夹` / `新建测试用例`

---

### 3.5 ContextMenu 组件

| 文件 | 功能 |
|------|------|
| `components/dashboard/components/ContextMenu.vue` | 右键上下文菜单 |

**实现要点**：
- 全局单例（同一时间只有一个菜单显示）
- 使用 Teleport 渲染到 body，避免被父容器 overflow 裁剪
- 菜单项根据 `contextType: 'folder' | 'case' | 'empty'` 动态切换
- 点击菜单外部或 ESC 自动关闭

---

## 📝 四、修改范围清单

### 4.1 新建文件
- [ ] `model_speed_test/migrations/add_test_case_folders.py` — 数据库迁移脚本
- [ ] `frontend/src/components/dashboard/TreeView.vue` — 树形容器组件
- [ ] `frontend/src/components/dashboard/TreeItem.vue` — 树形递归子组件
- [ ] `frontend/src/components/dashboard/components/ContextMenu.vue` — 右键菜单组件
- [ ] `frontend/src/components/dashboard/modals/TestSetManagerModal.vue` — 管理弹窗

### 4.2 修改现有文件

| 文件 | 改动内容 | 行数 |
|------|----------|:--:|
| `web/app.py` | get_config 加 folder_id + folders 返回；新增 4 个 API；add/update test_case 加 folder_id | ~155 |
| `web/report_generator.py` | `_fetch_group_data` SQL 增加 folder 维度；模板上下文增加 `folder_name` | ~15 |
| `web/excel_exporter.py` | 详细数据 Sheet 追加「所属文件夹」列 | ~10 |
| `src/scheduler.py` | 测试执行记录追加 `folder_id`（仅存储，不参与调度逻辑） | ~5 |
| `views/Dashboard.vue` | Test Cases 列替换为 TreeView；toggle 逻辑改写；搜索展开联动；[🔧管理] 按钮 | ~85 |
| `modals/StartConfigModal.vue` | 追加"已选用例"预览区，按文件夹分组展示 | ~30 |
| `modals/ModelCaseModal.vue` | **新增** `folder_id` 下拉选择器（§3.6） | ~20 |
| `composables/useConfig.ts` | 追加 Folder 类型 + 4 个 API 方法；CaseForm 增加 `folder_id` | ~60 |
| `views/History.vue` | 任务卡片追加文件夹标签展示 | ~15 |
| `styles/variables.scss` | 新增树形相关 CSS 变量（缩进、hover 色等） | ~20 |

---

## 🔒 五、数据备份策略

### 5.1 备份命令
```bash
cp results/config.db results/config.db.backup_$(date +%Y%m%d_%H%M%S)
```

### 5.2 回滚方案
- 直接恢复 config.db 备份文件
- 新代码不影响旧表结构（ALTER TABLE ADD COLUMN 可回退）

### 5.3 兼容性保证
- `folder_id` 默认 NULL，旧数据不受影响
- 旧测试用例在 TreeView 中显示在「未分类」区域
- 新增测试用例默认 folder_id=NULL（根目录）

---

## 📋 六、实施步骤

| 阶段 | 步骤 | 说明 |
|------|------|------|
| **准备** | 1. 备份数据库 | `cp results/config.db results/config.db.backup` |
| | 2. 确认现有数据完整性 | 检查 test_cases 数量 |
| **后端** | 3. 创建迁移脚本并执行 | 新增 test_case_folders 表 + 字段 |
| | 4. 实现文件夹 CRUD API | GET/POST/PUT/DELETE |
| | 5. 修改现有端点兼容 | get_config / add_test_case / update_test_case |
| **前端** | 6. 创建 TreeItem 递归组件 | checkbox 三态 + 展开折叠 |
| | 7. 创建 TreeView 容器组件 | 搜索 + 拖拽 + 事件分发 |
| | 8. 创建 ContextMenu 组件 | 右键菜单单例 |
| | 9. 创建 TestSetManagerModal | 管理弹窗 |
| | 10. Dashboard 集成 TreeView | 替换 Test Cases 列 |
| | 11. StartConfigModal 改造 | 加分组预览 |
| | 12. useConfig 追加 API | Folder + CRUD |
| **测试** | 13. 功能测试 | 全部功能 |
| | 14. 兼容性测试 | 旧数据正常 |
| **收尾** | 15. 清理备份 | 确认后删除 |

---

## 🎯 七、验收标准

1. 能创建、重命名、删除文件夹
2. 能拖拽测试用例到文件夹
3. 树形结构支持展开/折叠
4. 右键菜单功能正常
5. 搜索能定位用例并自动展开父路径
6. 文件夹全选/部分选（indeterminate）联动正常
7. StartConfigModal 按文件夹分组展示已选用例
8. 主页列表展示不受影响
9. 历史数据（无 folder_id）正常显示在「未分类」中

---

## ⚠️ 八、风险点与难度评估

### 8.1 复杂度热点

| 模块 | 风险等级 | 说明 |
|------|:--:|------|
| TreeItem 递归渲染 | ⭐⭐⭐⭐ | 全选联动 + indeterminate + 搜索展开父路径，是最大复杂度来源 |
| PUT folders/{id} 移动 | ⭐⭐⭐ | 循环检测需递归回溯 ancestor chain |
| DELETE folders/{id} | ⭐⭐⭐ | 级联删除子文件夹 + 子用例回退 NULL |
| Dashboard 集成 | ⭐⭐⭐ | 与 6817 行现有代码解耦，不破坏 selectedCases 消费者 |

### 8.2 改动量统计（终审后更新）

| 维度 | 数量 |
|------|:--:|
| 新增文件 | 5 个 |
| 修改文件 | 9 个（原 5 + 新增 4：report_generator.py / excel_exporter.py / scheduler.py / History.vue） |
| 新增代码 | ~1070 行（后端 ~185 + 前端 ~885） |

### 8.3 预计工时（终审后更新）

| 阶段 | 工时 |
|------|:--:|
| 后端开发 | ~2.5h（+0.5h 报告/导出/scheduler 适配） |
| 前端开发 | ~8h（+1h ModelCaseModal / History 适配） |
| 测试调试 | ~2h |
| **总计** | **~12.5h** |

---

## 🏗️ 九、架构影响分析

### 9.1 后端影响
| 模块 | 影响 | 风险 |
|------|------|:--:|
| get_config | test_cases 追加 folder_id，新增 folders 返回 | 低 |
| add_test_case / update_test_case | INSERT/UPDATE 追加 folder_id | 低 |
| 文件夹 CRUD | 4 个新路由 | 中 |
| models / 测试执行 / 报告 | 无影响 | — |

### 9.2 前端影响
| 模块 | 影响 | 风险 |
|------|------|:--:|
| Dashboard Test Cases 列 | 替换为 TreeView | 中 |
| Dashboard toggleCase / selectedCases | 改写为 flatten 后代逻辑 | 中 |
| StartConfigModal | 新增分组预览 | 低 |
| useConfig | 新增 Folder 类型 + API | 低 |
| 其他组件（History / Settings） | 无影响 | — |

### 9.3 数据兼容性
- ✅ 旧数据 folder_id=NULL → 显示在「未分类」
- ✅ 新增用例默认 NULL
- ✅ API 所有返回均追加 folder_id（前端可忽略）

---

## 📐 十、第二轮审查发现的业务要点

### 10.1 ModelCaseModal 的 folder 选择器（🔴 高优先级）

**现状**：`ModelCaseModal.vue` 的 `CaseForm` 仅有 `name / messages / max_tokens / expected_output / eval_model` 五个字段，无 folder 选择能力。

**用户场景**：用户在 Dashboard 点击「+」添加用例时，应该能直接指定放入哪个文件夹（就像新建文件时选择保存路径一样）。

**改动**：
- `CaseForm` 接口新增 `folder_id?: string`
- 表单新增一行 dropdown：`所属文件夹: [下拉选择器]`
- 下拉选项从 `config.folders` 扁平化为 `{ label: '📁 数学/几何', value: 'f_002' }` 格式
- 默认值为空（表示根目录 / 未分类）
- `submitModal()` 时 POST body 携带 `folder_id`

### 10.2 报告生成器的同名用例问题（🔴 高优先级）

**现状**：`report_generator.py` 的 `get_group_summary` SQL 使用 `GROUP BY model_name, test_case_name`。如果用户在「数学/几何」和「数学/代数」两个文件夹下各有一个名为「基础测试」的用例，它们的统计数据会被**错误合并**。

**改动**：
- SQL SELECT 追加 `folder_id`
- `GROUP BY` 改为 `GROUP BY model_name, test_case_name, folder_id`
- 模板上下文 `_build_template_context` 新增 `folder_name` 字段（通过 folder_id 回查）
- 报告封面可展示"所属文件夹: xxx"

**注意**：`get_group_summary` 函数同时被 `report_generator.py` 和 `excel_exporter.py` 调用，修改该 SQL 对两个模块均生效。

### 10.3 历史记录展示的文件夹标签（🟡 中优先级）

**现状**：`History.vue` 展示历史任务时仅显示 `test_case_name`，无法区分同名用例来源。

**改动**：
- `results` 表中每条执行记录追加 `folder_id` / `folder_name`（scheduler 写入时填入）
- History 页面任务卡片中用例名后面追加小型 folder 标签：`[📁 数学]`
- 若 folder_id 为 NULL（旧数据），不展示标签（向后兼容）

### 10.4 修订后的完整实施步骤

| 阶段 | 步骤 | 说明 |
|------|------|------|
| **准备** | 1. 备份数据库 | `cp results/config.db results/config.db.backup` |
| | 2. 确认现有数据完整性 | 检查 test_cases 数量，列出同名用例 |
| **后端** | 3. 创建迁移脚本并执行 | test_case_folders 表 + folder_id 字段 |
| | 4. 实现文件夹 CRUD API | GET/POST/PUT/DELETE |
| | 5. 修改现有端点兼容 | get_config / add_test_case / update_test_case 加文件夹 |
| | 6. 适配报告生成器 | get_group_summary SQL 加 folder 维度 |
| | 7. 适配 Excel 导出 | 追加文件夹列 |
| | 8. 适配 scheduler | 执行记录存储 folder_id |
| **前端** | 9. 创建 TreeItem 组件 | checkbox 三态 + 展开折叠 |
| | 10. 创建 TreeView 组件 | 搜索 + 拖拽 + 事件分发 |
| | 11. 创建 ContextMenu 组件 | 右键菜单单例 |
| | 12. 创建 TestSetManagerModal | 管理弹窗 |
| | 13. Dashboard 集成 TreeView | 替换 Test Cases 列 |
| | 14. ModelCaseModal 加 folder 选择器 | folder_id 下拉 |
| | 15. StartConfigModal 改造 | 分组预览 |
| | 16. useConfig 追加 API | Folder + CRUD |
| | 17. History 追加文件夹标签 | 任务卡片展示 |
| **测试** | 18. 功能测试 | 全部功能 |
| | 19. 同名用例报告验证 | 确保不同文件夹同名用例不合并 |
| | 20. 兼容性测试 | 旧数据正常 |
| **收尾** | 21. 清理备份 | 确认后删除 |

---

## 📐 十一、附录：TreeView 节点数据结构

```ts
interface TreeNode {
  folder_id: string
  name: string
  parent_id: string | null
  sort_order: number
  children: TreeNode[]
  // 前端运行时追加：
  _expanded?: boolean
  _matched?: boolean       // 搜索匹配
  _hasMatchInChildren?: boolean // 子节点有匹配（用于自动展开）
}

interface TestCaseWithFolder {
  id: string
  name: string
  folder_id: string | null  // 新增字段
  // ... 其他现有字段
}

---

## 📐 十二、优化方案对比分析

### 12.1 问题 6：ModelCaseModal 缺少 folder 选择器

#### 方案 A：表单内嵌下拉选择器（✅ 推荐，当前采纳）

在 CaseForm 中新增 `所属文件夹` dropdown，选项从 `config.folders` 扁平化。

```
新增用例表单
┌──────────────────────────────┐
│ 用例名称: [____________]     │
│ 所属文件夹: [📁 数学/几何 ▾] │  ← 新增
│ Prompt: [____________]       │
│ ...                          │
└──────────────────────────────┘
```

| 维度 | 评估 |
|------|------|
| 前端改动 | ~20 行 |
| 层级感知 | 🟡 较弱的扁平列表，不适合深层次文件夹 |
| 覆盖场景 | 90%，主流场景够用 |
| 代码冗余 | 无 |

#### 方案 B：弹窗内嵌微型 TreeView 选择器（备选）

将 folder 选择器改为可折叠的树形选择器，用户在表单中看到完整文件夹树。

| 维度 | 评估 |
|------|------|
| 前端改动 | ~80 行（需从 TreeItem 组件复用或抽取共享逻辑） |
| 层级感知 | ✅ 强，适合深层次文件夹 |
| 覆盖场景 | 100% |
| 代码冗余 | ⚠️ 与 TreeItem 组件逻辑重叠 |

#### 决策

**采用方案 A**。理由：
- "新建用例" 是附属操作，Dropdown 覆盖 90% 场景
- 用户如需精细管理文件夹结构，会去 TestSetManagerModal（右键菜单 → 移到文件夹）
- 方案 B 可作为第二阶段优化

---

### 12.2 问题 7：报告生成器同名用例合并

#### 方案 A：SQL GROUP BY 加入 folder_id（✅ 必须执行，当前采纳）

```sql
-- 原
GROUP BY model_name, test_case_name

-- 改后
GROUP BY model_name, test_case_name, folder_id
```

模板上下文通过 `folder_id` 回查 `folder_name`，报告封面可展示"所属文件夹: xxx"。

| 维度 | 评估 |
|------|------|
| SQL 改动 | ~5 行 |
| 模板改动 | ~10 行 |
| 展示效果 | 平铺 + folder 标签 |
| 向后兼容 | ✅ folder_id=NULL → 不展示标签 |
| 数据正确性 | ✅ 彻底解决同名合并问题 |

#### 方案 B：报告按「文件夹 → 用例 → 模型」三级展示（第二阶段可选）

不只是修改 GROUP BY，而是改变报告的整**展示结构**：

```
📊 模型速度评测报告
───────────────────────
📁 数学推理
  ├─ 📝 GSM8K-Math
  │   ├─ GPT-4   | 首字 0.3s | 总 1.2s | ...
  │   └─ Claude  | 首字 0.4s | 总 1.5s | ...
  └─ 📝 Math-Basic
      └─ ...
📁 代码生成
  ├─ 📝 Python-Sort
  │   └─ ...
  └─ ...
未分类
  └─ ...
```

| 维度 | 评估 |
|------|------|
| SQL 改动 | ~10 行 |
| 模板改动（Jinja2 模板） | ~40 行（需双层嵌套渲染） |
| 展示效果 | ✅ 结构清晰，一目了然 |
| 向后兼容 | ✅ folder_id=NULL → "未分类" |
| 风险 | ⚠️ 现有报告模板 `default_report.md.j2` / `minimal_report.md.j2` 均为平铺结构，重建工作量大 |

#### 决策

**第一阶段：方案 A 作为底线（必须执行）**，确保数据正确性不可妥协。

**第二阶段（可选）**：方案 B 的文件夹层级报告模板。触发条件：
- 项目有时间余量
- 用户反馈平铺展示可读性差
- 同一时间实施则总工时 +1.5h

| 方案 | 优先级 | 工时 | 备注 |
|------|:--:|:--|------|
| A：SQL 防合并 | 🔴 P0 | +0.3h | 必须做 |
| B：文件夹层级报告 | 🟢 P2 | +1.5h | 可延后 |

---

## 📐 十三、附录：现有报告模板结构参考

### default_report.md.j2 核心结构

```jinja2
{% for group in report_data.groups %}
## {{ group.model_name }} — {{ group.test_case_name }}
| 指标 | 值 |
|------|------|
| 首字耗时 | {{ group.ttft_avg }}ms |
| 总耗时 | {{ group.total_time_avg }}ms |
| ...
{% endfor %}
```

### 方案 B 改造后的模板结构（规划）

```jinja2
{% for folder in report_data.folder_groups %}
## 📁 {{ folder.name }}
{% for case in folder.cases %}
### {{ case.test_case_name }}
{% for model in case.models %}
| {{ model.name }} | {{ model.ttft_avg }}ms | {{ model.total_time_avg }}ms | ...
{% endfor %}
{% endfor %}
{% endfor %}
```
