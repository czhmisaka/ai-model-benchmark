<template>
  <div class="dashboard">
    <!-- 顶部栏 -->
    <header class="header">
      <div class="logo">
        <button class="fullscreen-btn" @click="toggleFullscreen" title="全屏显示">
          <span class="fullscreen-icon">{{ isFullscreen ? '⤓' : '⤢' }}</span>
        </button>
        Czhmisaka
        <span class="logo-tag">MODEL TEST</span>
      </div>
      <div class="status-row">
        <div class="status-item">
          <span class="status-dot" :class="{ connected: sseConnected }"></span>
          <span class="status-label">SSE</span>
          <span class="status-value">{{ sseStatus }}</span>
        </div>
        <div class="status-item">
          <span class="status-dot" :class="{ running: testRunning }"></span>
          <span class="status-label">TEST</span>
          <span class="status-value">{{ testStatus }}</span>
        </div>
      </div>
      <div class="controls">
        <button class="btn btn-primary" id="startBtn" @click="showStartConfig" :disabled="testRunning">▶ START</button>
        <button class="btn btn-secondary" id="stopBtn" @click="stopTest" :disabled="!testRunning">■ STOP</button>
        <button class="btn btn-secondary" id="clearBtn" @click="clearTest">✕ CLEAR</button>
        <button class="btn btn-secondary" id="historyBtn" @click="showHistoryModal">☰ HISTORY</button>
        <button class="btn btn-accent" id="aiAnalysisBtn" @click="toggleAiAnalysis" :disabled="aiAnalysisLoading">
          {{ aiAnalysisLoading ? '⏳ 分析中...' : '🤖 AI 分析' }}
        </button>
      </div>
    </header>

    <!-- 左侧：配置 -->
    <div class="panel-left" :class="{ collapsed: isCollapsed }">
      <!-- 折叠提示 -->
      <div class="collapse-hint" :class="{ collapsed: isCollapsed }" @click="toggleSidebar">
        <span class="collapse-icon" :class="{ collapsed: isCollapsed }">»</span>
      </div>
      <!-- 拖拽手柄 -->
      <div class="resize-handle" @mousedown="startDrag"></div>
      
      <!-- Models 列 -->
      <div class="list-section">
        <div class="list-header">
          <span>Models</span>
          <div class="header-actions">
            <button class="select-all-btn" @click="selectAllModels" title="Select/Deselect All">
              {{ selectedModels.size === config?.models?.length ? '⊙' : '○' }}
            </button>
            <button class="add-btn" @click="showModal('model')" title="Add Model">+</button>
          </div>
        </div>
        <div class="item-list" id="modelList">
          <div 
            v-for="model in config?.models || []" 
            :key="model.name"
            class="item"
            :class="{ selected: selectedModels.has(model.name) }"
            @click="toggleModel(model.name)"
            @mouseenter="showModelPopover($event, model)"
            @mouseleave="hideModelPopover"
          >
            <div class="item-checkbox">{{ selectedModels.has(model.name) ? '✓' : '' }}</div>
            <div class="item-name" :title="model.name">{{ model.name }}</div>
            <button class="item-edit" @click.stop="editModel(model)" title="Edit">✎</button>
            <button class="item-delete" @click.stop="deleteModel(model.name)" title="Delete">×</button>
          </div>
          <div v-if="!config?.models?.length" class="item">
            <span class="item-name" style="color:var(--gray-500)">No models</span>
          </div>
        </div>
      </div>
      
      <!-- Test Cases 列 -->
      <div class="list-section">
        <div class="list-header">
          <span>Test Cases</span>
          <div class="header-actions">
            <button class="select-all-btn" @click="selectAllCases" title="Select/Deselect All">
              {{ selectedCases.size === config?.test_cases?.length ? '⊙' : '○' }}
            </button>
            <button class="add-btn" @click="showModal('case')" title="Add Test Case">+</button>
          </div>
        </div>
        <div class="item-list" id="caseList">
          <div 
            v-for="caseItem in config?.test_cases || []" 
            :key="caseItem.id"
            class="item"
            :class="{ selected: selectedCases.has(caseItem.id) }"
            @click="toggleCase(caseItem.id)"
            @mouseenter="showCasePopover($event, caseItem)"
            @mouseleave="hideCasePopover"
          >
            <div class="item-checkbox">{{ selectedCases.has(caseItem.id) ? '✓' : '' }}</div>
            <div class="item-name" :title="caseItem.name">{{ caseItem.name }}</div>
            <button class="item-edit" @click.stop="editCase(caseItem)" title="Edit">✎</button>
            <button class="item-delete" @click.stop="deleteCase(caseItem.id)" title="Delete">×</button>
          </div>
          <div v-if="!config?.test_cases?.length" class="item">
            <span class="item-name" style="color:var(--gray-500)">No cases</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 中间：任务卡片 -->
    <div class="panel-main">
      <div class="task-cards" id="taskCards">
        <div v-if="taskCount === 0" class="empty-tasks">
          <div class="empty-icon">🧪</div>
          <div class="empty-text">No Running Tasks</div>
          <div class="empty-hint">Select models and test cases, then click START</div>
        </div>
        
        <div 
          v-for="(task, taskId) in tasks" 
          :key="taskId"
          class="task-card"
          :class="[task.status, { dragging: cardDragState.isDragging && cardDragState.draggingCardId === taskId }]"
          :id="`card-${taskId}`"
          :style="getCardStyle(taskId)"
          @click="openTaskDetail(taskId)"
          @mousedown="startCardDrag($event, taskId)"
        >
          <!-- 卡片尺寸调整手柄 -->
          <div class="card-resize-handle" @mousedown.stop="startCardResize($event, taskId)"></div>
          <div class="task-header">
            <div class="task-info">
              <div class="task-model">{{ task.model_name }}</div>
              <div class="task-case">{{ task.case_name }}</div>
            </div>
            <div class="task-actions">
              <button 
                v-if="task.status === 'running'" 
                class="task-action-btn stop" 
                @click.stop="stopSingleTask(taskId)"
                title="停止此任务"
              >■</button>
              <button 
                v-if="task.status === 'done' || task.status === 'error'" 
                class="task-action-btn retry" 
                @click.stop="retrySingleTask(taskId)"
                title="重试此任务"
              >↻</button>
              <span class="task-status" :class="task.status">
                {{ runningCount(task) > 0 ? '⟳' : task.status === 'done' ? '✓' : '!' }} {{ doneCount(task) }}/{{ task.sub_tasks ? Object.keys(task.sub_tasks).length : 0 }}
              </span>
            </div>
          </div>
          <div class="task-progress">
            <div class="task-progress-bar">
              <div class="task-progress-fill" :style="{ width: task.progress + '%' }"></div>
            </div>
            <div class="task-progress-text">
              <span>{{ task.current_round || 0 }}/{{ task.total_rounds || 0 }}</span>
              <span>{{ task.progress }}%</span>
            </div>
          </div>
          <div class="task-content">
            <div class="task-io">
              <div class="task-io-header">轮次 Rounds - 点击查看详情</div>
              <div class="round-matrix" :class="{ 'dot-mode': useDotMode(task.total_rounds) }" :style="{ gridTemplateColumns: `repeat(${getGridColumns(task.total_rounds)}, 1fr)` }">
                <div 
                  v-for="(subTask, subId) in task.sub_tasks" 
                  :key="subId"
                  class="round-btn"
                  :class="[subTask.status, { 'dot-mode': useDotMode(task.total_rounds) }]"
                  :style="{ fontSize: getFontSize(task.total_rounds) }"
                  @mouseenter="showRoundPopoverForButton($event, taskId, subId, subTask)"
                  @mouseleave="hideRoundPopover"
                >
                  {{ getRoundStatusIcon(subTask.status, getSubTaskIndex(task, subId) + 1, task.total_rounds) }}
                </div>
              </div>
            </div>
          </div>
          <div class="task-metrics">
            <div class="task-metric">
              <div class="task-metric-value">{{ doneCount(task) }}</div>
              <div class="task-metric-label">完成</div>
            </div>
            <div class="task-metric">
              <div class="task-metric-value">{{ runningCount(task) }}</div>
              <div class="task-metric-label">进行中</div>
            </div>
            <div class="task-metric">
              <div class="task-metric-value">{{ errorCount(task) }}</div>
              <div class="task-metric-label">错误</div>
            </div>
            <div class="task-metric">
              <div class="task-metric-value">{{ task.total_rounds || 0 }}</div>
              <div class="task-metric-label">总计</div>
            </div>
            <div class="task-metric">
              <div class="task-metric-value duration">{{ formatDuration(getTaskDuration(task)) }}</div>
              <div class="task-metric-label">耗时</div>
            </div>
          </div>
          <!-- 卡片内的汇总统计（始终显示） -->
          <div class="task-result" :class="{ visible: task.status === 'done' }">
            <div class="task-result-title"><b style="font-weight:800;font-size:1.1em">平均数据</b></div>
            <div class="task-result-grid">
              <div class="task-result-item">
                <div class="task-result-value">{{ task.avgTtft || '--' }}</div>
                <div class="task-result-label">TTFT(s)</div>
              </div>
              <div class="task-result-item">
                <div class="task-result-value">{{ task.avgTpft || '--' }}</div>
                <div class="task-result-label">TPFT(s)</div>
              </div>
              <div class="task-result-item">
                <div class="task-result-value">{{ task.avgSpeed || '--' }}</div>
                <div class="task-result-label">速度/s</div>
              </div>
              <div class="task-result-item">
                <div class="task-result-value">{{ task.avgTokens || '--' }}</div>
                <div class="task-result-label">Tokens</div>
              </div>
            </div>
            
            <!-- 校对评分区域 - 紧凑单行显示 -->
            <div class="eval-section" :class="{ 'has-data': task.avgEvalRate !== undefined }">
              <template v-if="task.avgEvalRate !== undefined">
                <span class="eval-inline-label">均分:</span>
                <span class="eval-inline-value" :class="{ correct: task.avgEvalRate >= 6, incorrect: task.avgEvalRate < 6 }">
                  {{ task.avgEvalRate !== null ? task.avgEvalRate.toFixed(1) + '/10' : '--' }}
                </span>
                <span class="eval-divider">|</span>
                <span class="eval-correct">✓ {{ task.evalCorrectCount || 0 }}</span>
                <span class="eval-divider">|</span>
                <span class="eval-incorrect">✗ {{ task.evalIncorrectCount || 0 }}</span>
                <span class="eval-divider">|</span>
                <span class="eval-accuracy">{{ getEvalAccuracy(task) }}%</span>
              </template>
              <template v-else>
                <span class="eval-placeholder-text">无校对数据</span>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑 Model/Case Modal -->
    <div class="modal-overlay" :class="{ show: modalVisible }">
      <div class="modal">
        <div class="modal-title">{{ isEditing ? (modalType === 'model' ? 'Edit Model' : 'Edit Test Case') : (modalType === 'model' ? 'Add Model' : 'Add Test Case') }}</div>
        
        <!-- Model Form -->
        <div v-if="modalType === 'model'">
          <div class="form-group">
            <label class="form-label">Name</label>
            <input type="text" class="form-input" v-model="modelForm.name" placeholder="My Model" />
          </div>
          <div class="form-group">
            <label class="form-label">Endpoint</label>
            <input type="text" class="form-input" v-model="modelForm.endpoint" placeholder="https://api.example.com/v1/chat/completions" />
          </div>
          <div class="form-group">
            <label class="form-label">API Key</label>
            <input type="text" class="form-input" v-model="modelForm.api_key" placeholder="sk-..." />
          </div>
          <div class="form-group">
            <label class="form-label">Model</label>
            <input type="text" class="form-input" v-model="modelForm.model" placeholder="gpt-4o-mini" />
          </div>
          <!-- 测试按钮 -->
          <div class="form-group">
            <button 
              class="btn btn-test" 
              @click="testModel" 
              :disabled="!canTestModel || isTesting"
            >
              {{ isTesting ? '测试中...' : '🧪 测试连接' }}
            </button>
            <div v-if="testResult" class="test-result" :class="testResult.success ? 'success' : 'error'">
              <span v-if="testResult.success">✓ 连接成功 ({{ testResult.latency_ms }}ms)</span>
              <span v-else>✗ {{ testResult.error }}</span>
            </div>
          </div>
        </div>
        
        <!-- Case Form -->
        <div v-else>
          <div class="form-group">
            <label class="form-label">Name</label>
            <input type="text" class="form-input" v-model="caseForm.name" placeholder="Test Case" />
          </div>
          
          <!-- Messages 编辑器 -->
          <div class="form-group">
            <label class="form-label">Messages</label>
            <div class="messages-editor">
              <div 
                v-for="(msg, index) in caseForm.messages" 
                :key="index"
                class="message-item"
              >
                <div class="message-header">
                  <select class="message-role-select" v-model="msg.role">
                    <option value="system">system</option>
                    <option value="user">user</option>
                    <option value="assistant">assistant</option>
                  </select>
                  <button class="message-delete-btn" @click="removeMessage(index)" title="删除">×</button>
                </div>
                <textarea 
                  class="form-input message-content" 
                  v-model="msg.content" 
                  placeholder="输入消息内容..."
                ></textarea>
              </div>
              <button class="add-message-btn" @click="addMessage">+ 添加消息</button>
            </div>
          </div>
          
          <div class="form-group">
            <label class="form-label">Max Tokens</label>
            <input type="number" class="form-input" v-model="caseForm.max_tokens" value="500" />
          </div>
          
          <!-- 质量评估配置（可选） -->
          <div class="form-group">
            <label class="form-label">标准答案 Expected Output（可选，用于质量评估）</label>
            <textarea 
              class="form-input" 
              v-model="caseForm.expected_output" 
              placeholder="输入标准答案，用于计算偏离度..."
              rows="3"
            ></textarea>
          </div>
          
          <div class="form-group">
            <label class="form-label">校对模型 Eval Model（可选）</label>
            <select class="form-input" v-model="caseForm.eval_model">
              <option value="">不使用校对模型</option>
              <option 
                v-for="model in config?.models || []" 
                :key="model.name" 
                :value="model.name"
              >
                {{ model.name }}
              </option>
            </select>
          </div>
        </div>
        
        <div class="form-actions">
          <button class="btn btn-secondary" @click="hideModal">Cancel</button>
          <button class="btn btn-primary" @click="submitModal">{{ isEditing ? 'Save' : 'Add' }}</button>
        </div>
      </div>
    </div>

    <!-- 测试启动配置 Modal -->
    <div class="modal-overlay" :class="{ show: startConfigVisible }" @click.self="hideStartConfig">
      <div class="modal">
        <div class="modal-title">测试启动配置</div>
        <div class="form-group">
          <label class="form-label">测试轮数 (Test Rounds)</label>
          <input type="number" class="form-input" v-model="startConfig.test_rounds" min="1" max="100" />
          <div style="font-size: 0.65rem; color: var(--gray-500); margin-top: 4px;">每个模型-测试用例组合重复测试的轮数</div>
        </div>
        <div class="form-group">
          <label class="form-label">最大并发数 (Max Concurrent)</label>
          <input type="number" class="form-input" v-model="startConfig.max_concurrent" min="1" max="10" />
          <div style="font-size: 0.65rem; color: var(--gray-500); margin-top: 4px;">同时运行的模型数量（0表示不限制）</div>
        </div>
        <div class="form-group">
          <label class="form-label">请求间隔 (秒)</label>
          <input type="number" class="form-input" v-model="startConfig.interval" min="0" max="60" step="0.5" />
          <div style="font-size: 0.65rem; color: var(--gray-500); margin-top: 4px;">每轮测试之间的等待时间</div>
        </div>
        <div class="form-group">
          <label class="form-label">测试名称（可选）</label>
          <input type="text" class="form-input" v-model="startConfig.test_name" placeholder="自动生成" />
          <div style="font-size: 0.65rem; color: var(--gray-500); margin-top: 4px;">用于标识这次测试，方便历史记录查找</div>
        </div>
        <div class="form-actions">
          <button class="btn btn-secondary" @click="hideStartConfig">取消</button>
          <button class="btn btn-primary" @click="confirmStartTest">确认启动</button>
        </div>
      </div>
    </div>

    <!-- 任务详情 Modal -->
    <div class="modal-overlay" :class="{ show: taskDetailVisible }" @click.self="hideTaskDetail">
      <div class="modal task-detail-modal" :class="{ animating: isAnimating }">
        <div class="modal-title">
          任务详情
          <span class="task-detail-subtitle">{{ taskDetailData.model_name }} → {{ taskDetailData.case_name }}</span>
        </div>
        
        <div class="task-detail-content" v-if="taskDetailData.sub_tasks">
          <!-- 汇总统计 -->
          <div class="task-detail-summary">
            <div class="detail-stat-grid">
              <div class="detail-stat-item">
                <div class="detail-stat-value">{{ taskDetailData.avgTtft || '--' }}s</div>
                <div class="detail-stat-label">首Token (TTFT)</div>
              </div>
              <div class="detail-stat-item">
                <div class="detail-stat-value">{{ taskDetailData.avgTpft || '--' }}s</div>
                <div class="detail-stat-label">生成时间 (TPFT)</div>
              </div>
              <div class="detail-stat-item">
                <div class="detail-stat-value">{{ taskDetailData.avgTokens || '--' }}</div>
                <div class="detail-stat-label">输出Token</div>
              </div>
              <div class="detail-stat-item">
                <div class="detail-stat-value">{{ taskDetailData.avgSpeed || '--' }}</div>
                <div class="detail-stat-label">总速度/s</div>
              </div>
              <div class="detail-stat-item accent" v-if="taskDetailData.avgAnswerSpeed && taskDetailData.avgAnswerSpeed !== '--'">
                <div class="detail-stat-value">{{ taskDetailData.avgAnswerSpeed }}</div>
                <div class="detail-stat-label">Answer速度/s</div>
              </div>
              <div class="detail-stat-item" v-if="taskDetailData.avgThinkTokens && taskDetailData.avgThinkTokens !== '--'">
                <div class="detail-stat-value">{{ taskDetailData.avgThinkTokens }}</div>
                <div class="detail-stat-label">Think Tokens</div>
              </div>
              <div class="detail-stat-item" v-if="taskDetailData.avgAnswerTokens && taskDetailData.avgAnswerTokens !== '--'">
                <div class="detail-stat-value">{{ taskDetailData.avgAnswerTokens }}</div>
                <div class="detail-stat-label">Answer Tokens</div>
              </div>
            </div>
          </div>
          
          <!-- 详细轮次列表 -->
          <div class="task-detail-rounds">
            <div class="detail-rounds-title">各轮次详细数据</div>
            <div class="detail-rounds-list">
              <div 
                v-for="(subTask, subId) in taskDetailData.sub_tasks" 
                :key="subId"
                class="detail-round-item"
                :class="subTask.status"
              >
                <div class="detail-round-header">
                  <span class="detail-round-number">{{ subTask.name }}</span>
                  <span class="detail-round-status" :class="subTask.status">
                    {{ subTask.status === 'done' ? '✓ 成功' : subTask.status === 'error' ? '✗ 失败' : subTask.status === 'running' ? '⟳ 进行中' : '○ 待测试' }}
                  </span>
                </div>
                <div class="detail-round-metrics" v-if="subTask.status === 'done' && subTask.metrics">
                  <div class="metric-row">
                    <span class="metric-label">速度:</span>
                    <span class="metric-value">{{ subTask.metrics.speed || '--' }} t/s</span>
                    <span class="metric-label" v-if="subTask.metrics.answerSpeed"> (Answer: {{ subTask.metrics.answerSpeed }} t/s)</span>
                  </div>
                  <div class="metric-row">
                    <span class="metric-label">TTFT:</span>
                    <span class="metric-value">{{ subTask.metrics.ttft || '--' }}s</span>
                    <span class="metric-label"> TPFT:</span>
                    <span class="metric-value">{{ subTask.metrics.tpft || '--' }}s</span>
                  </div>
                  <div class="metric-row" v-if="subTask.metrics.tokens">
                    <span class="metric-label">Tokens:</span>
                    <span class="metric-value">{{ subTask.metrics.tokens }}</span>
                    <span class="metric-label" v-if="subTask.metrics.thinkTokens"> (Think: {{ subTask.metrics.thinkTokens }})</span>
                    <span class="metric-label" v-if="subTask.metrics.answerTokens"> (Answer: {{ subTask.metrics.answerTokens }})</span>
                  </div>
                  <div class="metric-row" v-if="subTask.metrics.answerTime !== undefined && subTask.metrics.answerTime !== null">
                    <span class="metric-label" v-if="subTask.metrics.thinkTime !== undefined && subTask.metrics.thinkTime !== null && subTask.metrics.thinkTime > 0">Think时间:</span>
                    <span class="metric-value" v-if="subTask.metrics.thinkTime !== undefined && subTask.metrics.thinkTime !== null && subTask.metrics.thinkTime > 0">{{ subTask.metrics.thinkTime }}s</span>
                    <span class="metric-label"> Answer时间:</span>
                    <span class="metric-value">{{ subTask.metrics.answerTime }}s</span>
                  </div>
                </div>
                <!-- 输入/输出显示 -->
                <div class="detail-round-io" v-if="subTask.status === 'done' || subTask.status === 'running'">
                  <!-- 输入显示 -->
                  <div class="io-section" v-if="subTask.prompt">
                    <div class="io-label">输入 Prompt:</div>
                    <div class="io-content input">{{ trimText(subTask.prompt.substring(0, 300)) }}</div>
                  </div>
                  <!-- 输出显示 -->
                  <div class="io-section" v-if="subTask.output">
                    <div class="io-label">输出预览:</div>
                    <div class="io-content output">{{ trimText(subTask.output.substring(0, 500)) }}</div>
                  </div>
                </div>
                <!-- 校对结果展示 -->
                <div class="detail-round-evaluation" v-if="subTask.evaluation">
                  <div class="evaluation-badge" :class="{ correct: subTask.evaluation.is_correct, incorrect: !subTask.evaluation.is_correct }">
                    <span class="evaluation-icon">{{ subTask.evaluation.is_correct ? '✓' : '✗' }}</span>
                    <span class="evaluation-label">校对结果:</span>
                    <span class="evaluation-rate">{{ subTask.evaluation.rate }}/10</span>
                  </div>
                  <div class="evaluation-reason" v-if="subTask.evaluation.reason">
                    {{ subTask.evaluation.reason }}
                  </div>
                </div>
                <div class="detail-round-error" v-if="subTask.status === 'error'">
                  错误: {{ subTask.error || '未知错误' }}
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="form-actions">
          <button class="btn btn-secondary" @click="hideTaskDetail">关闭</button>
        </div>
      </div>
    </div>

    <!-- 卡片展开动画过渡元素 -->
    <div 
      class="card-expand-transition"
      :class="{ visible: expandTransition.visible }"
      :style="expandTransition.style"
    >
      <div class="transition-content">
        <div class="transition-header">
          <span class="transition-model">{{ expandTransition.model_name }}</span>
          <span class="transition-case">{{ expandTransition.case_name }}</span>
        </div>
        <div class="transition-progress">
          <div class="transition-progress-bar">
            <div class="transition-progress-fill" :style="{ width: expandTransition.progress + '%' }"></div>
          </div>
          <span class="transition-progress-text">{{ expandTransition.progress }}%</span>
        </div>
        <div class="transition-stats" v-if="expandTransition.stats">
          <div class="transition-stat">
            <span class="transition-stat-value">{{ expandTransition.stats.avgTtft || '--' }}s</span>
            <span class="transition-stat-label">TTFT</span>
          </div>
          <div class="transition-stat">
            <span class="transition-stat-value">{{ expandTransition.stats.avgSpeed || '--' }}</span>
            <span class="transition-stat-label">速度/s</span>
          </div>
          <div class="transition-stat">
            <span class="transition-stat-value">{{ expandTransition.stats.doneCount || 0 }}/{{ expandTransition.stats.totalRounds || 0 }}</span>
            <span class="transition-stat-label">完成</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史记录 Modal -->
    <div class="modal-overlay" :class="{ show: historyVisible }" @click.self="hideHistoryModal">
      <div class="modal history-modal">
        <div class="modal-title">测试历史记录</div>
        <div class="modal-body">
          <div class="history-list" v-if="historyList.length">
            <div 
              v-for="group in historyList" 
              :key="group.group_id"
              class="history-item"
              @click="viewHistoryDetail(group.group_id)"
            >
              <div class="history-info">
                <div class="history-name">{{ group.name || group.group_id }}</div>
                <div class="history-meta">
                  {{ formatDate(group.start_time) }} • {{ group.config?.models?.length || 0 }} 模型 × {{ group.config?.test_cases?.length || 0 }} 测试用例 • {{ group.total_rounds || 0 }} 轮
                </div>
              </div>
              <div class="history-stats">
                <div class="history-stat">
                  <div class="history-stat-value">{{ group.completed_rounds || 0 }}</div>
                  <div class="history-stat-label">完成</div>
                </div>
                <div class="history-stat">
                  <div class="history-stat-value" style="color:var(--primary)">{{ group.success_count || 0 }}</div>
                  <div class="history-stat-label">成功</div>
                </div>
                <div class="history-stat">
                  <div class="history-stat-value" style="color:var(--accent-red)">{{ group.failed_count || 0 }}</div>
                  <div class="history-stat-label">失败</div>
                </div>
              </div>
              <div class="history-actions">
                <button class="btn btn-secondary" style="padding:6px 12px;font-size:0.65rem" @click.stop="deleteHistory(group.group_id)">删除</button>
              </div>
            </div>
          </div>
          <div v-else style="color:var(--gray-500);text-align:center;padding:20px;">暂无历史记录</div>
        </div>
        <div class="form-actions">
          <button class="btn btn-secondary" @click="hideHistoryModal">关闭</button>
        </div>
      </div>
    </div>

    <!-- 模型 Popover -->
    <div 
      class="model-popover" 
      :class="{ visible: modelPopoverVisible }"
      :style="{ left: modelPopoverX + 'px', top: modelPopoverY + 'px' }"
    >
      <div class="model-popover-title">{{ modelPopoverData.display_name || modelPopoverData.name }}</div>
      <div class="model-popover-content" v-if="modelPopoverData">
        <div class="model-popover-row" v-if="modelPopoverData.publisher">
          <span class="model-popover-label">发布者:</span>
          <span class="model-popover-value">{{ modelPopoverData.publisher }}</span>
        </div>
        <div class="model-popover-row" v-if="modelPopoverData.architecture">
          <span class="model-popover-label">架构:</span>
          <span class="model-popover-value">{{ modelPopoverData.architecture }}</span>
        </div>
        <div class="model-popover-row" v-if="modelPopoverData.params_string">
          <span class="model-popover-label">参数:</span>
          <span class="model-popover-value">{{ modelPopoverData.params_string }}</span>
        </div>
        <div class="model-popover-row" v-if="modelPopoverData.quantization">
          <span class="model-popover-label">量化:</span>
          <span class="model-popover-value">{{ modelPopoverData.quantization.name }} ({{ modelPopoverData.quantization.bits_per_weight }}bit)</span>
        </div>
        <div class="model-popover-row" v-if="modelPopoverData.max_context_length">
          <span class="model-popover-label">上下文:</span>
          <span class="model-popover-value">{{ modelPopoverData.max_context_length.toLocaleString() }} tokens</span>
        </div>
        <div class="model-popover-row" v-if="modelPopoverData.size_bytes">
          <span class="model-popover-label">大小:</span>
          <span class="model-popover-value">{{ formatBytes(modelPopoverData.size_bytes) }}</span>
        </div>
        <div class="model-popover-row" v-if="modelPopoverData.format">
          <span class="model-popover-label">格式:</span>
          <span class="model-popover-value">{{ modelPopoverData.format }}</span>
        </div>
        <div class="model-popover-row" v-if="modelPopoverData.key">
          <span class="model-popover-label">Key:</span>
          <span class="model-popover-value" style="font-size: 0.55rem; word-break: break-all;">{{ modelPopoverData.key }}</span>
        </div>
      </div>
    </div>

    <!-- 轮次 Popover -->
    <div 
      class="round-popover" 
      :class="{ visible: popoverVisible }"
      :style="{ left: popoverX + 'px', top: popoverY + 'px' }"
    >
      <div class="round-popover-header">
        {{ popoverData.name }}
        <span v-if="popoverData.status === 'running'" style="animation: blink 1s infinite;"> ▌</span>
        <span v-else-if="popoverData.status === 'done'"> ✓</span>
        <span v-else-if="popoverData.status === 'error'"> ✗</span>
      </div>
      <div v-if="popoverData.metrics" style="font-size: 0.6rem; color: var(--primary); margin-bottom: 6px;">
        {{ popoverData.metrics }}
      </div>
      <div v-if="popoverData.status === 'pending'" class="round-popover-loading">
        <div class="loading-spinner"></div>等待中...
      </div>
      <div v-else-if="popoverData.output" class="round-popover-content">{{ popoverData.output }}</div>
      <div v-else style="color: var(--gray-500)">无输出</div>
    </div>

    <!-- Test Case Popover -->
    <div 
      class="case-popover" 
      :class="{ visible: casePopoverVisible }"
      :style="{ left: casePopoverX + 'px', top: casePopoverY + 'px' }"
    >
      <div class="case-popover-title">{{ casePopoverData.name }}</div>
      <div class="case-popover-content" v-if="casePopoverData">
        <div class="case-popover-row" v-if="casePopoverData.id">
          <span class="case-popover-label">ID:</span>
          <span class="case-popover-value">{{ casePopoverData.id }}</span>
        </div>
        <div class="case-popover-row" v-if="casePopoverData.prompt">
          <span class="case-popover-label">Prompt:</span>
          <span class="case-popover-value" style="white-space: pre-wrap; max-height: 100px; overflow-y: auto;">{{ casePopoverData.prompt.substring(0, 200) }}{{ casePopoverData.prompt.length > 200 ? '...' : '' }}</span>
        </div>
        <div class="case-popover-row" v-if="casePopoverData.max_tokens">
          <span class="case-popover-label">Max Tokens:</span>
          <span class="case-popover-value">{{ casePopoverData.max_tokens }}</span>
        </div>
        <div class="case-popover-row" v-if="casePopoverData.temperature">
          <span class="case-popover-label">Temperature:</span>
          <span class="case-popover-value">{{ casePopoverData.temperature }}</span>
        </div>
      </div>
    </div>

    <!-- Toast -->
      <div class="toast" :class="{ show: toastVisible, [toastType]: true }">{{ toastMessage }}</div>

    <!-- AI 分析结果 Modal -->
    <div class="ai-analysis-overlay" v-if="showAiAnalysis" @click.self="closeAiAnalysis">
      <div class="ai-analysis-modal">
        <div class="ai-analysis-header">
          <div class="ai-analysis-title">
            <span class="ai-analysis-title-icon">🤖</span>
            <span>MiniMax M2.7 分析报告</span>
          </div>
          <div class="ai-analysis-actions">
            <button class="ai-btn" @click="copyAiReport" :disabled="!aiAnalysisContent" title="复制报告">📋 复制</button>
            <button class="ai-analysis-close" @click="closeAiAnalysis" title="关闭">✕</button>
          </div>
        </div>
        <div class="ai-analysis-body" ref="aiReportContainer">
          <div v-if="aiAnalysisLoading && !aiAnalysisContent" class="ai-loading-state">
            <div class="ai-loading-spinner"></div>
            <div class="ai-loading-text">正在连接 MiniMax M2.7 进行分析...</div>
          </div>
          <div v-if="aiAnalysisError" class="ai-error-state">
            <div class="ai-error-icon">⚠️</div>
            <div class="ai-error-text">{{ aiAnalysisError }}</div>
          </div>
          <div class="ai-report-container" v-html="renderedAiReport" v-if="aiAnalysisContent"></div>
        </div>
        <div class="ai-analysis-footer">
          <span class="ai-analysis-status" v-if="aiAnalysisContent && !aiAnalysisLoading">✓ 分析完成</span>
          <span class="ai-analysis-status" v-else-if="aiAnalysisLoading">⏳ 流式接收中...</span>
          <span class="ai-analysis-status" v-else>等待中...</span>
        </div>
      </div>
    </div>
  </div>
  </template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'

// ===== 状态 =====
const config = ref<any>(null)
const isFullscreen = ref(false)
const sseConnected = ref(false)
const sseStatus = ref('--')
const testRunning = ref(false)
const testStatus = ref('IDLE')

// 任务卡片拖拽排序状态
const cardDragState = reactive({
  isDragging: false,
  draggingCardId: null as string | null,
  startX: 0,
  startY: 0,
  currentX: 0,
  currentY: 0,
  startIndex: -1,
  currentIndex: -1,
  placeholderIndex: -1
})

// 任务卡片尺寸状态
const cardResizeState = reactive({
  isResizing: false,
  resizingCardId: null as string | null,
  direction: '' as string,
  startX: 0,
  startY: 0,
  startWidth: 0,
  startHeight: 0
})

// 任务卡片位置和尺寸（持久化）
const cardPositions = ref<Record<string, { order: number, width: number, height: number }>>({})

// 任务卡片排序列表
const taskOrder = ref<string[]>([])
const MIN_CARD_WIDTH = 280
const MAX_CARD_WIDTH = 600
const MIN_CARD_HEIGHT = 180
const MAX_CARD_HEIGHT = 500

// 侧边栏宽度控制
const sidebarWidth = ref(400)
const isDragging = ref(false)
const isCollapsed = ref(false)
const wasCollapsedBeforeDrag = ref(false)  // 拖拽开始前的状态
const COLLAPSED_WIDTH = 24  // 折叠后的宽度（只留拖拽把手）
const EXPAND_TRIGGER = 120  // 展开触发的宽度阈值
const AUTO_COLLAPSE_WIDTH = 300  // 窗口宽度小于此值时自动折叠

// 浮动日志面板控制
const logMinimized = ref(false)
const logPanelX = ref(20)
const logPanelY = ref(window.innerHeight - 220)  // 默认距离底部220px
const logPanelWidth = ref(600)
const logPanelHeight = ref(200)
const isLogPanelDragging = ref(false)
const isLogResizing = ref(false)
const MIN_LOG_PANEL_WIDTH = 300
const MIN_LOG_PANEL_HEIGHT = 100
const MAX_LOG_PANEL_HEIGHT = 800
const MAX_LOG_PANEL_WIDTH = 1200
const MIN_LOG_PANEL_Y = 40  // 最小距离顶部的距离
const MAX_LOG_PANEL_Y = window.innerHeight - 100  // 最大距离顶部的距离

// 计算属性：是否正在调整大小（任意方向）
const isLogResizingAny = computed(() => isLogResizing.value)

// 计算日志面板样式
const logPanelStyle = computed(() => ({
  position: 'fixed',
  left: logPanelX.value + 'px',
  top: logPanelY.value + 'px',  // 使用 top 属性，使拖拽方向正确
  width: logPanelWidth.value + 'px',
  height: logMinimized.value ? 'auto' : logPanelHeight.value + 'px',
  zIndex: 50,
  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
  borderRadius: logMinimized.value ? '50%' : '12px'
}))

// 排序
const sortBy = ref('default')

// 任务数据
interface SubTask {
  name: string
  output: string
  status: string
  metrics: any
  prompt?: string
  error?: string
  think_content?: string  // 思考内容
  answer_content?: string // 回答内容
}

interface Task {
  model_name: string
  case_name: string
  progress: number
  status: string
  current_round: number
  total_rounds: number
  sub_tasks: Record<string, SubTask>
  avgTtft?: string
  avgTpft?: string
  avgTokens?: string
  avgSpeed?: string
  avgAnswerSpeed?: string
  avgThinkTokens?: string
  avgAnswerTokens?: string
  expanded?: boolean  // 展开状态
  startTime?: number  // 任务开始时间（Unix 时间戳秒）
  duration?: number   // 任务总耗时（秒），任务完成后设置
}

const tasks = ref<Record<string, Task>>({})
const selectedModels = ref<Set<string>>(new Set())
const selectedCases = ref<Set<string>>(new Set())
const activeSubTask = ref<Record<string, number>>({})

// 日志
interface Log {
  time: string
  fullTime: string
  tag: string
  msg: string
  isNew: boolean
}
const logs = ref<Log[]>([])

// 日志控制状态
const logSearchText = ref('')
const logFilter = ref<'all' | 'error' | 'running'>('all')
const logAutoScroll = ref(true)
const logSearchActive = ref(false)
const logAreaRef = ref<HTMLElement | null>(null)

// 过滤后的日志
const filteredLogs = computed(() => {
  let result = logs.value
  
  // 按过滤类型筛选
  if (logFilter.value === 'error') {
    result = result.filter(log => 
      log.tag.toLowerCase() === 'error' || 
      log.tag.toLowerCase() === 'stop'
    )
  } else if (logFilter.value === 'running') {
    result = result.filter(log => 
      log.tag.toLowerCase() === 'round' || 
      log.tag.toLowerCase() === 'start' ||
      log.tag.toLowerCase() === 'retry' ||
      log.tag.toLowerCase() === 'chunk'
    )
  }
  
  // 按搜索文本筛选
  if (logSearchText.value) {
    const searchLower = logSearchText.value.toLowerCase()
    result = result.filter(log => 
      log.msg.toLowerCase().includes(searchLower) ||
      log.tag.toLowerCase().includes(searchLower)
    )
  }
  
  return result
})

// 获取日志级别样式类
function getLogLevelClass(tag: string): string {
  const tagLower = tag.toLowerCase()
  if (tagLower === 'error') return 'level-error'
  if (tagLower === 'stop') return 'level-warning'
  if (tagLower === 'done' || tagLower === 'finish') return 'level-success'
  if (tagLower === 'round') return 'level-running'
  if (tagLower === 'start' || tagLower === 'retry') return 'level-info'
  if (tagLower === 'summary') return 'level-success'
  if (tagLower === 'chunk') return 'level-running'
  return 'level-default'
}

// 清除日志
function clearLogs() {
  logs.value = []
  showToast('日志已清除', 'success')
}

// 导出日志
function exportLogs() {
  const content = logs.value
    .map(log => `[${log.fullTime}] [${log.tag}] ${log.msg}`)
    .join('\n')
  
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `logs_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
  link.click()
  URL.revokeObjectURL(url)
  
  showToast('日志已导出', 'success')
}

// 复制单条日志
function copyLog(log: Log) {
  const text = `[${log.fullTime}] [${log.tag}] ${log.msg}`
  navigator.clipboard.writeText(text).then(() => {
    showToast('已复制到剪贴板', 'success')
  }).catch(() => {
    showToast('复制失败', 'error')
  })
}

// 自动滚动到底部
function scrollToBottom() {
  if (logAutoScroll.value && logAreaRef.value) {
    nextTick(() => {
      logAreaRef.value!.scrollTop = logAreaRef.value!.scrollHeight
    })
  }
}

// Modal 状态
const modalVisible = ref(false)
const modalType = ref<'model' | 'case'>('model')
const modelForm = reactive({
  name: '',
  endpoint: '',
  api_key: '',
  model: '',
  temperature: 0.7,
  top_p: 1.0,
  max_tokens: 4096,
  presence_penalty: 0.0,
  frequency_penalty: 0.0,
  thinking_enabled: true
})
const caseForm = reactive({
  name: '',
  messages: [
    { role: 'user', content: '' }
  ],
  max_tokens: 500,
  expected_output: '',  // 标准答案（用于质量评估）
  eval_model: ''        // 校对模型名称
})

// 启动配置
const startConfigVisible = ref(false)
const startConfig = reactive({
  test_rounds: 30,
  max_concurrent: 0,
  interval: 0.1,
  test_name: ''
})

// 任务详情
const taskDetailVisible = ref(false)
const taskDetailData = ref<any>({})

// 历史记录
const historyVisible = ref(false)
const historyList = ref<any[]>([])

// Popover
const popoverVisible = ref(false)
const popoverX = ref(0)
const popoverY = ref(0)
const popoverData = ref<any>({})

// 模型 Popover
const modelPopoverVisible = ref(false)
const modelPopoverX = ref(0)
const modelPopoverY = ref(0)
const modelPopoverData = ref<any>({})

// Toast
const toastVisible = ref(false)
const toastMessage = ref('')
const toastType = ref('')

// AI 分析
const showAiAnalysis = ref(false)
const aiAnalysisLoading = ref(false)
const aiAnalysisContent = ref('')
const aiAnalysisError = ref('')
const aiReportContainer = ref<HTMLElement | null>(null)
let aiEventSource: EventSource | null = null

const renderedAiReport = computed(() => {
  if (!aiAnalysisContent.value) return ''
  return formatMarkdown(aiAnalysisContent.value)
})

function formatMarkdown(text: string): string {
  let html = text
    .replace(/&/g, '&')
    .replace(/</g, '<')
    .replace(/>/g, '>')
  
  // 代码块 ```...```
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="ai-code-block"><code>$2</code></pre>')
  
  // 行内代码 `...`
  html = html.replace(/`([^`]+)`/g, '<code class="ai-inline-code">$1</code>')
  
  // 粗体 **...**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  
  // 斜体 *...*
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  
  // 标题 ###, ##, #
  html = html.replace(/^### (.+)$/gm, '<h3 class="ai-h3">$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2 class="ai-h2">$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1 class="ai-h1">$1</h1>')
  
  // 水平线 ---
  html = html.replace(/^---$/gm, '<hr class="ai-hr">')
  
  // 无序列表
  html = html.replace(/^- (.+)$/gm, '<li class="ai-li">$1</li>')
  
  // 换行
  html = html.replace(/\n\n/g, '</p><p class="ai-p">')
  html = html.replace(/\n/g, '<br>')
  
  html = '<p class="ai-p">' + html + '</p>'
  
  return html
}

function toggleAiAnalysis() {
  if (aiAnalysisLoading.value) return
  if (showAiAnalysis.value) {
    closeAiAnalysis()
    return
  }
  openAiAnalysis()
}

function openAiAnalysis() {
  showAiAnalysis.value = true
  aiAnalysisLoading.value = true
  aiAnalysisContent.value = ''
  aiAnalysisError.value = ''
  
  const baseUrl = window.location.origin
  const url = `${baseUrl}/api/analysis`
  
  aiEventSource = new EventSource(url)
  
  aiEventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.content) {
        aiAnalysisContent.value += data.content
        // 自动滚动到底部
        nextTick(() => {
          if (aiReportContainer.value) {
            aiReportContainer.value.scrollTop = aiReportContainer.value.scrollHeight
          }
        })
      }
      if (data.done) {
        aiAnalysisLoading.value = false
        aiEventSource?.close()
        aiEventSource = null
      }
      if (data.error) {
        aiAnalysisError.value = data.error
        aiAnalysisLoading.value = false
        aiEventSource?.close()
        aiEventSource = null
      }
    } catch (e) {
      // 非 JSON 数据，可能是纯文本
      aiAnalysisContent.value += event.data
    }
  }
  
  aiEventSource.onerror = () => {
    aiAnalysisError.value = 'SSE 连接失败或中断，请检查后端服务是否运行'
    aiAnalysisLoading.value = false
    aiEventSource?.close()
    aiEventSource = null
  }
}

function closeAiAnalysis() {
  if (aiEventSource) {
    aiEventSource.close()
    aiEventSource = null
  }
  showAiAnalysis.value = false
  aiAnalysisLoading.value = false
}

function copyAiReport() {
  if (!aiAnalysisContent.value) return
  navigator.clipboard.writeText(aiAnalysisContent.value).then(() => {
    showToast('报告已复制到剪贴板', 'success')
  }).catch(() => {
    showToast('复制失败，请手动选择复制', 'error')
  })
}

// 卡片展开动画
const isAnimating = ref(false)
const expandTransition = reactive({
  visible: false,
  style: {} as Record<string, string>,
  model_name: '',
  case_name: '',
  progress: 0,
  stats: null as any,
  cardRect: { left: 0, top: 0, width: 0, height: 0 }
})

let eventSource: EventSource | null = null

// ===== 计算属性 =====
const taskCount = computed(() => Object.keys(tasks.value).length)

const isEditing = computed(() => {
  return currentEditCaseId.value !== null || currentEditModelName.value !== null
})

function doneCount(task: Task): number {
  return Object.values(task.sub_tasks || {}).filter(t => t.status === 'done').length
}

function runningCount(task: Task): number {
  return Object.values(task.sub_tasks || {}).filter(t => t.status === 'running').length
}

function errorCount(task: Task): number {
  return Object.values(task.sub_tasks || {}).filter(t => t.status === 'error').length
}

function isAllDone(task: Task): boolean {
  const subTasks = Object.values(task.sub_tasks || {})
  return subTasks.length > 0 && subTasks.every(t => t.status === 'done' || t.status === 'error')
}

// 排序功能
function sortTasks() {
  // Vue的响应式会自动更新视图，这里保留接口即可
  // 实际排序在模板中通过computed处理
  console.log('Sort by:', sortBy.value)
}

// ===== 工具函数 =====

/**
 * 解析思考内容 - 支持多种标记方式
 * 支持格式：
 * 1.<think>...</think> 格式
 * 2.<think>...</think> 格式  
 * 3. [[模型分析]]...[[/模型分析]] 格式
 * 4. THINK: ... ANSWER: ... 格式
 * 5. 思考过程：... 最终答案：... 格式
 * 6. reasoning 字段（非流式响应）
 */
function extractThinkAndAnswer(content: string): { think: string; answer: string } {
  if (!content) return { think: '', answer: content }
  
  let think = ''
  let answer = content
  
  // 1. 去除 <think>...</think> 格式
  const thinkMatch1 = content.match(/<think>\s*([\s\S]*?)\s*<\/think>/gi)
  if (thinkMatch1) {
    think = thinkMatch1.map(m => m.replace(/<think>\s*/gi, '').replace(/\s*<\/think>/gi, '')).join('\n')
    answer = content.replace(/<think>\s*[\s\S]*?\s*<\/think>/gi, '').trim()
  }
  
  // 2. 去除 <think>...</think> 格式
  const thinkMatch2 = content.match(/<think>\s*([\s\S]*?)\s*<\/think>/gi)
  if (thinkMatch2) {
    think = thinkMatch2.map(m => m.replace(/<think>\s*/gi, '').replace(/\s*<\/think>/gi, '')).join('\n')
    answer = answer.replace(/<think>\s*[\s\S]*?\s*<\/think>/gi, '').trim()
  }
  
  // 3. 去除 [[模型分析]]...[[/模型分析]] 格式
  const thinkMatch3 = content.match(/\[\[模型分析\]\]\s*([\s\S]*?)\s*\[\[\/模型分析\]\]/gi)
  if (thinkMatch3) {
    think = thinkMatch3.map(m => m.replace(/\[\[模型分析\]\]\s*/gi, '').replace(/\s*\[\[\/模型分析\]\]/gi, '')).join('\n')
    answer = answer.replace(/\[\[模型分析\]\]\s*[\s\S]*?\s*\[\[\/模型分析\]\]/gi, '').trim()
  }
  
  // 4. 去除 THINK: ... ANSWER: ... 格式中的 THINK 部分
  const thinkMatch4 = content.match(/THINK:\s*([\s\S]*?)(?=ANSWER:|$)/gi)
  if (thinkMatch4) {
    think = thinkMatch4.map(m => m.replace(/THINK:\s*/gi, '')).join('\n')
    answer = answer.replace(/THINK:\s*[\s\S]*?(?=ANSWER:|$)/gi, '').replace(/^ANSWER:\s*/i, '').trim()
  }
  
  // 5. 去除 思考: ... 答案: ... 格式中的思考部分
  const thinkMatch5 = content.match(/思考[：:]\s*([\s\S]*?)(?=答案[：:]|最终答案[：:]|回答[：:]|输出[：:])/gi)
  if (thinkMatch5) {
    think = thinkMatch5.map(m => m.replace(/思考[：:]\s*/gi, '')).join('\n')
    answer = answer.replace(/思考[：:]\s*[\s\S]*?(?=答案[：:]|最终答案[：:]|回答[：:]|输出[：:])/gi, '').trim()
  }
  
  // 清理多余空白
  think = think.replace(/\n{3,}/g, '\n\n').trim()
  answer = answer.replace(/\n{3,}/g, '\n\n').trim()
  
  return { think, answer }
}
function getTaskId(modelName: string, caseName: string): string {
  return `${modelName}__${caseName}`
}

function getSubTaskId(modelName: string, caseName: string, round: number): string {
  return `${modelName}__${caseName}__${round}`
}

function getSubTaskIndex(task: Task, subId: string): number {
  const keys = Object.keys(task.sub_tasks)
  return keys.indexOf(subId)
}

function getGridColumns(totalRounds: number): number {
  if (totalRounds <= 10) return 7
  if (totalRounds <= 50) {
    return Math.round(7 + (totalRounds - 10) * (20 - 7) / (50 - 10))
  }
  return Math.round(20 + (Math.min(totalRounds, 100) - 50) * (30 - 20) / (100 - 50))
}

function getFontSize(totalRounds: number): string {
  if (totalRounds <= 10) return '0.6rem'
  if (totalRounds <= 20) return '0.55rem'
  if (totalRounds <= 30) return '0.5rem'
  if (totalRounds <= 50) return '0.45rem'
  return '0.4rem'
}

// 实时更新时间
const now = ref(Date.now() / 1000)
let timer: number | null = null

onMounted(() => {
  // 每秒更新时间
  timer = window.setInterval(() => {
    now.value = Date.now() / 1000
  }, 1000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})

// 计算任务的显示耗时
function getTaskDuration(task: Task): number {
  if (task.status === 'done' && task.duration) {
    // 任务完成时显示最终耗时
    return task.duration
  }
  // 运行中或停止时，计算已用时间
  if (task.startTime) {
    return now.value - task.startTime
  }
  return 0
}

// 格式化耗时
function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return '--'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  if (mins > 0) {
    return `${mins}分${secs}秒`
  }
  return `${secs}秒`
}

// 判断是否使用圆点模式（超过80轮时）
function useDotMode(totalRounds: number): boolean {
  return totalRounds > 80
}

// 计算校对准确率
function getEvalAccuracy(task: any): string {
  const correct = task.evalCorrectCount || 0
  const incorrect = task.evalIncorrectCount || 0
  const total = correct + incorrect
  if (total === 0) return '0'
  return ((correct / total) * 100).toFixed(1)
}

function getRoundStatusIcon(status: string, roundNum: number, totalRounds: number = 0): string {
  // 超过80轮时使用圆点模式，不显示字符
  if (useDotMode(totalRounds)) {
    return ''
  }
  if (status === 'done') return '✓'
  if (status === 'error') return '✗'
  if (status === 'running') return '⟳'
  return roundNum
}

function trimText(text: string): string {
  if (!text) return ''
  return text.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim()
}

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '--'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatBytes(bytes: number): string {
  if (!bytes) return '--'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let unitIndex = 0
  let size = bytes
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return size.toFixed(1) + ' ' + units[unitIndex]
}

// 全屏
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

// 侧边栏拖拽
function startDrag(e: MouseEvent) {
  // 记录拖拽开始前的状态
  wasCollapsedBeforeDrag.value = isCollapsed.value
  isDragging.value = true
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()
}

// 侧边栏自动折叠/展开逻辑
function checkCollapseState(width: number, fromCollapsed: boolean) {
  // 如果从收起状态拖动
  if (fromCollapsed) {
    // 拖到超过120px就展开到400px
    if (width > EXPAND_TRIGGER) {
      isCollapsed.value = false
      sidebarWidth.value = 400
    }
    // 否则保持收起状态
    else {
      isCollapsed.value = true
      sidebarWidth.value = COLLAPSED_WIDTH
    }
  } 
  // 如果从展开状态拖动
  else {
    // 宽度小于等于自动折叠阈值，则折叠
    if (width <= AUTO_COLLAPSE_WIDTH) {
      isCollapsed.value = true
      sidebarWidth.value = COLLAPSED_WIDTH
    }
    // 展开超过120px但没到400px，自动弹开到400px
    else if (width > EXPAND_TRIGGER && width < 400) {
      sidebarWidth.value = 400
    }
    // 否则保持展开状态（不改变isCollapsed）
  }
}

function onDrag(e: MouseEvent) {
  if (!isDragging.value) return
  const newWidth = e.clientX
  // 限制最小和最大宽度
  const minWidth = isCollapsed.value ? COLLAPSED_WIDTH : 60
  const maxWidth = window.innerWidth - 300
  
  // 如果正在展开过程中，使用较大最小值
  const actualMinWidth = isCollapsed.value ? COLLAPSED_WIDTH : 60
  
  sidebarWidth.value = Math.max(actualMinWidth, Math.min(maxWidth, newWidth))
}

function stopDrag() {
  // 鼠标放开后检查是否需要自动折叠/展开，传入拖拽开始前的状态
  checkCollapseState(sidebarWidth.value, wasCollapsedBeforeDrag.value)
  
  // 保存折叠状态到 localStorage
  localStorage.setItem('sidebarCollapsed', String(isCollapsed.value))
  localStorage.setItem('sidebarWidth', String(sidebarWidth.value))
  
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 切换侧边栏展开/折叠
function toggleSidebar() {
  if (isCollapsed.value) {
    // 当前是收起状态，点击展开
    isCollapsed.value = false
    sidebarWidth.value = 400
  } else {
    // 当前是展开状态，点击收起
    isCollapsed.value = true
    sidebarWidth.value = COLLAPSED_WIDTH
  }
  // 保存折叠状态到 localStorage
  localStorage.setItem('sidebarCollapsed', String(isCollapsed.value))
  localStorage.setItem('sidebarWidth', String(sidebarWidth.value))
}

// 浮动日志面板拖拽 - 优化版本，使用 transform 提升性能
let logPanelDragStartX = 0
let logPanelDragStartY = 0
let logPanelStartX = 0
let logPanelStartY = 0
let logPanelDraggingEl: HTMLElement | null = null
let logPanelDragOffsetX = 0
let logPanelDragOffsetY = 0

function startLogPanelDrag(e: MouseEvent) {
  // 不允许拖拽带有输入焦点的元素
  if ((e.target as HTMLElement).tagName === 'INPUT') return
  
  const panel = document.querySelector('.log-panel') as HTMLElement
  if (!panel) return
  
  isLogPanelDragging.value = true
  logPanelDragStartX = e.clientX
  logPanelDragStartY = e.clientY
  logPanelStartX = logPanelX.value
  logPanelStartY = logPanelY.value
  
  // 使用 transform 提升性能
  panel.style.transition = 'none'
  panel.style.zIndex = '1000'
  
  // 添加全局事件监听
  document.addEventListener('mousemove', onLogPanelDrag, { passive: false })
  document.addEventListener('mouseup', stopLogPanelDrag, { passive: true })
  e.preventDefault()
}

function onLogPanelDrag(e: MouseEvent) {
  if (!isLogPanelDragging.value) return
  
  // 使用 requestAnimationFrame 优化性能
  requestAnimationFrame(() => {
    const deltaX = e.clientX - logPanelDragStartX
    const deltaY = e.clientY - logPanelDragStartY
    
    // 更新面板位置 - 使用 top 属性，方向正确
    const newX = Math.max(0, Math.min(window.innerWidth - logPanelWidth.value - 20, logPanelStartX + deltaX))
    const newY = Math.max(MIN_LOG_PANEL_Y, Math.min(MAX_LOG_PANEL_Y, logPanelStartY + deltaY))
    
    logPanelX.value = newX
    logPanelY.value = newY
  })
}

function stopLogPanelDrag() {
  isLogPanelDragging.value = false
  
  // 恢复面板样式
  const panel = document.querySelector('.log-panel') as HTMLElement
  if (panel) {
    panel.style.transition = ''
    panel.style.zIndex = '50'
  }
  
  document.removeEventListener('mousemove', onLogPanelDrag)
  document.removeEventListener('mouseup', stopLogPanelDrag)
}

// 浮动日志面板大小调整
let logResizeStartY = 0
let logResizeStartHeight = 0

function startLogResize(e: MouseEvent) {
  isLogResizing.value = true
  logResizeStartY = e.clientY
  logResizeStartHeight = logPanelHeight.value
  
  document.addEventListener('mousemove', onLogResize)
  document.addEventListener('mouseup', stopLogResize)
  e.preventDefault()
}

function onLogResize(e: MouseEvent) {
  if (!isLogResizing.value) return
  
  const deltaY = e.clientY - logResizeStartY
  const newHeight = Math.max(MIN_LOG_PANEL_HEIGHT, Math.min(MAX_LOG_PANEL_HEIGHT, logResizeStartHeight + deltaY))
  
  logPanelHeight.value = newHeight
}

function stopLogResize() {
  isLogResizing.value = false
  document.removeEventListener('mousemove', onLogResize)
  document.removeEventListener('mouseup', stopLogResize)
}

// 顶部 resize
let logResizeTopStartY = 0
let logResizeTopStartHeight = 0

function startLogResizeTop(e: MouseEvent) {
  isLogResizing.value = true
  logResizeTopStartY = e.clientY
  logResizeTopStartHeight = logPanelHeight.value
  
  document.addEventListener('mousemove', onLogResizeTop)
  document.addEventListener('mouseup', stopLogResizeTop)
  e.preventDefault()
}

function onLogResizeTop(e: MouseEvent) {
  if (!isLogResizing.value) return
  
  const deltaY = logResizeTopStartY - e.clientY  // 反向：向上拖动时 deltaY 为正
  const newHeight = Math.max(MIN_LOG_PANEL_HEIGHT, Math.min(MAX_LOG_PANEL_HEIGHT, logResizeTopStartHeight + deltaY))
  
  logPanelHeight.value = newHeight
}

function stopLogResizeTop() {
  isLogResizing.value = false
  document.removeEventListener('mousemove', onLogResizeTop)
  document.removeEventListener('mouseup', stopLogResizeTop)
}

// 底部 resize
let logResizeBottomStartY = 0
let logResizeBottomStartHeight = 0

function startLogResizeBottom(e: MouseEvent) {
  isLogResizing.value = true
  logResizeBottomStartY = e.clientY
  logResizeBottomStartHeight = logPanelHeight.value
  
  document.addEventListener('mousemove', onLogResizeBottom)
  document.addEventListener('mouseup', stopLogResizeBottom)
  e.preventDefault()
}

function onLogResizeBottom(e: MouseEvent) {
  if (!isLogResizing.value) return
  
  const deltaY = e.clientY - logResizeBottomStartY
  const newHeight = Math.max(MIN_LOG_PANEL_HEIGHT, Math.min(MAX_LOG_PANEL_HEIGHT, logResizeBottomStartHeight + deltaY))
  
  logPanelHeight.value = newHeight
}

function stopLogResizeBottom() {
  isLogResizing.value = false
  document.removeEventListener('mousemove', onLogResizeBottom)
  document.removeEventListener('mouseup', stopLogResizeBottom)
}

// 左侧 resize
let logResizeLeftStartX = 0
let logResizeLeftStartWidth = 0

function startLogResizeLeft(e: MouseEvent) {
  isLogResizing.value = true
  logResizeLeftStartX = e.clientX
  logResizeLeftStartWidth = logPanelWidth.value
  
  document.addEventListener('mousemove', onLogResizeLeft)
  document.addEventListener('mouseup', stopLogResizeLeft)
  e.preventDefault()
}

function onLogResizeLeft(e: MouseEvent) {
  if (!isLogResizing.value) return
  
  const deltaX = logResizeLeftStartX - e.clientX  // 向左拖动时 deltaX 为正
  const newWidth = Math.max(MIN_LOG_PANEL_WIDTH, Math.min(MAX_LOG_PANEL_WIDTH, logResizeLeftStartWidth + deltaX))
  
  logPanelWidth.value = newWidth
}

function stopLogResizeLeft() {
  isLogResizing.value = false
  document.removeEventListener('mousemove', onLogResizeLeft)
  document.removeEventListener('mouseup', stopLogResizeLeft)
}

// 右侧 resize
let logResizeRightStartX = 0
let logResizeRightStartWidth = 0

function startLogResizeRight(e: MouseEvent) {
  isLogResizing.value = true
  logResizeRightStartX = e.clientX
  logResizeRightStartWidth = logPanelWidth.value
  
  document.addEventListener('mousemove', onLogResizeRight)
  document.addEventListener('mouseup', stopLogResizeRight)
  e.preventDefault()
}

function onLogResizeRight(e: MouseEvent) {
  if (!isLogResizing.value) return
  
  const deltaX = e.clientX - logResizeRightStartX
  const newWidth = Math.max(MIN_LOG_PANEL_WIDTH, Math.min(MAX_LOG_PANEL_WIDTH, logResizeRightStartWidth + deltaX))
  
  logPanelWidth.value = newWidth
}

function stopLogResizeRight() {
  isLogResizing.value = false
  document.removeEventListener('mousemove', onLogResizeRight)
  document.removeEventListener('mouseup', stopLogResizeRight)
}

// 左上角 resize
let logResizeTopLeftStartX = 0
let logResizeTopLeftStartY = 0
let logResizeTopLeftStartWidth = 0
let logResizeTopLeftStartHeight = 0

function startLogResizeTopLeft(e: MouseEvent) {
  isLogResizing.value = true
  logResizeTopLeftStartX = e.clientX
  logResizeTopLeftStartY = e.clientY
  logResizeTopLeftStartWidth = logPanelWidth.value
  logResizeTopLeftStartHeight = logPanelHeight.value
  
  document.addEventListener('mousemove', onLogResizeTopLeft)
  document.addEventListener('mouseup', stopLogResizeTopLeft)
  e.preventDefault()
}

function onLogResizeTopLeft(e: MouseEvent) {
  if (!isLogResizing.value) return
  
  const deltaX = logResizeTopLeftStartX - e.clientX
  const deltaY = logResizeTopLeftStartY - e.clientY
  
  const newWidth = Math.max(MIN_LOG_PANEL_WIDTH, Math.min(MAX_LOG_PANEL_WIDTH, logResizeTopLeftStartWidth + deltaX))
  const newHeight = Math.max(MIN_LOG_PANEL_HEIGHT, Math.min(MAX_LOG_PANEL_HEIGHT, logResizeTopLeftStartHeight + deltaY))
  
  logPanelWidth.value = newWidth
  logPanelHeight.value = newHeight
}

function stopLogResizeTopLeft() {
  isLogResizing.value = false
  document.removeEventListener('mousemove', onLogResizeTopLeft)
  document.removeEventListener('mouseup', stopLogResizeTopLeft)
}

// 右上角 resize
let logResizeTopRightStartX = 0
let logResizeTopRightStartY = 0
let logResizeTopRightStartWidth = 0
let logResizeTopRightStartHeight = 0

function startLogResizeTopRight(e: MouseEvent) {
  isLogResizing.value = true
  logResizeTopRightStartX = e.clientX
  logResizeTopRightStartY = e.clientY
  logResizeTopRightStartWidth = logPanelWidth.value
  logResizeTopRightStartHeight = logPanelHeight.value
  
  document.addEventListener('mousemove', onLogResizeTopRight)
  document.addEventListener('mouseup', stopLogResizeTopRight)
  e.preventDefault()
}

function onLogResizeTopRight(e: MouseEvent) {
  if (!isLogResizing.value) return
  
  const deltaX = e.clientX - logResizeTopRightStartX
  const deltaY = logResizeTopRightStartY - e.clientY
  
  const newWidth = Math.max(MIN_LOG_PANEL_WIDTH, Math.min(MAX_LOG_PANEL_WIDTH, logResizeTopRightStartWidth + deltaX))
  const newHeight = Math.max(MIN_LOG_PANEL_HEIGHT, Math.min(MAX_LOG_PANEL_HEIGHT, logResizeTopRightStartHeight + deltaY))
  
  logPanelWidth.value = newWidth
  logPanelHeight.value = newHeight
}

function stopLogResizeTopRight() {
  isLogResizing.value = false
  document.removeEventListener('mousemove', onLogResizeTopRight)
  document.removeEventListener('mouseup', stopLogResizeTopRight)
}

// 左下角 resize
let logResizeBottomLeftStartX = 0
let logResizeBottomLeftStartY = 0
let logResizeBottomLeftStartWidth = 0
let logResizeBottomLeftStartHeight = 0

function startLogResizeBottomLeft(e: MouseEvent) {
  isLogResizing.value = true
  logResizeBottomLeftStartX = e.clientX
  logResizeBottomLeftStartY = e.clientY
  logResizeBottomLeftStartWidth = logPanelWidth.value
  logResizeBottomLeftStartHeight = logPanelHeight.value
  
  document.addEventListener('mousemove', onLogResizeBottomLeft)
  document.addEventListener('mouseup', stopLogResizeBottomLeft)
  e.preventDefault()
}

function onLogResizeBottomLeft(e: MouseEvent) {
  if (!isLogResizing.value) return
  
  const deltaX = logResizeBottomLeftStartX - e.clientX
  const deltaY = e.clientY - logResizeBottomLeftStartY
  
  const newWidth = Math.max(MIN_LOG_PANEL_WIDTH, Math.min(MAX_LOG_PANEL_WIDTH, logResizeBottomLeftStartWidth + deltaX))
  const newHeight = Math.max(MIN_LOG_PANEL_HEIGHT, Math.min(MAX_LOG_PANEL_HEIGHT, logResizeBottomLeftStartHeight + deltaY))
  
  logPanelWidth.value = newWidth
  logPanelHeight.value = newHeight
}

function stopLogResizeBottomLeft() {
  isLogResizing.value = false
  document.removeEventListener('mousemove', onLogResizeBottomLeft)
  document.removeEventListener('mouseup', stopLogResizeBottomLeft)
}

// Model/Case 选择
function toggleModel(name: string) {
  if (selectedModels.value.has(name)) {
    selectedModels.value.delete(name)
  } else {
    selectedModels.value.add(name)
  }
  localStorage.setItem('selectedModels', JSON.stringify([...selectedModels.value]))
}

function toggleCase(id: string) {
  if (selectedCases.value.has(id)) {
    selectedCases.value.delete(id)
  } else {
    selectedCases.value.add(id)
  }
  localStorage.setItem('selectedCases', JSON.stringify([...selectedCases.value]))
}

function selectAllModels() {
  const models = config.value?.models || []
  if (selectedModels.value.size === models.length) {
    selectedModels.value.clear()
  } else {
    models.forEach((m: any) => selectedModels.value.add(m.name))
  }
  localStorage.setItem('selectedModels', JSON.stringify([...selectedModels.value]))
}

function selectAllCases() {
  const cases = config.value?.test_cases || []
  if (selectedCases.value.size === cases.length) {
    selectedCases.value.clear()
  } else {
    cases.forEach((c: any) => selectedCases.value.add(c.id))
  }
  localStorage.setItem('selectedCases', JSON.stringify([...selectedCases.value]))
}

// Modal
function showModal(type: 'model' | 'case') {
  modalType.value = type
  modalVisible.value = true
  // 清除之前的测试结果
  testResult.value = null
}

function hideModal() {
  modalVisible.value = false
  // 重置表单
  Object.assign(modelForm, { name: '', endpoint: '', api_key: '', model: '' })
  Object.assign(caseForm, { name: '', messages: [{ role: 'user', content: '' }], max_tokens: 500, expected_output: '', eval_model: '' })
  // 重置编辑状态
  currentEditCaseId.value = null
  currentEditModelName.value = null
}

// Messages 编辑器函数
function addMessage() {
  caseForm.messages.push({ role: 'user', content: '' })
}

function removeMessage(index: number) {
  caseForm.messages.splice(index, 1)
}

async function submitModal() {
  // 如果是编辑模式
  if (currentEditModelName.value) {
    const data = {
      name: modelForm.name,  // 使用表单中的新名称
      endpoint: modelForm.endpoint,
      api_key: modelForm.api_key,
      model: modelForm.model,
      enabled: true
    }
    // 使用旧名称作为 URL 参数进行更新
    const oldName = currentEditModelName.value
    const res = await fetch(`/config/models/${encodeURIComponent(oldName)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    const result = await res.json()
    if (result.error) showToast(result.error, 'error')
    else {
      showToast('Model updated', 'success')
      config.value.models = result.models
      
      // 如果名称改变了，需要更新选中状态
      if (oldName !== modelForm.name) {
        if (selectedModels.value.has(oldName)) {
          selectedModels.value.delete(oldName)
          selectedModels.value.add(modelForm.name)
          localStorage.setItem('selectedModels', JSON.stringify([...selectedModels.value]))
        }
      }
      
      hideModal()
    }
    return
  }
  
  if (currentEditCaseId.value) {
    const data = {
      name: caseForm.name,
      messages: caseForm.messages,
      max_tokens: caseForm.max_tokens,
      temperature: 0.7,
      stream: true,
      expected_output: caseForm.expected_output,
      eval_model: caseForm.eval_model
    }
    const res = await fetch(`/config/test-cases/${currentEditCaseId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    const result = await res.json()
    if (result.error) showToast(result.error, 'error')
    else {
      showToast('Test case updated', 'success')
      config.value.test_cases = result.test_cases
      hideModal()
    }
    return
  }
  
  // 添加模式
  if (modalType.value === 'model') {
    const data = {
      name: modelForm.name,
      endpoint: modelForm.endpoint,
      api_key: modelForm.api_key,
      model: modelForm.model,
      enabled: true
    }
    if (!data.name || !data.endpoint || !data.model) {
      showToast('Please fill all fields', 'error')
      return
    }
    const res = await fetch('/config/models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    const result = await res.json()
    if (result.error) showToast(result.error, 'error')
    else {
      showToast('Model added', 'success')
      config.value.models = result.models
      hideModal()
    }
  } else {
    const data = {
      name: caseForm.name,
      messages: caseForm.messages,
      max_tokens: caseForm.max_tokens,
      temperature: 0.7,
      stream: true,
      expected_output: caseForm.expected_output,
      eval_model: caseForm.eval_model
    }
    // 检查是否至少有一条消息有内容
    const hasContent = caseForm.messages.some((msg: any) => msg.content && msg.content.trim())
    if (!data.name || !hasContent) {
      showToast('Please fill all fields', 'error')
      return
    }
    const res = await fetch('/config/test-cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    const result = await res.json()
    if (result.error) showToast(result.error, 'error')
    else {
      showToast('Test case added', 'success')
      config.value.test_cases = result.test_cases
      hideModal()
    }
  }
}

async function deleteModel(name: string) {
  if (!confirm(`Delete "${name}"?`)) return
  const res = await fetch(`/config/models/${encodeURIComponent(name)}`, { method: 'DELETE' })
  const result = await res.json()
  config.value.models = result.models
  selectedModels.value.delete(name)
  localStorage.setItem('selectedModels', JSON.stringify([...selectedModels.value]))
  showToast('Deleted', 'success')
}

async function deleteCase(id: string) {
  if (!confirm('Delete this case?')) return
  const res = await fetch(`/config/test-cases/${id}`, { method: 'DELETE' })
  const result = await res.json()
  config.value.test_cases = result.test_cases
  selectedCases.value.delete(id)
  localStorage.setItem('selectedCases', JSON.stringify([...selectedCases.value]))
  showToast('Deleted', 'success')
}

// 启动配置
function showStartConfig() {
  if (selectedModels.value.size === 0 || selectedCases.value.size === 0) {
    showToast('Select at least one model and test case', 'error')
    return
  }
  startConfigVisible.value = true
}

function hideStartConfig() {
  startConfigVisible.value = false
}

async function confirmStartTest() {
  hideStartConfig()
  
  // 清空之前的结果
  tasks.value = {}
  
  const modelsToTest = Array.from(selectedModels.value)
  const casesToTest = Array.from(selectedCases.value)
  
  console.log('[Start] Models:', modelsToTest)
  console.log('[Start] Cases:', casesToTest)
  console.log('[Start] Config:', startConfig)
  
  try {
    const res = await fetch('/test/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        models: modelsToTest,
        cases: casesToTest,
        test_rounds: startConfig.test_rounds,
        max_concurrent: startConfig.max_concurrent,
        interval: startConfig.interval,
        test_name: startConfig.test_name
      })
    })
    const result = await res.json()
    if (result.error) {
      showToast(result.error, 'error')
      return
    }
    
    console.log('[Start] Response:', result)
    
    if (result.config) {
      const { models, cases, total_rounds, concurrency } = result.config
      const rounds = total_rounds || 10
      
      models.forEach((m: string) => {
        cases.forEach((c: string) => {
          createTask(m, c, rounds)
        })
      })
      
      addLog(new Date().toLocaleTimeString(), 'START', `${models.length} models × ${cases.length} cases (${rounds} rounds each) [concurrency: ${concurrency ? 'ON' : 'OFF'}]`)
    }
    
    showToast('Test started', 'success')
    testRunning.value = true
    testStatus.value = 'RUNNING'
  } catch (e) {
    console.error('[Start] Error:', e)
    showToast('Failed to start', 'error')
  }
}

async function stopTest() {
  try {
    await fetch('/test/stop', { method: 'POST' })
    showToast('Test stopped', 'success')
    testRunning.value = false
    testStatus.value = 'STOPPED'
  } catch (e) {
    showToast('Failed to stop', 'error')
  }
}

async function clearTest() {
  tasks.value = {}
  activeSubTask.value = {}
  
  try {
    await fetch('/reset', { method: 'POST' })
  } catch (e) {
    console.error('Reset API error:', e)
  }
  
  testRunning.value = false
  testStatus.value = 'IDLE'
  showToast('Cleared', 'success')
}

// 单任务控制
async function stopSingleTask(taskId: string) {
  const task = tasks.value[taskId]
  if (!task) return
  
  // 将所有进行中的轮次标记为停止
  Object.values(task.sub_tasks).forEach(subTask => {
    if (subTask.status === 'running') {
      subTask.status = 'error'
    }
  })
  
  task.status = 'stopped'
  
  // 保留当前进度值，进度条继续显示
  // task.progress 不再归零
  
  // 检查是否还有其他运行中的任务
  const hasRunningTasks = Object.values(tasks.value).some(t => t.status === 'running')
  if (!hasRunningTasks) {
    testRunning.value = false
    testStatus.value = 'STOPPED'
  }
  
  addLog(new Date().toLocaleTimeString(), 'STOP', `${task.model_name} → ${task.case_name} 已停止`)
  showToast('任务已停止', 'success')
}

async function retrySingleTask(taskId: string) {
  const task = tasks.value[taskId]
  if (!task) return
  
  // 重置所有轮次
  const totalRounds = task.total_rounds
  for (let r = 1; r <= totalRounds; r++) {
    const subId = getSubTaskId(task.model_name, task.case_name, r)
    if (task.sub_tasks[subId]) {
      task.sub_tasks[subId] = {
        name: `Round ${r}/${totalRounds}`,
        output: '',
        status: 'pending',
        metrics: {}
      }
    }
  }
  
  task.status = 'running'
  task.progress = 0
  task.current_round = 0
  task.avgTtft = undefined
  task.avgTpft = undefined
  task.avgTokens = undefined
  task.avgSpeed = undefined
  task.avgAnswerSpeed = undefined
  task.avgThinkTokens = undefined
  task.avgAnswerTokens = undefined
  
  testRunning.value = true
  testStatus.value = 'RUNNING'
  
  addLog(new Date().toLocaleTimeString(), 'RETRY', `${task.model_name} → ${task.case_name} 重新测试`)
  showToast('任务已重新开始', 'success')
}

// 任务管理
function createTask(modelName: string, caseName: string, totalRounds: number = 10) {
  const taskId = getTaskId(modelName, caseName)
  
  const existingTask = tasks.value[taskId]
  
  tasks.value[taskId] = {
    model_name: modelName,
    case_name: caseName,
    progress: 0,
    status: 'running',
    current_round: 0,
    total_rounds: totalRounds,
    sub_tasks: existingTask ? existingTask.sub_tasks : {},
    startTime: Date.now() / 1000,  // 记录任务开始时间
    duration: undefined  // 初始未设置，完成后设置
  }
  
  // 预创建所有轮次
  for (let r = 1; r <= totalRounds; r++) {
    const subId = getSubTaskId(modelName, caseName, r)
    if (!tasks.value[taskId].sub_tasks[subId]) {
      tasks.value[taskId].sub_tasks[subId] = {
        name: `Round ${r}/${totalRounds}`,
        output: '',
        status: 'pending',
        metrics: {}
      }
    } else {
      tasks.value[taskId].sub_tasks[subId].name = `Round ${r}/${totalRounds}`
    }
  }
  
  if (activeSubTask.value[taskId] === undefined) {
    activeSubTask.value[taskId] = Math.max(0, totalRounds - 1)
  }
  
  // 初始化卡片位置
  initCardPosition(taskId)
}

// 初始化卡片位置
function initCardPosition(taskId: string) {
  if (!cardPositions.value[taskId]) {
    const order = taskOrder.value.length
    cardPositions.value[taskId] = {
      order: order,
      width: 320,
      height: 180
    }
    taskOrder.value.push(taskId)
  }
}

// 卡片拖拽排序 - 开始
function startCardDrag(e: MouseEvent, taskId: string) {
  // 如果点击的是按钮或操作区域，不触发拖拽
  if ((e.target as HTMLElement).closest('.task-action-btn') || 
      (e.target as HTMLElement).closest('.task-status')) {
    return
  }
  
  cardDragState.isDragging = true
  cardDragState.draggingCardId = taskId
  cardDragState.startX = e.clientX
  cardDragState.startY = e.clientY
  cardDragState.startIndex = taskOrder.value.indexOf(taskId)
  cardDragState.currentIndex = cardDragState.startIndex
  
  document.addEventListener('mousemove', onCardDrag)
  document.addEventListener('mouseup', stopCardDrag)
  e.preventDefault()
  e.stopPropagation()
}

// 卡片拖拽排序 - 移动
function onCardDrag(e: MouseEvent) {
  if (!cardDragState.isDragging || !cardDragState.draggingCardId) return
  
  const container = document.getElementById('taskCards')
  if (!container) return
  
  const containerRect = container.getBoundingClientRect()
  const cards = container.querySelectorAll('.task-card')
  
  // 计算当前拖拽位置
  const deltaX = e.clientX - cardDragState.startX
  const deltaY = e.clientY - cardDragState.startY
  
  // 找到当前拖拽卡片应该放置的位置
  let newIndex = cardDragState.startIndex
  
  cards.forEach((card, index) => {
    if (index === cardDragState.startIndex) return
    
    const rect = card.getBoundingClientRect()
    const cardCenterX = rect.left + rect.width / 2
    const cardCenterY = rect.top + rect.height / 2
    
    // 检查是否越过了其他卡片
    if (cardDragState.startIndex < index) {
      // 从左向右拖
      if (deltaX > 0 && e.clientX > cardCenterX - 20) {
        newIndex = index
      } else if (deltaY > 0 && e.clientY > cardCenterY - 20) {
        newIndex = index
      }
    } else {
      // 从右向左拖
      if (deltaX < 0 && e.clientX < cardCenterX + 20) {
        newIndex = index
      } else if (deltaY < 0 && e.clientY < cardCenterY + 20) {
        newIndex = index
      }
    }
  })
  
  // 更新排序
  if (newIndex !== cardDragState.currentIndex) {
    cardDragState.currentIndex = newIndex
    reorderTasks(newIndex)
  }
}

// 重新排序任务
function reorderTasks(newIndex: number) {
  const draggingId = cardDragState.draggingCardId
  if (!draggingId) return
  
  const currentIndex = taskOrder.value.indexOf(draggingId)
  if (currentIndex === -1 || currentIndex === newIndex) return
  
  // 从原位置移除
  taskOrder.value.splice(currentIndex, 1)
  // 插入到新位置
  taskOrder.value.splice(newIndex, 0, draggingId)
  
  // 更新所有卡片的order
  taskOrder.value.forEach((taskId, index) => {
    if (cardPositions.value[taskId]) {
      cardPositions.value[taskId].order = index
    }
  })
}

// 卡片拖拽排序 - 结束
function stopCardDrag() {
  // 保存排序到localStorage
  saveCardPositions()
  
  cardDragState.isDragging = false
  cardDragState.draggingCardId = null
  cardDragState.startIndex = -1
  cardDragState.currentIndex = -1
  
  document.removeEventListener('mousemove', onCardDrag)
  document.removeEventListener('mouseup', stopCardDrag)
}

// 卡片尺寸调整 - 开始
function startCardResize(e: MouseEvent, taskId: string) {
  e.preventDefault()
  e.stopPropagation()
  
  const cardEl = document.getElementById(`card-${taskId}`)
  if (!cardEl) return
  
  const rect = cardEl.getBoundingClientRect()
  
  cardResizeState.isResizing = true
  cardResizeState.resizingCardId = taskId
  cardResizeState.startX = e.clientX
  cardResizeState.startY = e.clientY
  cardResizeState.startWidth = rect.width
  cardResizeState.startHeight = rect.height
  
  document.addEventListener('mousemove', onCardResize)
  document.addEventListener('mouseup', stopCardResize)
}

// 卡片尺寸调整 - 移动
function onCardResize(e: MouseEvent) {
  if (!cardResizeState.isResizing || !cardResizeState.resizingCardId) return
  
  const deltaX = e.clientX - cardResizeState.startX
  const deltaY = e.clientY - cardResizeState.startY
  
  const newWidth = Math.max(MIN_CARD_WIDTH, Math.min(MAX_CARD_WIDTH, cardResizeState.startWidth + deltaX))
  const newHeight = Math.max(MIN_CARD_HEIGHT, Math.min(MAX_CARD_HEIGHT, cardResizeState.startHeight + deltaY))
  
  if (cardPositions.value[cardResizeState.resizingCardId]) {
    cardPositions.value[cardResizeState.resizingCardId].width = newWidth
    cardPositions.value[cardResizeState.resizingCardId].height = newHeight
  }
}

// 卡片尺寸调整 - 结束
function stopCardResize() {
  // 保存尺寸到localStorage
  saveCardPositions()
  
  cardResizeState.isResizing = false
  cardResizeState.resizingCardId = null
  
  document.removeEventListener('mousemove', onCardResize)
  document.removeEventListener('mouseup', stopCardResize)
}

// 保存卡片位置和尺寸
function saveCardPositions() {
  localStorage.setItem('taskCardPositions', JSON.stringify(cardPositions.value))
  localStorage.setItem('taskCardOrder', JSON.stringify(taskOrder.value))
}

// 加载卡片位置和尺寸
function loadCardPositions() {
  try {
    const savedPositions = localStorage.getItem('taskCardPositions')
    const savedOrder = localStorage.getItem('taskCardOrder')
    
    if (savedPositions) {
      cardPositions.value = JSON.parse(savedPositions)
    }
    if (savedOrder) {
      taskOrder.value = JSON.parse(savedOrder)
    }
  } catch (e) {
    console.error('Failed to load card positions:', e)
  }
}

// 获取卡片样式
function getCardStyle(taskId: string): Record<string, string> {
  const pos = cardPositions.value[taskId]
  if (!pos) return {}
  
  const style: Record<string, string> = {}
  
  if (pos.width && pos.width !== 320) {
    style.width = pos.width + 'px'
  }
  if (pos.height && pos.height !== 180) {
    style.minHeight = pos.height + 'px'
  }
  
  return style
}

// 卡片展开/折叠
function toggleExpand(taskId: string) {
  const task = tasks.value[taskId]
  if (!task) return
  
  // 切换展开状态
  task.expanded = !task.expanded
}

// 打开任务详情弹窗
function openTaskDetail(taskId: string) {
  const task = tasks.value[taskId]
  if (!task) return
  
  // 先设置数据
  taskDetailData.value = { ...task }
  // 显示遮罩层（带动画）
  taskDetailVisible.value = true
  // 触发重绘后添加 animating 类
  nextTick(() => {
    isAnimating.value = true
    setTimeout(() => {
      isAnimating.value = false
    }, 400)
  })
}

// 关闭任务详情弹窗
function hideTaskDetail() {
  taskDetailVisible.value = false
}

function updateSubTask(modelName: string, caseName: string, round: number, totalRounds: number, status: string = 'running') {
  const taskId = getTaskId(modelName, caseName)
  const subId = getSubTaskId(modelName, caseName, round)
  
  if (!tasks.value[taskId]) {
    tasks.value[taskId] = {
      model_name: modelName,
      case_name: caseName,
      progress: 0,
      status: 'running',
      current_round: round,
      total_rounds: totalRounds,
      sub_tasks: {}
    }
    
    for (let r = 1; r <= totalRounds; r++) {
      const sid = getSubTaskId(modelName, caseName, r)
      tasks.value[taskId].sub_tasks[sid] = {
        name: `Round ${r}/${totalRounds}`,
        output: '',
        status: r === round ? status : 'pending',
        metrics: {}
      }
    }
    
    activeSubTask.value[taskId] = round - 1
  } else {
    tasks.value[taskId].total_rounds = totalRounds
    
    if (!tasks.value[taskId].sub_tasks[subId]) {
      tasks.value[taskId].sub_tasks[subId] = {
        name: `Round ${round}/${totalRounds}`,
        output: '',
        status: status,
        metrics: {}
      }
    } else {
      tasks.value[taskId].sub_tasks[subId].status = status
    }
    
    if (activeSubTask.value[taskId] === undefined) {
      const subTaskKeys = Object.keys(tasks.value[taskId].sub_tasks)
      const idx = subTaskKeys.indexOf(subId)
      activeSubTask.value[taskId] = idx >= 0 ? idx : 0
    }
  }
  
  tasks.value[taskId].current_round = round
  tasks.value[taskId].progress = Math.round((round / totalRounds) * 100)
  
  const subTasks = tasks.value[taskId].sub_tasks
  const allDone = Object.values(subTasks).every(t => t.status === 'done' || t.status === 'error')
  if (allDone && Object.keys(subTasks).length >= totalRounds) {
    tasks.value[taskId].status = 'done'
    // 计算平均值
    calculateAverages(taskId)
  } else {
    tasks.value[taskId].status = 'running'
  }
  
  return subId
}

function calculateAverages(taskId: string) {
  const task = tasks.value[taskId]
  const subTasks = Object.values(task.sub_tasks)
  
  const doneTasks = subTasks.filter(st => {
    if (st.status !== 'done') return false
    if (!st.metrics) return false
    const m = st.metrics
    return (m.ttft && m.ttft !== '--') || (m.speed && m.speed !== '--')
  })
  
  if (doneTasks.length === 0) return
  
  let ttftSum = 0, tpftSum = 0, tokenSum = 0, speedSum = 0
  let ttftCount = 0, tpftCount = 0, tokenCount = 0, speedCount = 0
  
  // Think/Answer 统计
  let thinkTokenSum = 0, answerTokenSum = 0, answerSpeedSum = 0
  let thinkTokenCount = 0, answerTokenCount = 0, answerSpeedCount = 0
  
  // 校对结果统计
  let evalRateSum = 0, evalCount = 0
  let evalCorrectCount = 0, evalIncorrectCount = 0
  
  doneTasks.forEach(t => {
    const m = t.metrics
    if (m.ttft && m.ttft !== '--') {
      const v = parseFloat(m.ttft)
      if (!isNaN(v)) { ttftSum += v; ttftCount++ }
    }
    if (m.tpft && m.tpft !== '--') {
      const v = parseFloat(m.tpft)
      if (!isNaN(v)) { tpftSum += v; tpftCount++ }
    }
    if (m.tokens && m.tokens !== '--') {
      const v = parseFloat(m.tokens)
      if (!isNaN(v)) { tokenSum += v; tokenCount++ }
    }
    if (m.speed && m.speed !== '--') {
      const v = parseFloat(m.speed)
      if (!isNaN(v)) { speedSum += v; speedCount++ }
    }
    // Think/Answer 指标
    if (m.thinkTokens && m.thinkTokens !== '--') {
      const v = parseFloat(m.thinkTokens)
      if (!isNaN(v)) { thinkTokenSum += v; thinkTokenCount++ }
    }
    if (m.answerTokens && m.answerTokens !== '--') {
      const v = parseFloat(m.answerTokens)
      if (!isNaN(v)) { answerTokenSum += v; answerTokenCount++ }
    }
    if (m.answerSpeed && m.answerSpeed !== '--') {
      const v = parseFloat(m.answerSpeed)
      if (!isNaN(v)) { answerSpeedSum += v; answerSpeedCount++ }
    }
    // 校对结果统计 - 只统计成功的轮次
    if (t.status === 'done' && t.evaluation && t.evaluation.rate !== undefined && t.evaluation.rate !== null) {
      const rate = parseFloat(t.evaluation.rate)
      if (!isNaN(rate)) {
        evalRateSum += rate
        evalCount++
        if (rate >= 6) {
          evalCorrectCount++
        } else {
          evalIncorrectCount++
        }
      }
    }
  })
  
  task.avgTtft = ttftCount > 0 ? (ttftSum / ttftCount).toFixed(3) : '--'
  task.avgTpft = tpftCount > 0 ? (tpftSum / tpftCount).toFixed(3) : '--'
  task.avgTokens = tokenCount > 0 ? Math.round(tokenSum / tokenCount) : '--'
  task.avgSpeed = speedCount > 0 ? (speedSum / speedCount).toFixed(1) : '--'
  task.avgThinkTokens = thinkTokenCount > 0 ? Math.round(thinkTokenSum / thinkTokenCount) : '--'
  task.avgAnswerTokens = answerTokenCount > 0 ? Math.round(answerTokenSum / answerTokenCount) : '--'
  task.avgAnswerSpeed = answerSpeedCount > 0 ? (answerSpeedSum / answerSpeedCount).toFixed(1) : '--'
  
  // 校对结果平均分
  if (evalCount > 0) {
    task.avgEvalRate = evalRateSum / evalCount
    task.evalCorrectCount = evalCorrectCount
    task.evalIncorrectCount = evalIncorrectCount
  } else {
    task.avgEvalRate = undefined
    task.evalCorrectCount = 0
    task.evalIncorrectCount = 0
  }
  
  // 任务完成时设置最终耗时
  if (task.startTime) {
    task.duration = now.value - task.startTime
  }
}

// Popover
function showRoundPopoverForButton(e: MouseEvent, taskId: string, subId: string, subTask: SubTask) {
  showRoundPopover(e, taskId, subId, subTask)
}

function showRoundPopover(e: MouseEvent, taskId: string, subId: string, subTask: SubTask) {
  const target = e.target as HTMLElement
  const rect = target.getBoundingClientRect()
  
  popoverX.value = rect.left + rect.width / 2 - 150
  popoverY.value = rect.top + 15
  
  let outputText = ''
  if (subTask.output) {
    outputText = subTask.status === 'running' ? subTask.output.substring(0, 500) : trimText(subTask.output.substring(0, 500))
  } else if (subTask.status === 'pending') {
    outputText = '等待中...'
  } else {
    outputText = '无输出'
  }
  
  let metricsInfo = ''
  if (subTask.metrics && subTask.status === 'done') {
    const m = subTask.metrics
    const parts = []
    if (m.speed) parts.push(`总速度: ${m.speed} t/s`)
    if (m.answerSpeed) parts.push(`Answer: ${m.answerSpeed} t/s`)
    if (m.tokens) parts.push(`Tokens: ${m.tokens}`)
    if (m.thinkTokens) parts.push(`Think: ${m.thinkTokens}`)
    if (m.answerTokens) parts.push(`Answer: ${m.answerTokens}`)
    if (m.ttft) parts.push(`TTFT: ${m.ttft}s`)
    if (m.tpft) parts.push(`TPFT: ${m.tpft}s`)
    if (m.thinkTime && m.thinkTime !== '--') parts.push(`Think: ${m.thinkTime}s`)
    if (m.answerTime && m.answerTime !== '--') parts.push(`Answer: ${m.answerTime}s`)
    metricsInfo = parts.join(' | ')
  }
  
  popoverData.value = {
    name: subTask.name,
    status: subTask.status,
    output: outputText,
    metrics: metricsInfo
  }
  
  // 调整位置确保不超出视口
  nextTick(() => {
    const popover = document.querySelector('.round-popover') as HTMLElement
    if (!popover) return
    
    const popoverRect = popover.getBoundingClientRect()
    let left = popoverX.value
    let top = popoverY.value
    
    if (left + popoverRect.width > window.innerWidth - 10) {
      left = window.innerWidth - popoverRect.width - 10
    }
    if (left < 10) left = 10
    if (top + popoverRect.height > window.innerHeight - 10) {
      top = rect.top - popoverRect.height - 10
    }
    if (top < 10) top = 10
    
    popoverX.value = left
    popoverY.value = top
  })
  
  popoverVisible.value = true
}

function hideRoundPopover() {
  popoverVisible.value = false
}

// 模型 Popover
function showModelPopover(e: MouseEvent, model: any) {
  const target = e.target as HTMLElement
  const rect = target.getBoundingClientRect()
  
  modelPopoverX.value = rect.left + rect.width / 2 - 120
  modelPopoverY.value = rect.bottom + 8
  
  // 使用模型信息
  modelPopoverData.value = model
  
  // 调整位置确保不超出视口
  nextTick(() => {
    const popover = document.querySelector('.model-popover') as HTMLElement
    if (!popover) return
    
    const popoverRect = popover.getBoundingClientRect()
    let left = modelPopoverX.value
    let top = modelPopoverY.value
    
    if (left + popoverRect.width > window.innerWidth - 10) {
      left = window.innerWidth - popoverRect.width - 10
    }
    if (left < 10) left = 10
    if (top + popoverRect.height > window.innerHeight - 10) {
      top = rect.top - popoverRect.height - 8
    }
    if (top < 10) top = 10
    
    modelPopoverX.value = left
    modelPopoverY.value = top
  })
  
  modelPopoverVisible.value = true
}

function hideModelPopover() {
  modelPopoverVisible.value = false
}

// Test Case Popover
const casePopoverVisible = ref(false)
const casePopoverX = ref(0)
const casePopoverY = ref(0)
const casePopoverData = ref<any>({})

function showCasePopover(e: MouseEvent, caseItem: any) {
  const target = e.target as HTMLElement
  const rect = target.getBoundingClientRect()
  
  casePopoverX.value = rect.left + rect.width / 2 - 150
  casePopoverY.value = rect.bottom + 8
  
  // 使用测试用例信息
  casePopoverData.value = caseItem
  
  // 调整位置确保不超出视口
  nextTick(() => {
    const popover = document.querySelector('.case-popover') as HTMLElement
    if (!popover) return
    
    const popoverRect = popover.getBoundingClientRect()
    let left = casePopoverX.value
    let top = casePopoverY.value
    
    if (left + popoverRect.width > window.innerWidth - 10) {
      left = window.innerWidth - popoverRect.width - 10
    }
    if (left < 10) left = 10
    if (top + popoverRect.height > window.innerHeight - 10) {
      top = rect.top - popoverRect.height - 8
    }
    if (top < 10) top = 10
    
    casePopoverX.value = left
    casePopoverY.value = top
  })
  
  casePopoverVisible.value = true
}

function hideCasePopover() {
  casePopoverVisible.value = false
}

// 编辑功能
function editCase(caseItem: any) {
  // 填充表单
  caseForm.name = caseItem.name
  // 优先使用 messages 字段，如果没有则降级使用 prompt
  if (caseItem.messages && Array.isArray(caseItem.messages) && caseItem.messages.length > 0) {
    caseForm.messages = JSON.parse(JSON.stringify(caseItem.messages))
  } else if (caseItem.prompt) {
    // 兼容旧数据：将 prompt 转换为 messages 格式
    caseForm.messages = [{ role: 'user', content: caseItem.prompt }]
  } else {
    caseForm.messages = [{ role: 'user', content: '' }]
  }
      caseForm.max_tokens = caseItem.max_tokens || 500
  caseForm.expected_output = caseItem.expected_output || ''
  caseForm.eval_model = caseItem.eval_model || ''
  
  // 保存当前编辑的用例ID
  currentEditCaseId.value = caseItem.id
  
  // 显示模态框
  modalType.value = 'case'
  modalVisible.value = true
}

function editModel(model: any) {
  // 填充表单
  modelForm.name = model.name
  modelForm.endpoint = model.endpoint || ''
  modelForm.api_key = model.api_key || ''
  modelForm.model = model.model || ''
  modelForm.temperature = model.temperature ?? 0.7
  modelForm.top_p = model.top_p ?? 1.0
  modelForm.max_tokens = model.max_tokens ?? 4096
  modelForm.presence_penalty = model.presence_penalty ?? 0.0
  modelForm.frequency_penalty = model.frequency_penalty ?? 0.0
  modelForm.thinking_enabled = model.thinking_enabled ?? true
  
  // 保存当前编辑的模型名称
  currentEditModelName.value = model.name
  
  // 显示模态框
  modalType.value = 'model'
  modalVisible.value = true
}

const currentEditCaseId = ref<string | null>(null)
const currentEditModelName = ref<string | null>(null)

// 测试功能状态
const isTesting = ref(false)
const testResult = ref<{ success: boolean; latency_ms?: number; error?: string; response_preview?: string } | null>(null)

// 判断是否可以测试（需要填写 endpoint, api_key, model）
const canTestModel = computed(() => {
  return modelForm.endpoint && modelForm.api_key && modelForm.model
})

// 测试模型连接
async function testModel() {
  if (!canTestModel.value || isTesting.value) return
  
  isTesting.value = true
  testResult.value = null
  
  try {
    // 如果是编辑模式，使用当前编辑的模型名称
    // 否则使用表单中填写的信息进行测试
    const modelData = {
      endpoint: modelForm.endpoint,
      api_key: modelForm.api_key,
      model: modelForm.model
    }
    
    const res = await fetch('/config/models/ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(modelData)
    })
    
    const data = await res.json()
    testResult.value = data
    
    if (data.success) {
      showToast('连接测试成功', 'success')
    } else {
      showToast('连接测试失败: ' + (data.error || '未知错误'), 'error')
    }
  } catch (e) {
    testResult.value = { success: false, error: String(e) }
    showToast('连接测试失败', 'error')
  } finally {
    isTesting.value = false
  }
}

// 历史记录
function showHistoryModal() {
  historyVisible.value = true
  loadHistory()
}

function hideHistoryModal() {
  historyVisible.value = false
}

async function loadHistory() {
  try {
    const res = await fetch('/api/history?limit=20')
    const data = await res.json()
    
    if (data.success && data.data) {
      historyList.value = data.data
    } else {
      historyList.value = []
    }
  } catch (e) {
    console.error('Load history error:', e)
    historyList.value = []
  }
}
async function viewHistoryDetail(groupId: string) {
  hideHistoryModal()
  // 跳转到历史页面并传递 groupId
  router.push({ path: '/history', query: { groupId } })
}

async function deleteHistory(groupId: string) {
  if (!confirm('确定删除此测试记录吗？')) return
  
  try {
    const res = await fetch(`/api/history/${groupId}`, { method: 'DELETE' })
    const data = await res.json()
    
    if (data.success) {
      showToast('删除成功', 'success')
      await loadHistory()
    } else {
      showToast('删除失败: ' + data.error, 'error')
    }
  } catch (e) {
    showToast('删除失败', 'error')
  }
}

// SSE
function connectSSE() {
  eventSource = new EventSource('/events')
  
  eventSource.onopen = () => {
    sseConnected.value = true
    sseStatus.value = 'OK'
  }
  
  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      handleEvent(data)
    } catch (err) {}
  }
  
  eventSource.onerror = () => {
    sseConnected.value = false
    sseStatus.value = 'RETRY'
    setTimeout(connectSSE, 3000)
  }
}

function handleEvent(event: any) {
  const { type, data: eventData } = event
  const data = eventData
  const now = new Date().toLocaleTimeString()
  const taskId = data.model_name && data.test_case_name ? getTaskId(data.model_name, data.test_case_name) : null
  
  const currentRound = data.current_round || 1
  const totalRounds = data.total_rounds || 10
  const subTaskId = taskId ? getSubTaskId(data.model_name, data.test_case_name, currentRound) : null
  
  switch (type) {
    case 'start':
      const models = data.models || []
      const cases = data.test_cases || []
      const startTotalRounds = data.total_rounds || 10
      models.forEach((m: string) => {
        cases.forEach((c: string) => {
          createTask(m, c, startTotalRounds)
        })
      })
      addLog(now, 'START', `${models.length} models × ${cases.length} cases (${startTotalRounds} rounds each)`)
      break
      
    case 'progress':
      if (taskId) {
        updateSubTask(data.model_name, data.test_case_name, currentRound, totalRounds, 'running')
      }
      addLog(now, 'ROUND', `${data.model_name}: ${currentRound}/${totalRounds}`)
      break
      
    case 'chunk':
      if (subTaskId && taskId && tasks.value[taskId] && tasks.value[taskId].sub_tasks[subTaskId]) {
        tasks.value[taskId].sub_tasks[subTaskId].output += data.content
      }
      break
      
    case 'complete':
      console.log('[complete event] prompt:', data.prompt, 'response length:', data.response?.length)
      if (taskId && tasks.value[taskId] && subTaskId && tasks.value[taskId].sub_tasks[subTaskId]) {
        tasks.value[taskId].sub_tasks[subTaskId].status = data.success ? 'done' : 'error'
        tasks.value[taskId].sub_tasks[subTaskId].metrics = {
          ttft: data.metrics?.ttft_seconds?.toFixed(3) || '--',
          tpft: data.metrics?.tpft_seconds?.toFixed(3) || '--',
          tokens: data.metrics?.output_tokens || '--',
          speed: data.metrics?.tokens_per_second?.toFixed(1) || '--',
          thinkTime: data.metrics?.think_time_seconds?.toFixed(3) || '--',
          answerTime: data.metrics?.answer_time_seconds?.toFixed(3) || '--',
          thinkTokens: data.metrics?.think_tokens || '--',
          answerTokens: data.metrics?.answer_tokens || '--',
          thinkSpeed: data.metrics?.think_tokens_per_second?.toFixed(1) || '--',
          answerSpeed: data.metrics?.answer_tokens_per_second?.toFixed(1) || '--'
        }
        // 保存 prompt 和 response 用于详情显示
        console.log('[complete] saving prompt:', data.prompt ? 'yes' : 'no', 'response:', data.response ? 'yes' : 'no')
        if (data.prompt) {
          tasks.value[taskId].sub_tasks[subTaskId].prompt = data.prompt
          console.log('[complete] prompt saved:', data.prompt.substring(0, 50))
        }
        if (data.response) {
          tasks.value[taskId].sub_tasks[subTaskId].output = data.response
          console.log('[complete] response saved, length:', data.response.length)
        }
        // 保存校对结果（如果存在）
        if (data.evaluation) {
          tasks.value[taskId].sub_tasks[subTaskId].evaluation = data.evaluation
          console.log('[complete] evaluation saved:', JSON.stringify(data.evaluation))
        }
        
        // 检查所有轮次是否都已完成
        const subTasks = tasks.value[taskId].sub_tasks
        const subTaskKeys = Object.keys(subTasks)
        const allDone = subTaskKeys.length > 0 && subTaskKeys.every(key => 
          subTasks[key].status === 'done' || subTasks[key].status === 'error'
        )
        
        if (allDone) {
          tasks.value[taskId].status = 'done'
          calculateAverages(taskId)
        }
      }
      addLog(now, 'DONE', `${data.model_name} → ${data.test_case_name} R${currentRound}`)
      break
      
    case 'summary':
      testRunning.value = false
      testStatus.value = 'DONE'
      // 获取总耗时
      const totalDuration = eventData.total_duration_seconds || 0
      if (totalDuration > 0) {
        const durationMinutes = Math.floor(totalDuration / 60)
        const durationSeconds = (totalDuration % 60).toFixed(1)
        addLog(now, 'FINISH', `All tests complete - 总耗时: ${durationMinutes > 0 ? durationMinutes + '分' : ''}${durationSeconds}秒`)
      } else {
        addLog(now, 'FINISH', 'All tests complete')
      }
      break
      
    case 'error':
      if (taskId && tasks.value[taskId]) {
        tasks.value[taskId].status = 'error'
        if (subTaskId && tasks.value[taskId].sub_tasks[subTaskId]) {
          tasks.value[taskId].sub_tasks[subTaskId].status = 'error'
        }
      }
      addLog(now, 'ERROR', data.error || 'Unknown error')
      showToast('Error: ' + (data.error || 'Unknown'), 'error')
      break
  }
}

// 日志
function addLog(time: string, tag: string, msg: string) {
  const now = new Date()
  const fullTime = now.toISOString()
  logs.value.push({ time, fullTime, tag, msg, isNew: true })
  // 限制日志数量
  if (logs.value.length > 100) {
    logs.value = logs.value.slice(-100)
  }
  // 标记旧日志为非新
  if (logs.value.length > 1) {
    logs.value[logs.value.length - 2].isNew = false
  }
  // 自动滚动
  scrollToBottom()
}

// Toast
function showToast(msg: string, type: string = '') {
  toastMessage.value = msg
  toastType.value = type
  toastVisible.value = true
  setTimeout(() => {
    toastVisible.value = false
  }, 3000)
}

// 加载配置
async function loadConfig() {
  try {
    const res = await fetch('/config')
    config.value = await res.json()
  } catch (e) {
    console.error('Failed to load config:', e)
  }
}

// 加载测试状态
async function loadTestStatus() {
  try {
    const res = await fetch('/test/status')
    const data = await res.json()
    if (data.running) {
      testRunning.value = true
      testStatus.value = 'RUNNING'
    }
  } catch (e) {
    console.error('Failed to load test status:', e)
  }
}

// 加载测试状态恢复
async function loadTestState() {
  try {
    const res = await fetch('/status')
    const data = await res.json()
    
    const savedTasks = data.tasks || {}
    const taskKeys = Object.keys(savedTasks)
    
    if (taskKeys.length > 0) {
      console.log(`[State] 恢复 ${taskKeys.length} 个任务状态`)
      
      for (const [taskId, taskData] of Object.entries(savedTasks)) {
        const modelName = taskData.model_name
        const caseName = taskData.test_case_name
        const totalRounds = taskData.total_rounds || 10
        const rounds = taskData.rounds || {}
        
        tasks.value[taskId] = {
          model_name: modelName,
          case_name: caseName,
          progress: 0,
          status: 'running',
          current_round: 0,
          total_rounds: totalRounds,
          sub_tasks: {}
        }
        
        let doneCount = 0
        let latestRound = 0
        
          for (const [roundKey, roundData] of Object.entries(rounds)) {
          const subId = getSubTaskId(modelName, caseName, parseInt(roundKey))
          
          // 转换 metrics 格式：后端字段名 -> 前端字段名
          let metrics = {}
          if (roundData.metrics) {
            const m = roundData.metrics
            metrics = {
              ttft: m.ttft_seconds !== undefined ? m.ttft_seconds.toFixed(3) : '--',
              tpft: m.tpft_seconds !== undefined ? m.tpft_seconds.toFixed(3) : '--',
              tokens: m.output_tokens || '--',
              speed: m.tokens_per_second !== undefined ? m.tokens_per_second.toFixed(1) : '--',
              thinkTime: m.think_time_seconds !== undefined ? m.think_time_seconds.toFixed(3) : '--',
              answerTime: m.answer_time_seconds !== undefined ? m.answer_time_seconds.toFixed(3) : '--',
              thinkTokens: m.think_tokens || '--',
              answerTokens: m.answer_tokens || '--',
              thinkSpeed: m.think_tokens_per_second !== undefined ? m.think_tokens_per_second.toFixed(1) : '--',
              answerSpeed: m.answer_tokens_per_second !== undefined ? m.answer_tokens_per_second.toFixed(1) : '--'
            }
          }
          
          tasks.value[taskId].sub_tasks[subId] = {
            name: `Round ${roundKey}/${totalRounds}`,
            output: roundData.output || '',
            status: roundData.status || 'pending',
            metrics: metrics,
            evaluation: roundData.evaluation || undefined
          }
          
          if (roundData.status === 'done') {
            doneCount++
            latestRound = Math.max(latestRound, parseInt(roundKey))
          } else if (roundData.status === 'running') {
            latestRound = Math.max(latestRound, parseInt(roundKey))
          }
        }
        
        tasks.value[taskId].current_round = latestRound
        tasks.value[taskId].progress = Math.round((latestRound / totalRounds) * 100)
        
        const subTasks = tasks.value[taskId].sub_tasks
        const allDone = Object.values(subTasks).every(t => t.status === 'done' || t.status === 'error')
        if (allDone && Object.keys(subTasks).length >= totalRounds) {
          tasks.value[taskId].status = 'done'
          calculateAverages(taskId)
        }
        
        activeSubTask.value[taskId] = latestRound > 0 ? latestRound - 1 : 0
      }
      
      const runningCount = taskKeys.filter(id => tasks.value[id].status === 'running').length
      
      if (runningCount > 0) {
        testRunning.value = true
        testStatus.value = 'RUNNING'
      } else {
        testStatus.value = 'DONE'
      }
    }
  } catch (e) {
    console.error('[State] 加载状态失败:', e)
  }
}

// 初始化
onMounted(async () => {
  // 加载本地存储的选中状态
  const savedModels = localStorage.getItem('selectedModels')
  const savedCases = localStorage.getItem('selectedCases')
  if (savedModels) {
    JSON.parse(savedModels).forEach((m: string) => selectedModels.value.add(m))
  }
  if (savedCases) {
    JSON.parse(savedCases).forEach((c: string) => selectedCases.value.add(c))
  }
  
  // 加载卡片位置和尺寸
  loadCardPositions()
  
  // 加载侧边栏状态（折叠状态和宽度）
  const savedCollapsed = localStorage.getItem('sidebarCollapsed')
  const savedWidth = localStorage.getItem('sidebarWidth')
  if (savedCollapsed !== null) {
    isCollapsed.value = savedCollapsed === 'true'
  }
  if (savedWidth) {
    sidebarWidth.value = parseInt(savedWidth)
  } else {
    // 如果没有保存的宽度，检查窗口宽度是否需要自动折叠
    if (window.innerWidth <= AUTO_COLLAPSE_WIDTH) {
      isCollapsed.value = true
      sidebarWidth.value = COLLAPSED_WIDTH
    }
  }
  
  await loadConfig()
  await loadTestStatus()
  await loadTestState()
  connectSSE()
  
  // 添加初始日志
  addLog(new Date().toLocaleTimeString(), 'SYSTEM', 'Ready')
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
  }
})
</script>

<style lang="scss" scoped>
.dashboard {
  display: grid;
  grid-template-columns: v-bind('sidebarWidth + "px"') 1fr;
  grid-template-rows: 52px 1fr;
  height: 100vh;
  gap: 0;
  padding: 0;
  background: var(--white);
  user-select: none;
  position: relative;
  
  &.dragging {
    cursor: col-resize;
    user-select: none;
    
    * {
      pointer-events: none;
    }
  }
}

/* 顶部栏 */
.header {
  grid-column: span 2;
  background: var(--white);
  border-bottom: 1px solid var(--gray-200);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.fullscreen-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  margin-right: 16px;
  flex-shrink: 0;
  
  &:hover {
    background: var(--gray-200);
  }
  
  .fullscreen-icon {
    font-size: 20px;
    color: var(--gray-600);
  }
  
  &:hover .fullscreen-icon {
    color: var(--gray-900);
  }
}

.logo {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--gray-900);
  display: flex;
  align-items: center;
  gap: 8px;
  letter-spacing: -0.02em;
}

.logo-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--gray-500);
  border: 1px solid var(--gray-300);
  padding: 2px 6px;
  letter-spacing: 0.05em;
}

.controls {
  display: flex;
  gap: 12px;
}

.btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 500;
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid var(--gray-300);
  background: var(--white);
  color: var(--gray-700);
  cursor: pointer;
  transition: all 0.2s ease;
  letter-spacing: 0.3px;
  min-height: 36px;
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  
  &:hover:not(:disabled) {
    border-color: var(--primary);
    color: var(--primary);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
  
  &:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: none;
  }
  
  &:focus {
    outline: none;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
  }
}

.btn-primary {
  background: var(--primary);
  color: var(--white);
  border-color: var(--primary);
  
  &:hover:not(:disabled) {
    background: var(--primary-light);
    border-color: var(--primary-light);
    color: var(--white);
  }
}

.btn-secondary {
  &:hover:not(:disabled) {
    background: var(--gray-50);
  }
}

/* 测试按钮样式 */
.btn-test {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  color: white;
  border: none;
  padding: 10px 20px;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover:not(:disabled) {
    background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(139, 92, 246, 0.4);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  &:active:not(:disabled) {
    transform: translateY(0);
  }
}

/* 测试结果样式 */
.test-result {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 500;
  
  &.success {
    background: rgba(34, 197, 94, 0.15);
    color: #16a34a;
    border: 1px solid rgba(34, 197, 94, 0.3);
  }
  
  &.error {
    background: rgba(239, 68, 68, 0.15);
    color: #dc2626;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }
}

/* 状态指示 */
.status-row {
  display: flex;
  gap: 20px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
}

.status-dot {
  width: 10px;
  height: 10px;
  min-width: 10px;
  border-radius: 50%;
  background: var(--gray-400);
  transition: all 0.3s;
  
  &.connected {
    background: var(--primary);
    box-shadow: 0 0 8px rgba(37, 99, 235, 0.5);
  }
  
  &.running {
    background: var(--accent-orange);
    box-shadow: 0 0 8px rgba(249, 115, 22, 0.5);
    animation: pulse 1.5s infinite;
  }
}

@keyframes pulse {
  0%, 100% { 
    transform: scale(1);
    opacity: 1;
  }
  50% { 
    transform: scale(1.2);
    opacity: 0.8;
  }
}

.status-label {
  color: var(--gray-400);
}

.status-value {
  color: var(--gray-700);
}

/* 左侧面板 */
.panel-left {
  background: var(--white);
  border-right: 1px solid var(--gray-200);
  padding: 16px;
  display: flex;
  flex-direction: row;
  gap: 16px;
  overflow: hidden;
  height: 100%;
  box-sizing: border-box;
  position: relative;
  transition: all 0.3s ease;
  
  // 折叠状态
  &.collapsed {
    padding: 8px 4px;
    gap: 4px;
    
    .list-section {
      opacity: 0;
      width: 0;
      padding: 0;
      margin: 0;
    }
    
    .collapse-hint {
      opacity: 1;
    }
  }
}

/* 折叠提示按钮 */
.collapse-hint {
  position: absolute;
  left: auto;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 1;
  transition: all 0.2s ease;
  z-index: 5;
  border-radius: 4px;
  background: var(--gray-100);
  
  &:hover {
    background: var(--primary-dim);
    
    .collapse-icon {
      color: var(--primary);
    }
  }
}

.collapse-icon {
  font-size: 14px;
  color: var(--gray-500);
  transition: all 0.2s ease;
  
  .panel-left.collapsed & {
    transform: rotate(0deg);
  }
  
  .panel-left:not(.collapsed) & {
    transform: rotate(180deg);
  }
}

/* 拖拽手柄 */
.resize-handle {
  position: absolute;
  right: -4px;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: col-resize;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  
  &::after {
    content: '';
    width: 4px;
    height: 48px;
    background: var(--gray-300);
    border-radius: 2px;
    transition: all 0.2s;
  }
  
  &:hover::after,
  &:active::after {
    background: var(--primary);
    height: 64px;
  }
}

.list-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.list-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--gray-600);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.select-all-btn {
  width: 22px;
  height: 22px;
  min-width: 22px;
  border: 1px solid var(--gray-300);
  background: transparent;
  border-radius: 4px;
  color: var(--gray-500);
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--gray-50);
  }
}

.item-list {
  flex: 1 1 auto;
  overflow-y: auto;
  margin: 0 -4px;
  padding: 0 4px;
  min-height: 0;
  height: 0;
}

.item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--white);
  
  &:hover {
    border-color: var(--primary);
    background: var(--gray-50);
    transform: translateX(2px);
  }
  
  &.selected {
    border-color: var(--primary);
    background: var(--primary-dim);
  }
}

.item-checkbox {
  width: 16px;
  height: 16px;
  border: 2px solid var(--gray-300);
  border-radius: 4px;
  margin-right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--white);
  font-size: 11px;
  flex-shrink: 0;
  transition: all 0.2s;
  
  .selected & {
    border-color: var(--primary);
    background: var(--primary);
    color: var(--white);
  }
}

.item-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--gray-700);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.item-delete, .item-edit {
  width: 24px;
  height: 24px;
  min-width: 24px;
  border: none;
  background: transparent;
  color: var(--gray-500);
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
  flex-shrink: 0;
  opacity: 0;
  transition: all 0.2s;
  margin-left: 4px;
  
  .item:hover & {
    opacity: 1;
  }
  
  &:hover {
    background: var(--accent-red);
    color: white;
  }
}

.item-edit {
  font-size: 12px;
  
  &:hover {
    background: var(--primary);
  }
}

/* Test Case Popover - 简洁风格 */
.case-popover {
  position: fixed;
  z-index: 100;
  background: var(--white);
  border: 1px solid var(--gray-300);
  border-radius: 6px;
  padding: 10px 12px;
  max-width: 300px;
  min-width: 200px;
  overflow-y: auto;
  font-size: 0.7rem;
  line-height: 1.5;
  color: var(--gray-700);
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  display: none;
  pointer-events: none;
  
  &.visible {
    display: block;
  }
}

.case-popover-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--gray-200);
}

.case-popover-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.case-popover-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.case-popover-label {
  color: var(--gray-500);
  font-size: 0.65rem;
}

.case-popover-value {
  color: var(--gray-900);
  word-break: break-word;
  font-weight: 500;
}

.add-btn {
  width: 100%;
  padding: 6px;
  background: transparent;
  border: 1px solid var(--gray-200);
  border-radius: 4px;
  color: var(--gray-500);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  cursor: pointer;
  transition: all 0.15s;
  
  &:hover {
    border-color: var(--gray-400);
    color: var(--gray-700);
  }
}

/* 中间任务卡片区域 */
.panel-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 12px;
}

.tasks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
}

.tasks-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--gray-400);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.tasks-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sort-select {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  padding: 4px 8px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: var(--white);
  color: var(--gray-700);
  cursor: pointer;
  outline: none;
  
  &:hover {
    border-color: var(--primary);
  }
  
  &:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }
}

.tasks-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--primary);
}

.task-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  grid-auto-rows: auto;
  gap: 12px;
  overflow: visible;
  align-items: start;
}

/* 任务卡片 */
.task-card {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  min-height: 180px;
  height: auto;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: visible;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  flex-shrink: 0;
  
  &:hover {
    border-color: var(--primary);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
    transform: translateY(-2px);
  }
  
  &.done {
    .task-status {
      background: var(--gray-200);
      color: var(--gray-600);
    }
  }
  
  &.error {
    .task-status {
      background: var(--accent-red);
      color: var(--white);
    }
  }
  
  &.stopped {
    .task-status {
      background: var(--gray-500);
      color: var(--white);
    }
    
    .task-progress-fill {
      background: var(--gray-500);
    }
  }
  
  /* 展开状态 */
  &.expanded {
    min-height: 400px;
    max-height: 500px;
    border-color: var(--gray-400);
  }
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.task-info {
  flex: 1;
}

.task-model {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 2px;
}

.task-case {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--gray-700);
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.task-action-btn {
  width: 22px;
  height: 22px;
  min-width: 22px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  transition: all 0.2s ease;
  
  &.stop {
    background: rgba(239, 68, 68, 0.15);
    color: var(--accent-red);
    
    &:hover {
      background: var(--accent-red);
      color: white;
    }
  }
  
  &.retry {
    background: rgba(59, 130, 246, 0.15);
    color: var(--primary);
    
    &:hover {
      background: var(--primary);
      color: white;
    }
  }
}

.task-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  padding: 3px 8px;
  border-radius: 10px;
  
  &.running {
    background: var(--accent-orange);
    color: var(--white);
  }
  
  &.done {
    background: var(--gray-600);
    color: var(--gray-300);
  }
  
  &.error {
    background: var(--accent-red);
    color: var(--white);
  }
}

/* 进度条 */
.task-progress {
  margin-bottom: 8px;
}

.task-progress-bar {
  height: 8px;
  background: var(--gray-200);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.task-progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 4px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  box-shadow: 
    0 0 10px rgba(37, 99, 235, 0.5),
    0 0 20px rgba(37, 99, 235, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
  
  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 50%;
    background: linear-gradient(
      to bottom,
      rgba(255, 255, 255, 0.25),
      transparent
    );
    border-radius: 4px 4px 0 0;
  }
}

.task-progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-600);
  margin-top: 6px;
  display: flex;
  justify-content: space-between;
}

/* 卡片内容区 */
.task-content {
  display: flex;
  flex-direction: column;
  overflow: visible;
  width: 100%;
  min-height: 30px;
}

.task-io {
  display: block;
  width: 100%;
  overflow: visible;
}

.task-io-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--gray-500);
  text-transform: uppercase;
  margin-bottom: 3px;
}

/* 轮次矩阵 - 自动伸缩 */
.round-matrix {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  overflow: visible;
  width: auto;
  min-width: 100%;
}

.round-btn {
  width: auto;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  background: var(--gray-200);
  color: var(--gray-500);
  border: none;
  
  &.pending {
    background: var(--gray-100);
    color: var(--gray-400);
    
    &:hover {
      background: var(--gray-300);
    }
  }
  
  &.running {
    border-radius: 50%;
    background: var(--accent-orange);
    color: var(--white);
    animation: breathe-pulse 1.5s ease-in-out infinite;
    
    &:hover {
      background: var(--primary-dark);
    }
  }
  
  &.done {
    background: var(--gray-900);
    color: var(--white);
    
    &:hover {
      transform: scale(1.1);
    }
  }
  
  &.error {
    background: var(--white);
    border: 2px solid var(--accent-red);
    color: var(--accent-red);
    font-size: 0.85rem;
    font-weight: 700;
    line-height: 1;
  }
}

@keyframes breathe-pulse {
  0% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.4);
  }
  50% {
    transform: scale(1.15);
    box-shadow: 0 0 0 6px rgba(249, 115, 22, 0);
  }
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(249, 115, 22, 0);
  }
}

@keyframes pulse-ring {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 69, 0, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(255, 69, 0, 0); }
}

/* Loading 动画 */
.loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--gray-600);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

/* 卡片指标 */
.task-metrics {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding-top: 6px;
  border-top: 1px solid var(--gray-100);
}

.task-metric {
  flex: 1;
  text-align: center;
}

.task-metric-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-900);
  
  &.duration {
    color: var(--accent-orange);
  }
}

.task-metric-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--gray-500);
  margin-top: 2px;
}

/* 最终结果 - 橙色主题 */
.task-result {
  display: none;
  margin-top: 8px;
  padding: 12px;
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border-radius: 8px;
  border: 2px solid #fdba74;
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.15);
  
  &.visible {
    display: block;
  }
}

.task-result-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #1f2937;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 100;
}

.task-result-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.task-result-item {
  text-align: center;
  padding: 8px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 6px;
  transition: all 0.2s ease;
  
  &:hover {
    background: rgba(255, 255, 255, 0.7);
    transform: translateY(-2px);
  }
}

.task-result-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.1rem;
  font-weight: 100;
  color: #1f2937;
  
  &.accent {
    color: #ea580c;
    font-size: 1.15rem;
  }
}

.task-result-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: #4b5563;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  font-weight: 100;
}

/* 校对结果统计样式 - 与上方一致 */
.task-result-item.eval-stat {
  border: none;  /* 移除细线边框 */
  background: rgba(255, 255, 255, 0.5);
  border-radius: 6px;
}

.task-result-value.eval-value {
  color: #000000;
  font-size: 1rem;
  
  &.correct {
    color: #22C55E;  /* 语义色：Success */
  }
  
  &.incorrect {
    color: #EF4444;  /* 语义色：Danger */
  }
}

/* 校对评分区域 - 紧凑单行显示 */
.eval-section {
  min-height: 28px;
  margin-top: 10px;
  border-radius: 4px;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px;
  transition: all 0.2s ease;
  
  /* 有数据时的样式 - 橙色主题 */
  &.has-data {
    border: 1px solid #fdba74;
    background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
    padding: 4px 8px;
  }
  
  /* 无数据时的样式 - 虚线边框 */
  &:not(.has-data) {
    border: 1px dashed #fdba74;
    padding: 4px 8px;
  }
}

/* 紧凑单行内联元素 */
.eval-inline-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: #b45309;
  font-weight: 500;
}

.eval-inline-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  font-weight: 700;
  
  &.correct {
    color: #16a34a;
  }
  
  &.incorrect {
    color: #dc2626;
  }
}

.eval-divider {
  color: #fdba74;
  font-size: 0.6rem;
}

.eval-correct {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: #16a34a;
  font-weight: 600;
}

.eval-incorrect {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: #dc2626;
  font-weight: 600;
}

.eval-accuracy {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: #ea580c;
  font-weight: 700;
}

/* 校对统计行 - 一行显示 */
.eval-stats {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
}

.eval-stat-row {
  display: flex;
  align-items: center;
  gap: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
}

.eval-stat-label {
  color: #666666;  /* 次要线条色 */
}

.eval-stat-value {
  font-weight: 600;
  color: #000000;  /* 主线条色 */
  
  &.correct {
    color: #22C55E;  /* 语义色：Success */
  }
  
  &.incorrect {
    color: #EF4444;  /* 语义色：Danger */
  }
  
  &.accuracy {
    color: #FF4500;  /* 强调色：Orange */
  }
  
  /* 行内显示的校对均分样式 */
  &.eval-inline {
    font-size: 0.75rem;
    font-weight: 600;
  }
}

/* 无数据占位文本 */
.eval-placeholder-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: #b45309;
}

/* 空状态 */
.empty-tasks {
  grid-column: 1 / -1;
  min-height: calc(100vh - 250px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--gray-400);
  font-size: 0.9rem;
  gap: 12px;
  padding: 40px;
  
  .empty-icon {
    font-size: 64px;
    opacity: 0.4;
  }
  
  .empty-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1rem;
    color: var(--gray-500);
  }
  
  .empty-hint {
    font-size: 0.8rem;
    color: var(--gray-400);
    margin-top: 4px;
  }
}

/* 浮动日志面板 - 完整样式 */
.log-panel {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  overflow: visible;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s ease;
  
  /* 最小化/隐藏状态 - 显示为圆形小球 */
  &.minimized {
    width: 80px !important;
    height: 80px !important;
    min-height: 80px !important;
    border-radius: 50% !important;
    cursor: pointer;
    
    .log-panel-header {
      padding: 20px;
      justify-content: center;
      min-height: 80px;
    }
    
    .log-header-left, .log-header-right {
      flex-direction: column;
      gap: 4px;
    }
    
    .log-header-right {
      display: none;
    }
    
    .log-area, .log-resize-handle {
      display: none;
    }
    
    /* 小球内显示进度 */
    .log-panel-header::after {
      content: '📋';
      font-size: 24px;
    }
  }
  
  /* 拖拽时样式 */
  &:active {
    cursor: moving;
  }
  
  /* 拖拽时的高亮效果 */
  &.drag-over {
    box-shadow: 0 8px 32px rgba(37, 99, 235, 0.25), 0 0 0 2px var(--primary);
  }
  
  /* 调整大小时的高亮效果 */
  &.resizing {
    box-shadow: 0 8px 32px rgba(37, 99, 235, 0.25), 0 0 0 2px var(--primary);
    cursor: nwse-resize;
  }
}

/* 四边调整大小手柄 - 通用样式 */
.log-resize-handle {
  position: absolute;
  z-index: 20;
  background: transparent;
  transition: background 0.15s ease;
  
  &:hover, &:active {
    background: rgba(37, 99, 235, 0.15);
  }
}

/* 顶部手柄 */
.log-resize-handle-top {
  top: -4px;
  left: 12px;
  right: 12px;
  height: 8px;
  cursor: n-resize;
  border-radius: 4px 4px 0 0;
  
  &::after {
    content: '';
    position: absolute;
    top: 3px;
    left: 50%;
    transform: translateX(-50%);
    width: 40px;
    height: 3px;
    background: var(--gray-400);
    border-radius: 2px;
    transition: background 0.15s ease;
  }
  
  &:hover::after, &:active::after {
    background: var(--primary);
  }
}

/* 底部手柄 */
.log-resize-handle-bottom {
  bottom: -4px;
  left: 12px;
  right: 12px;
  height: 8px;
  cursor: s-resize;
  border-radius: 0 0 4px 4px;
  
  &::after {
    content: '';
    position: absolute;
    bottom: 3px;
    left: 50%;
    transform: translateX(-50%);
    width: 40px;
    height: 3px;
    background: var(--gray-400);
    border-radius: 2px;
    transition: background 0.15s ease;
  }
  
  &:hover::after, &:active::after {
    background: var(--primary);
  }
}

/* 左侧手柄 */
.log-resize-handle-left {
  left: -6px;
  top: 44px;
  bottom: 40px;
  width: 14px;
  cursor: w-resize;
  border-radius: 6px 0 0 6px;
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.15), transparent);
  opacity: 0;
  transition: all 0.2s ease;
  
  &:hover, &:active {
    opacity: 1;
    background: linear-gradient(90deg, rgba(59, 130, 246, 0.25), transparent);
  }
  
  &::after {
    content: '';
    position: absolute;
    left: 5px;
    top: 50%;
    transform: translateY(-50%);
    width: 4px;
    height: 40px;
    background: var(--primary);
    border-radius: 2px;
    opacity: 0;
    transition: opacity 0.15s ease;
    box-shadow: 0 0 8px rgba(37, 99, 235, 0.4);
  }
  
  &:hover::after, &:active::after {
    opacity: 1;
  }
}

/* 右侧手柄 */
.log-resize-handle-right {
  right: -6px;
  top: 44px;
  bottom: 40px;
  width: 14px;
  cursor: e-resize;
  border-radius: 0 6px 6px 0;
  background: linear-gradient(-90deg, rgba(59, 130, 246, 0.15), transparent);
  opacity: 0;
  transition: all 0.2s ease;
  
  &:hover, &:active {
    opacity: 1;
    background: linear-gradient(-90deg, rgba(59, 130, 246, 0.25), transparent);
  }
  
  &::after {
    content: '';
    position: absolute;
    right: 5px;
    top: 50%;
    transform: translateY(-50%);
    width: 4px;
    height: 40px;
    background: var(--primary);
    border-radius: 2px;
    opacity: 0;
    transition: opacity 0.15s ease;
    box-shadow: 0 0 8px rgba(37, 99, 235, 0.4);
  }
  
  &:hover::after, &:active::after {
    opacity: 1;
  }
}

/* 隐藏不需要的手柄样式 */
.log-panel .log-resize-handle:not(.log-resize-handle-top):not(.log-resize-handle-bottom):not(.log-resize-handle-left):not(.log-resize-handle-right) {
  position: relative;
  height: 10px;
  cursor: row-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-100);
  border-top: 1px solid var(--gray-200);
  
  &::after {
    content: '⋮⋮';
    font-size: 10px;
    color: var(--gray-400);
    letter-spacing: 2px;
    transition: all 0.2s;
    position: static;
    width: auto;
    height: auto;
    background: transparent;
    transform: none;
    border: none;
    border-radius: 0;
  }
  
  &:hover::after, &:active::after {
    color: var(--primary);
  }
}

/* 日志面板头部 */
.log-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: var(--gray-50);
  border-bottom: 1px solid var(--gray-200);
  min-height: 44px;
  box-sizing: border-box;
  flex-shrink: 0;
  cursor: move;  /* 提示可拖拽 */
  user-select: none;
  
  &:hover {
    background: var(--gray-100);
  }
}

.log-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-800);
}

.log-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: var(--gray-500);
}

/* 搜索框 */
.log-search {
  position: relative;
  display: flex;
  align-items: center;
  
  input {
    width: 120px;
    padding: 4px 24px 4px 8px;
    border: 1px solid var(--gray-300);
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    background: var(--white);
    color: var(--gray-900);
    transition: all 0.2s ease;
    
    &::placeholder {
      color: var(--gray-400);
    }
    
    &:focus {
      outline: none;
      border-color: var(--primary);
      width: 160px;
      box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
    }
  }
  
  &.active input {
    border-color: var(--primary);
  }
  
  .log-search-clear {
    position: absolute;
    right: 6px;
    cursor: pointer;
    color: var(--gray-400);
    font-size: 0.75rem;
    padding: 2px;
    
    &:hover {
      color: var(--gray-700);
    }
  }
}

/* 过滤按钮组 */
.log-filter-group {
  display: flex;
  gap: 4px;
}

.log-filter-btn {
  padding: 4px 8px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: var(--white);
  color: var(--gray-600);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: var(--gray-400);
    color: var(--gray-700);
  }
  
  &.active {
    background: var(--primary);
    border-color: var(--primary);
    color: var(--white);
  }
}

/* 操作按钮 */
.log-action-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: var(--white);
  color: var(--gray-600);
  font-size: 0.7rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--gray-50);
  }
  
  &.active {
    background: var(--primary-dim);
    border-color: var(--primary);
    color: var(--primary);
  }
}

/* 底部日志 - 拖拽手柄 */
.log-resize-handle {
  height: 10px;
  cursor: row-resize;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-100);
  border-top: 1px solid var(--gray-200);
  flex-shrink: 0;
  
  &::after {
    content: '⋮⋮';
    font-size: 10px;
    color: var(--gray-400);
    letter-spacing: 2px;
    transition: all 0.2s;
  }
  
  &:hover::after,
  &:active::after {
    color: var(--primary);
  }
}

.log-area {
  position: relative;
  background: linear-gradient(180deg, var(--gray-50) 0%, var(--gray-100) 100%);
  border-top: 1px solid var(--gray-200);
  padding: 10px 16px;
  overflow-x: auto;
  overflow-y: auto;
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  
  /* 日志容器滚动条美化 */
  &::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  
  &::-webkit-scrollbar-track {
    background: var(--gray-200);
    border-radius: 3px;
  }
  
  &::-webkit-scrollbar-thumb {
    background: var(--gray-400);
    border-radius: 3px;
    
    &:hover {
      background: var(--gray-500);
    }
  }
}

.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-400);
  white-space: nowrap;
  flex-shrink: 0;
}

.log-time {
  color: var(--gray-600);
}

.log-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.65rem;
  background: var(--gray-700);
  color: var(--gray-300);
  
  &.model {
    background: var(--gray-700);
    color: var(--primary);
  }
  
  &.case {
    background: var(--gray-700);
    color: var(--gray-300);
  }
  
  &.round {
    background: var(--gray-700);
    color: var(--gray-300);
  }
  
  &.error {
    background: var(--gray-700);
    color: var(--accent-red);
  }
}

/* Modal 遮罩层 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
  
  &.show {
    opacity: 1;
    visibility: visible;
  }
}

/* Modal - 简洁风格 */
.modal {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  padding: 24px;
  width: 480px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  transform: scale(0.95) translateY(10px);
  opacity: 0;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
  
  .modal-overlay.show & {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
  
  &.animating {
    animation: modalBounceIn 0.4s ease;
  }
}

@keyframes modalBounceIn {
  0% { transform: scale(0.95); opacity: 0; }
  50% { transform: scale(1.02); }
  100% { transform: scale(1); opacity: 1; }
}

.modal-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--gray-200);
}

.form-group {
  margin-bottom: 14px;
}

.form-label {
  font-size: 0.7rem;
  color: var(--gray-600);
  margin-bottom: 6px;
  display: block;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  color: var(--gray-900);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  transition: all 0.2s ease;
  
  &::placeholder {
    color: var(--gray-400);
  }
  
  &:focus {
    outline: none;
    border-color: var(--primary);
    background: var(--white);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }
  
  &:hover:not(:focus) {
    border-color: var(--gray-300);
    background: var(--white);
  }
  
  textarea.form-input {
    min-height: 80px;
    resize: vertical;
    line-height: 1.5;
  }
}

/* Toast 提示优化 */
.toast {
  position: fixed !important;
  bottom: 90px !important;
  left: 50% !important;
  transform: translateX(-50%) translateY(20px);
  background: #111827 !important;
  color: #ffffff !important;
  padding: 8px 16px !important;
  border-radius: 6px !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  opacity: 0;
  visibility: hidden;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 200;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
  white-space: nowrap;
  height: auto !important;
  max-height: 40px !important;
  max-width: 300px !important;
  min-height: 0 !important;
  line-height: 1.4 !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  box-sizing: border-box !important;
  overflow: hidden !important;
  
  &::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #ffffff !important;
    flex-shrink: 0;
  }
  
  &.show {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) translateY(0);
  }
  
  &.success {
    background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
    color: var(--white);
    
    &::before {
      background: var(--white);
    }
  }
  
  &.error {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: var(--white);
    
    &::before {
      background: var(--white);
    }
  }
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

/* 任务详情模态框 - 浅色风格 */
.task-detail-modal {
  width: 700px;
  max-width: 95vw;
  max-height: 85vh;
  overflow-y: auto;
  
  .modal-title {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .task-detail-content {
    max-height: calc(85vh - 100px);
    overflow-y: auto;
  }
}

.task-detail-subtitle {
  font-size: 0.8rem;
  font-weight: 400;
  color: var(--gray-500);
}

.task-detail-content {
  max-height: 60vh;
  overflow-y: auto;
}

.task-detail-summary {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--gray-100);
  border-radius: 8px;
}

.detail-stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  
  @media (max-width: 600px) {
    grid-template-columns: repeat(2, 1fr);
  }
}

.detail-stat-item {
  text-align: center;
  
  &.accent .detail-stat-value {
    color: var(--primary);
    font-size: 1.1rem;
  }
}

.detail-stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  font-weight: 600;
  color: var(--gray-900);
}

.detail-stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: var(--gray-500);
  margin-top: 4px;
}

.task-detail-rounds {
  margin-top: 16px;
}

.detail-rounds-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--gray-500);
  margin-bottom: 12px;
  text-transform: uppercase;
}

.detail-rounds-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-round-item {
  padding: 12px;
  background: var(--gray-100);
  border-radius: 8px;
  border-left: 3px solid var(--gray-400);
  
  &.done {
    border-left-color: var(--primary);
  }
  
  &.error {
    border-left-color: var(--accent-red);
  }
  
  &.running {
    border-left-color: var(--accent-orange);
  }
}

.detail-round-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.detail-round-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--gray-900);
}

.detail-round-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 4px;
  
  &.done {
    background: var(--primary-dim);
    color: var(--primary);
  }
  
  &.error {
    background: rgba(255,107,107,0.15);
    color: var(--accent-red);
  }
  
  &.running {
    background: rgba(249, 115, 22, 0.15);
    color: var(--accent-orange);
  }
  
  &.pending {
    background: var(--gray-200);
    color: var(--gray-500);
  }
}

.detail-round-metrics {
  font-size: 0.7rem;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--gray-200);
}

.metric-row {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.metric-label {
  color: var(--gray-500);
}

.metric-value {
  color: var(--primary);
  font-family: 'JetBrains Mono', monospace;
}

.detail-round-output {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--gray-200);
}

.output-label {
  font-size: 0.65rem;
  color: var(--gray-500);
  margin-bottom: 4px;
}

.output-content {
  font-size: 0.7rem;
  color: var(--gray-700);
  background: var(--gray-200);
  padding: 8px;
  border-radius: 4px;
  max-height: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-round-error {
  margin-top: 8px;
  padding: 8px;
  background: rgba(255,107,107,0.1);
  border-radius: 4px;
  font-size: 0.7rem;
  color: var(--accent-red);
}

/* 校对结果展示样式 */
.detail-round-evaluation {
  margin-top: 8px;
  padding: 8px;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 6px;
}

.evaluation-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.7rem;
  
  &.correct {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.3);
    
    .evaluation-icon {
      color: #22c55e;
    }
    
    .evaluation-rate {
      color: #16a34a;
    }
  }
  
  &.incorrect {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.25);
    
    .evaluation-icon {
      color: #ef4444;
    }
    
    .evaluation-rate {
      color: #dc2626;
    }
  }
}

.evaluation-icon {
  font-size: 0.85rem;
  font-weight: bold;
}

.evaluation-label {
  color: var(--gray-600);
}

.evaluation-rate {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
}

.evaluation-reason {
  margin-top: 6px;
  font-size: 0.65rem;
  color: var(--gray-600);
  line-height: 1.4;
}

/* 输入/输出显示区域 */
.detail-round-io {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--gray-200);
}

.io-section {
  margin-bottom: 8px;
  
  &:last-child {
    margin-bottom: 0;
  }
}

.io-label {
  font-size: 0.65rem;
  color: var(--gray-500);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.io-content {
  font-size: 0.7rem;
  padding: 8px;
  border-radius: 4px;
  max-height: 100px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  
  &.input {
    background: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.2);
    color: var(--gray-700);
  }
  
  &.output {
    background: rgba(34, 197, 94, 0.08);
    border: 1px solid rgba(34, 197, 94, 0.2);
    color: var(--gray-700);
  }
}

/* 历史记录模态框 - 浅色风格 */
.history-modal {
  width: 800px;
  max-width: 95vw;
  max-height: 85vh;
  overflow-y: auto;
  
  .modal-body {
    max-height: calc(85vh - 120px);
    overflow-y: auto;
  }
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--gray-100);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
  
  &:hover {
    background: var(--gray-200);
    border-color: var(--gray-300);
  }
}

.history-info {
  flex: 1;
}

.history-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: var(--gray-900);
}

.history-meta {
  font-size: 0.7rem;
  color: var(--gray-500);
  margin-top: 4px;
}

.history-stats {
  display: flex;
  gap: 16px;
}

.history-stat {
  text-align: center;
}

.history-stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  color: var(--gray-900);
}

.history-stat-label {
  font-size: 0.6rem;
  color: var(--gray-500);
}

.history-actions {
  display: flex;
  gap: 8px;
}

/* 模型 Popover - 简洁风格 */
.model-popover {
  position: fixed;
  z-index: 100;
  background: var(--white);
  border: 1px solid var(--gray-300);
  border-radius: 6px;
  padding: 10px 12px;
  max-width: 260px;
  min-width: 180px;
  overflow-y: auto;
  font-size: 0.7rem;
  line-height: 1.5;
  color: var(--gray-700);
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  display: none;
  pointer-events: none;
  
  &.visible {
    display: block;
  }
}

.model-popover-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--gray-200);
}

.model-popover-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-popover-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.model-popover-label {
  color: var(--gray-500);
  flex-shrink: 0;
}

.model-popover-value {
  color: var(--gray-900);
  text-align: right;
  word-break: break-word;
  font-weight: 500;
}

/* 轮次 Popover - 简洁风格 */
.round-popover {
  position: fixed;
  z-index: 100;
  background: var(--white);
  border: 1px solid var(--gray-300);
  border-radius: 6px;
  padding: 10px 12px;
  max-width: 360px;
  max-height: 180px;
  overflow-y: auto;
  font-size: 0.65rem;
  line-height: 1.5;
  color: var(--gray-700);
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  display: none;
  pointer-events: none;
  
  &.visible {
    display: block;
  }
  
  &.streaming {
    border: 1px dashed var(--accent-purple);
    background: rgba(139, 92, 246, 0.05);
  }
}

.round-popover-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: var(--gray-900);
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--gray-200);
  display: flex;
  align-items: center;
  gap: 4px;
}

.round-popover-content {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--gray-600);
}

.round-popover-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-500);
}

/* 卡片展开过渡动画 */
.card-expand-transition {
  position: fixed;
  z-index: 1000;
  background: var(--gray-800);
  border: 1px solid var(--gray-700);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  opacity: 0;
  pointer-events: none;
  overflow: hidden;
  
  &.visible {
    opacity: 1;
  }
  
  .transition-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
    height: 100%;
  }
  
  .transition-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .transition-model {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--primary);
  }
  
  .transition-case {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.85rem;
    color: var(--white);
  }
  
  .transition-progress {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .transition-progress-bar {
    height: 6px;
    background: var(--gray-700);
    border-radius: 3px;
    overflow: hidden;
  }
  
  .transition-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), #ff6b2c);
    border-radius: 3px;
  }
  
  .transition-progress-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: var(--gray-400);
  }
  
  .transition-stats {
    display: flex;
    gap: 12px;
    margin-top: 4px;
    padding-top: 8px;
    border-top: 1px solid var(--gray-700);
  }
  
  .transition-stat {
    flex: 1;
    text-align: center;
  }
  
  .transition-stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--white);
  }
  
  .transition-stat-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.5rem;
    color: var(--gray-500);
  }
}

/* 展开内容区域 */
.task-expand-content {
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: all 0.3s ease;
  
  .expanded & {
    max-height: 400px;
    opacity: 1;
    overflow-y: auto;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--gray-700);
  }
}

.task-expand-summary {
  margin-bottom: 12px;
  padding: 12px;
  background: var(--gray-700);
  border-radius: 8px;
}

.expand-stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.expand-stat-item {
  text-align: center;
  
  &.accent .expand-stat-value {
    color: var(--accent-cyan);
    font-size: 0.95rem;
  }
}

.expand-stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--white);
}

.expand-stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: var(--gray-400);
  margin-top: 2px;
}

.task-expand-rounds {
  margin-top: 8px;
}

.expand-rounds-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: var(--gray-400);
  margin-bottom: 8px;
  text-transform: uppercase;
}

.expand-rounds-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.expand-round-item {
  padding: 8px;
  background: var(--gray-700);
  border-radius: 6px;
  border-left: 3px solid var(--gray-600);
  
  &.done {
    border-left-color: var(--primary);
  }
  
  &.error {
    border-left-color: var(--accent-red);
  }
  
  &.running {
    border-left-color: var(--accent-purple);
  }
  
  &.pending {
    opacity: 0.6;
  }
}

.expand-round-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.expand-round-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: var(--white);
}

.expand-round-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  padding: 1px 6px;
  border-radius: 3px;
  
  &.done {
    background: var(--primary-dim);
    color: var(--primary);
  }
  
  &.error {
    background: rgba(255,107,107,0.15);
    color: var(--accent-red);
  }
  
  &.running {
    background: rgba(139, 92, 246, 0.15);
    color: var(--accent-purple);
  }
  
  &.pending {
    background: var(--gray-600);
    color: var(--gray-400);
  }
}

.expand-round-metrics {
  font-size: 0.6rem;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
}

.expand-metric-label {
  color: var(--gray-500);
}

.expand-metric-value {
  color: var(--accent-cyan);
  font-family: 'JetBrains Mono', monospace;
}

.expand-round-error {
  margin-top: 4px;
  font-size: 0.6rem;
  color: var(--accent-red);
}

/* 折叠提示 */
.expand-hint {
  text-align: center;
  padding: 8px;
  margin-top: 8px;
  color: var(--gray-500);
  font-size: 0.65rem;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px dashed var(--gray-700);
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Messages 编辑器样式 */
.messages-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-item {
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 10px;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.message-role-select {
  padding: 4px 8px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  background: var(--white);
  color: var(--gray-700);
  cursor: pointer;
  
  &:focus {
    outline: none;
    border-color: var(--primary);
  }
}

.message-delete-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--gray-400);
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
  transition: all 0.2s;
  
  &:hover {
    background: var(--accent-red);
    color: white;
  }
}

.message-content {
  min-height: 60px !important;
}

.add-message-btn {
  width: 100%;
  padding: 10px;
  background: transparent;
  border: 1px dashed var(--gray-300);
  border-radius: 8px;
  color: var(--gray-500);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--gray-50);
  }
}

/* 响应式 - 只影响任务卡片布局，不影响左侧面板宽度 */
@media (max-width: 1024px) {
  .task-cards {
    grid-template-columns: 1fr;
  }
  
  .history-modal {
    width: 90vw;
  }
}

@media (max-width: 768px) {
  .task-cards {
    grid-template-columns: 1fr;
  }
  
  .header {
    flex-wrap: wrap;
    gap: 12px;
  }
}

/* ====== 日志区域增强样式 ====== */

/* 日志头部 */
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: var(--gray-100);
  border-top: 1px solid var(--gray-200);
  border-bottom: 1px solid var(--gray-200);
  min-height: 36px;
  box-sizing: border-box;
  flex-shrink: 0;
}

.log-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--gray-700);
}

.log-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: var(--gray-500);
}

/* 搜索框 */
.log-search {
  position: relative;
  display: flex;
  align-items: center;
  
  input {
    width: 140px;
    padding: 4px 24px 4px 8px;
    border: 1px solid var(--gray-300);
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    background: var(--white);
    color: var(--gray-900);
    transition: all 0.2s ease;
    
    &::placeholder {
      color: var(--gray-400);
    }
    
    &:focus {
      outline: none;
      border-color: var(--primary);
      width: 180px;
      box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
    }
  }
  
  &.active input {
    border-color: var(--primary);
  }
  
  .log-search-clear {
    position: absolute;
    right: 6px;
    cursor: pointer;
    color: var(--gray-400);
    font-size: 0.75rem;
    padding: 2px;
    
    &:hover {
      color: var(--gray-700);
    }
  }
}

/* 过滤按钮组 */
.log-filter-group {
  display: flex;
  gap: 4px;
}

.log-filter-btn {
  padding: 4px 10px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: var(--white);
  color: var(--gray-600);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: var(--gray-400);
    color: var(--gray-700);
  }
  
  &.active {
    background: var(--primary);
    border-color: var(--primary);
    color: var(--white);
  }
}

/* 操作按钮 */
.log-action-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: var(--white);
  color: var(--gray-600);
  font-size: 0.7rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--gray-50);
  }
  
  &.active {
    background: var(--primary-dim);
    border-color: var(--primary);
    color: var(--primary);
  }
}

/* 日志项增强样式 */
.log-item {
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid transparent;
  
  &:hover {
    background: var(--gray-200);
    border-color: var(--gray-300);
  }
  
  /* 日志级别颜色 */
  &.level-error {
    .log-tag {
      background: rgba(239, 68, 68, 0.15);
      color: #ef4444;
    }
    .log-msg {
      color: #ef4444;
    }
  }
  
  &.level-warning {
    .log-tag {
      background: rgba(245, 158, 11, 0.15);
      color: #f59e0b;
    }
    .log-msg {
      color: #f59e0b;
    }
  }
  
  &.level-success {
    .log-tag {
      background: rgba(34, 197, 94, 0.15);
      color: #22c55e;
    }
    .log-msg {
      color: #22c55e;
    }
  }
  
  &.level-running {
    .log-tag {
      background: rgba(59, 130, 246, 0.15);
      color: #3b82f6;
    }
    .log-msg {
      color: #3b82f6;
    }
  }
  
  &.level-info {
    .log-tag {
      background: rgba(99, 102, 241, 0.15);
      color: #6366f1;
    }
    .log-msg {
      color: #6366f1;
    }
  }
  
  &.level-default {
    .log-tag {
      background: var(--gray-700);
      color: var(--gray-300);
    }
  }
  
  /* 新日志动画 */
  &.new-log {
    background: rgba(59, 130, 246, 0.08);
    border-color: rgba(59, 130, 246, 0.2);
    animation: logFadeIn 0.3s ease;
  }
}

@keyframes logFadeIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* 日志消息 */
.log-msg {
  color: var(--gray-700);
  max-width: 500px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* NEW 标签 */
.log-new-badge {
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--primary);
  color: var(--white);
  font-size: 0.5rem;
  font-weight: 600;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 日志空状态 */
.log-empty {
  width: 100%;
  padding: 20px;
  text-align: center;
  color: var(--gray-500);
  font-size: 0.75rem;
  font-family: 'JetBrains Mono', monospace;
}

/* ===== AI 分析 Modal 样式 ===== */
.ai-analysis-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.3s ease;
}

.ai-analysis-modal {
  width: min(900px, 90vw);
  max-height: 85vh;
  background: #FFFFFF;
  border: 1px solid var(--gray-300);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  animation: slideUp 0.3s ease;
}

.ai-analysis-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--gray-200);
}

.ai-analysis-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.95rem;
  font-weight: 600;
  color: #000000;
  font-family: 'Space Grotesk', sans-serif;
}

.ai-analysis-title-icon {
  width: 24px;
  height: 24px;
  border: 2px solid var(--accent);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  font-size: 0.7rem;
}

.ai-analysis-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--gray-200);
  border-radius: 4px;
  color: var(--gray-600);
  cursor: pointer;
  transition: all 0.15s ease;
}

.ai-analysis-close:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.ai-analysis-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  min-height: 300px;
}

.ai-loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  height: 200px;
  color: var(--gray-600);
}

.ai-loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--gray-200);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.ai-loading-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: var(--gray-500);
}

.ai-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 200px;
}

.ai-error-icon {
  width: 40px;
  height: 40px;
  border: 2px solid var(--danger);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--danger);
}

.ai-error-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: var(--danger);
}

.ai-report-container {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.8;
  color: #333;
}

.ai-report-container :deep(h1.ai-h1) {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.5rem;
  font-weight: 700;
  color: #000;
  border-bottom: 2px solid var(--accent);
  padding-bottom: 8px;
  margin: 24px 0 16px 0;
}

.ai-report-container :deep(h2.ai-h2) {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.15rem;
  font-weight: 600;
  color: #000;
  border-bottom: 1px solid var(--gray-200);
  padding-bottom: 6px;
  margin: 20px 0 12px 0;
}

.ai-report-container :deep(h3.ai-h3) {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  color: #000;
  margin: 16px 0 8px 0;
}

.ai-report-container :deep(.ai-p) {
  margin: 8px 0;
  font-size: 0.88rem;
  color: #333;
}

.ai-report-container :deep(strong) {
  font-weight: 600;
  color: #000;
}

.ai-report-container :deep(em) {
  color: var(--gray-600);
}

.ai-report-container :deep(.ai-li) {
  margin: 4px 0 4px 20px;
  font-size: 0.88rem;
  list-style-type: disc;
}

.ai-report-container :deep(.ai-code-block) {
  background: #f5f5f5;
  border: 1px solid var(--gray-200);
  border-radius: 4px;
  padding: 12px 16px;
  margin: 12px 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
}

.ai-report-container :deep(.ai-inline-code) {
  background: #f5f5f5;
  border: 1px solid var(--gray-200);
  border-radius: 3px;
  padding: 2px 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
}

.ai-report-container :deep(.ai-hr) {
  border: none;
  border-top: 1px solid var(--gray-200);
  margin: 20px 0;
}

.ai-analysis-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-top: 1px solid var(--gray-200);
  gap: 12px;
}

.ai-analysis-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--gray-400);
}

.ai-analysis-actions {
  display: flex;
  gap: 8px;
}

.ai-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: transparent;
  color: #000;
  font-size: 0.78rem;
  font-family: 'Space Grotesk', sans-serif;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ai-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.ai-btn-primary {
  background: transparent;
  border: 1px solid var(--gray-300);
}

.ai-btn-primary:hover {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.ai-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  border-color: var(--gray-200);
}

/* header AI 分析按钮样式 */
.header-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: transparent;
  color: #000;
  font-size: 0.78rem;
  font-family: 'Space Grotesk', sans-serif;
  cursor: pointer;
  transition: all 0.15s ease;
}

.header-action-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.header-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 机器人图标脉冲动画 */
.ai-pulse {
  animation: pulse 2s ease-in-out infinite;
}

/* 打字光标动画 */
.ai-cursor {
  display: inline-block;
  width: 8px;
  height: 16px;
  background: var(--accent);
  margin-left: 2px;
  animation: blink 1s step-end infinite;
  vertical-align: text-bottom;
}
</style>
