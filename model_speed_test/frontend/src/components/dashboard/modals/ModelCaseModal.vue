<template>
  <div class="modal-overlay" :class="{ show: visible }" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-title">
        {{ isEditing ? (type === 'model' ? 'Edit Model' : 'Edit Test Case') : (type === 'model' ? 'Add Model' : 'Add Test Case') }}
      </div>
      
      <!-- Model Form -->
      <div v-if="type === 'model'">
        <div class="form-group">
          <label class="form-label">Name</label>
          <input 
            type="text" 
            class="form-input" 
            v-model="modelForm.name" 
            placeholder="My Model" 
          />
        </div>
        
        <!-- Provider 选择 -->
        <div class="form-group">
          <label class="form-label">Provider</label>
          <select class="form-input" v-model="modelForm.provider">
            <option value="openai">OpenAI 兼容</option>
            <option value="anthropic">Anthropic Claude</option>
            <option value="gemini">Google Gemini</option>
            <option value="lmstudio">LM Studio</option>
            <option value="ollama">Ollama</option>
            <option value="azure">Azure OpenAI</option>
          </select>
        </div>
        
        <div class="form-group">
          <label class="form-label">Endpoint</label>
          <input 
            type="text" 
            class="form-input" 
            v-model="modelForm.endpoint" 
            :placeholder="endpointPlaceholder" 
          />
        </div>
        <div class="form-group">
          <label class="form-label">API Key</label>
          <input 
            type="text" 
            class="form-input" 
            v-model="modelForm.api_key" 
            placeholder="sk-..." 
          />
        </div>
        <div class="form-group">
          <label class="form-label">Model</label>
          <input 
            type="text" 
            class="form-input" 
            v-model="modelForm.model" 
            placeholder="gpt-4o-mini" 
          />
        </div>
        
        <!-- 模型参数配置 -->
        <div class="params-section">
          <div class="params-title">模型参数</div>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Temperature</label>
              <input 
                type="number" 
                class="form-input" 
                v-model.number="modelForm.temperature" 
                placeholder="0.7"
                step="0.1"
                min="0"
                max="2"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Top P</label>
              <input 
                type="number" 
                class="form-input" 
                v-model.number="modelForm.top_p" 
                placeholder="1.0"
                step="0.1"
                min="0"
                max="1"
              />
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Max Tokens</label>
              <input 
                type="number" 
                class="form-input" 
                v-model.number="modelForm.max_tokens" 
                placeholder="4096"
                step="1"
                min="1"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Presence Penalty</label>
              <input 
                type="number" 
                class="form-input" 
                v-model.number="modelForm.presence_penalty" 
                placeholder="0.0"
                step="0.1"
                min="-2"
                max="2"
              />
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Frequency Penalty</label>
              <input 
                type="number" 
                class="form-input" 
                v-model.number="modelForm.frequency_penalty" 
                placeholder="0.0"
                step="0.1"
                min="-2"
                max="2"
              />
            </div>
            <div class="form-group checkbox-group">
              <label class="form-label">思考模式</label>
              <label class="checkbox-label">
                <input 
                  type="checkbox" 
                  v-model="modelForm.thinking_enabled" 
                />
                <span>启用深度思考</span>
              </label>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Case Form -->
      <div v-else>
        <div class="form-group">
          <label class="form-label">Name</label>
          <input type="text" class="form-input" v-model="caseForm.name" placeholder="Test Case" />
        </div>
        
        <!-- Folder 选择器 -->
        <div class="form-group">
          <label class="form-label">所属文件夹</label>
          <select class="form-input" v-model="caseForm.folder_id">
            <option value="">未分类（根目录）</option>
            <option v-for="opt in folderOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
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
                <select
                  class="message-mode-select"
                  v-model="msg._mode"
                  @change="onModeChange(msg)"
                  title="内容形态"
                >
                  <option value="text">文本</option>
                  <option value="multipart">多模态</option>
                </select>
                <button class="message-delete-btn" @click="$emit('remove-message', index)" title="删除">×</button>
              </div>

              <!-- 纯文本模式 -->
              <textarea
                v-if="msg._mode === 'text'"
                class="form-input message-content"
                v-model="msg.content"
                placeholder="输入消息内容..."
              ></textarea>

              <!-- 多模态分块模式 -->
              <div v-else class="parts-editor">
                <div
                  v-for="(part, pIdx) in msg.content"
                  :key="pIdx"
                  class="part-item"
                >
                  <div class="part-header">
                    <select class="part-type-select" v-model="part.type">
                      <option value="text">文本</option>
                      <option value="image_url">图片</option>
                    </select>
                    <button class="part-delete-btn" @click="removePart(msg, pIdx)" title="删除分块">×</button>
                  </div>

                  <textarea
                    v-if="part.type === 'text'"
                    class="form-input part-text"
                    v-model="part.text"
                    placeholder="输入文本..."
                  ></textarea>

                  <div v-else class="part-image">
                    <input
                      type="text"
                      class="form-input part-image-url"
                      v-model="part.image_url.url"
                      placeholder="图片 URL 或 data:image/...;base64,..."
                    />
                    <label class="file-pick-label">
                      <input
                        type="file"
                        accept="image/*"
                        class="file-pick-input"
                        @change="onImagePick(part, $event)"
                      />
                      <span class="file-pick-btn">📁 选择本地图片</span>
                    </label>
                    <img
                      v-if="part.image_url && part.image_url.url"
                      :src="part.image_url.url"
                      class="part-image-preview"
                      alt="预览"
                    />
                  </div>
                </div>
                <div class="parts-toolbar">
                  <button class="part-add-btn" @click="addPart(msg, 'text')">+ 文本</button>
                  <button class="part-add-btn" @click="addPart(msg, 'image_url')">+ 图片</button>
                </div>
              </div>
            </div>
            <button class="add-message-btn" @click="$emit('add-message')">+ 添加消息</button>
          </div>
        </div>
        
        <div class="form-group">
          <label class="form-label">Max Tokens</label>
          <input type="number" class="form-input" v-model="caseForm.max_tokens" value="500" />
        </div>
        
        <!-- 标准答案配置 -->
        <div class="eval-section">
          <div class="eval-title">质量评估配置（可选）</div>
          
          <div class="form-group">
            <label class="form-label">标准答案</label>
            <textarea 
              class="form-input" 
              v-model="caseForm.expected_output" 
              placeholder="输入标准答案，用于计算偏离度..."
              rows="3"
            ></textarea>
          </div>
          
          <div class="form-group">
            <label class="form-label">校对模型</label>
            <select class="form-input" v-model="caseForm.eval_model">
              <option value="">无（使用被测模型）</option>
              <option v-for="model in availableModels" :key="model.name" :value="model.name">
                {{ model.name }}
              </option>
            </select>
          </div>
        </div>
      </div>
      
      <div class="form-actions">
        <button class="btn btn-secondary" @click="$emit('close')">Cancel</button>
        <button class="btn btn-primary" @click="$emit('submit')">{{ isEditing ? 'Save' : 'Add' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch, computed } from 'vue'

interface ContentPart {
  type: 'text' | 'image_url'
  text?: string
  image_url?: { url: string }
}

interface Message {
  role: string
  content: string | ContentPart[]
  _mode?: 'text' | 'multipart'
}

interface ModelForm {
  name: string
  provider: string
  endpoint: string
  api_key: string
  model: string
}

interface CaseForm {
  name: string
  messages: Message[]
  max_tokens: number
  expected_output?: string
  eval_model?: string
  folder_id?: string
}

interface ModelOption {
  name: string
  endpoint: string
  api_key: string
  model: string
}

interface TreeNode {
  folder_id: string
  name: string
  parent_id: string | null
  children: TreeNode[]
}

interface FolderOption {
  label: string
  value: string
}

interface Props {
  visible: boolean
  type: 'model' | 'case'
  isEditing: boolean
  modelForm: ModelForm
  caseForm: CaseForm
  availableModels?: ModelOption[]
  folders?: TreeNode[]
}

const props = withDefaults(defineProps<Props>(), {
  availableModels: () => [],
  folders: () => []
})

// 规范化每条 message：补 _mode 字段，list content -> multipart
watch(
  () => props.caseForm.messages,
  (msgs) => {
    if (!msgs) return
    for (const m of msgs) {
      if (Array.isArray(m.content)) {
        m._mode = 'multipart'
      } else if (!m._mode) {
        m._mode = 'text'
      }
    }
  },
  { deep: true, immediate: true }
)

// 切换内容形态。切回文本时如有图片 part，弹确认避免误丢。
function onModeChange(msg: Message) {
  if (msg._mode === 'multipart') {
    const text = typeof msg.content === 'string' ? msg.content : ''
    msg.content = text ? [{ type: 'text', text }] : []
  } else {
    if (Array.isArray(msg.content)) {
      const hasImage = msg.content.some((p: ContentPart) => p.type === 'image_url')
      if (hasImage) {
        const ok = confirm('切换为纯文本模式将丢弃所有图片分块。是否继续？')
        if (!ok) {
          msg._mode = 'multipart'
          return
        }
      }
      const txt = msg.content
        .filter((p) => p.type === 'text')
        .map((p) => p.text || '')
        .join('')
      msg.content = txt
    }
  }
}

function addPart(msg: Message, type: 'text' | 'image_url') {
  if (!Array.isArray(msg.content)) msg.content = []
  if (type === 'text') {
    msg.content.push({ type: 'text', text: '' })
  } else {
    msg.content.push({ type: 'image_url', image_url: { url: '' } })
  }
}

function removePart(msg: Message, index: number) {
  if (Array.isArray(msg.content)) msg.content.splice(index, 1)
}

function onImagePick(part: ContentPart, ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files && input.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    const dataUrl = String(reader.result || '')
    if (!part.image_url) part.image_url = { url: '' }
    part.image_url.url = dataUrl
    // 清空 input 以便重复选择同一文件
    input.value = ''
  }
  reader.readAsDataURL(file)
}

// 扁平化文件夹为下拉选项（排除根目录下的"未分类"）
function flattenFolders(nodes: TreeNode[], prefix = ''): FolderOption[] {
  const result: FolderOption[] = []
  for (const node of nodes) {
    const label = prefix ? `${prefix} / ${node.name}` : `📁 ${node.name}`
    result.push({ label, value: node.folder_id })
    if (node.children && node.children.length > 0) {
      result.push(...flattenFolders(node.children, label))
    }
  }
  return result
}

const folderOptions = computed(() => flattenFolders(props.folders || []))

// Provider 默认端点
const providerEndpoints: Record<string, string> = {
  'openai': 'https://api.openai.com/v1/chat/completions',
  'anthropic': 'https://api.anthropic.com/v1/messages',
  'gemini': 'https://generativelanguage.googleapis.com/v1beta/models',
  'lmstudio': 'http://localhost:1234/v1/chat/completions',
  'ollama': 'http://localhost:11434/api/chat',
  'azure': 'https://YOUR_RESOURCE.openai.azure.com/openai/deployments/YOUR_DEPLOYMENT'
}

// 计算端点占位符
const endpointPlaceholder = computed(() => {
  return providerEndpoints[props.modelForm.provider] || 'https://api.example.com/v1/chat/completions'
})

// 监听 Provider 变化，自动填充端点
watch(() => props.modelForm.provider, (newProvider) => {
  if (!props.modelForm.endpoint || 
      Object.values(providerEndpoints).includes(props.modelForm.endpoint) ||
      props.isEditing) {
    props.modelForm.endpoint = providerEndpoints[newProvider] || ''
  }
})

defineEmits<{
  close: []
  submit: []
  'add-message': []
  'remove-message': [index: number]
}>()
</script>

<style lang="scss" scoped>
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
  box-sizing: border-box;
  
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
  
  &:disabled {
    background: var(--gray-100);
    cursor: not-allowed;
  }
  
  textarea.form-input {
    min-height: 80px;
    resize: vertical;
    line-height: 1.5;
  }
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
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
  
  &:hover:not(:disabled) {
    border-color: var(--primary);
    color: var(--primary);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
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

/* 多模态内容形态选择 */
.message-mode-select {
  padding: 4px 8px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  background: var(--white);
  color: var(--gray-700);
  cursor: pointer;
  margin-left: 6px;

  &:focus {
    outline: none;
    border-color: var(--primary);
  }
}

/* 多模态分块编辑器 */
.parts-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.part-item {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  padding: 8px;
}

.part-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.part-type-select {
  padding: 3px 6px;
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

.part-delete-btn {
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: var(--gray-400);
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  transition: all 0.2s;

  &:hover {
    background: var(--accent-red);
    color: white;
  }
}

.part-text {
  min-height: 50px !important;
}

.part-image {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.part-image-url {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem !important;
}

.file-pick-label {
  display: inline-block;
  cursor: pointer;
}

.file-pick-input {
  display: none;
}

.file-pick-btn {
  display: inline-block;
  padding: 5px 10px;
  background: var(--gray-100);
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--gray-700);
  transition: all 0.2s;

  &:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
}

.part-image-preview {
  max-width: 100%;
  max-height: 160px;
  border-radius: 4px;
  border: 1px solid var(--gray-200);
  object-fit: contain;
}

.parts-toolbar {
  display: flex;
  gap: 8px;
}

.part-add-btn {
  flex: 1;
  padding: 6px;
  background: transparent;
  border: 1px dashed var(--gray-300);
  border-radius: 6px;
  color: var(--gray-500);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
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

/* 参数配置区域样式 */
.params-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--gray-200);
}

.params-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-700);
  margin-bottom: 12px;
  padding-bottom: 8px;
}

.form-row {
  display: flex;
  gap: 12px;
  
  .form-group {
    flex: 1;
  }
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 12px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  font-size: 0.75rem;
  color: var(--gray-700);
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--primary);
    background: var(--white);
  }
  
  input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--primary);
  }
  
  span {
    font-weight: 500;
  }
}

/* 评估配置区域样式 */
.eval-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px dashed var(--gray-300);
}

.eval-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-600);
  margin-bottom: 12px;
  padding-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  
  &::before {
    content: '⚖';
    font-size: 0.9rem;
  }
}
</style>
