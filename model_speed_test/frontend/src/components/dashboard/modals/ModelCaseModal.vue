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
        <div class="form-group">
          <label class="form-label">Endpoint</label>
          <input 
            type="text" 
            class="form-input" 
            v-model="modelForm.endpoint" 
            placeholder="https://api.example.com/v1/chat/completions" 
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
                <button class="message-delete-btn" @click="$emit('remove-message', index)" title="删除">×</button>
              </div>
              <textarea 
                class="form-input message-content" 
                v-model="msg.content" 
                placeholder="输入消息内容..."
              ></textarea>
            </div>
            <button class="add-message-btn" @click="$emit('add-message')">+ 添加消息</button>
          </div>
        </div>
        
        <div class="form-group">
          <label class="form-label">Max Tokens</label>
          <input type="number" class="form-input" v-model="caseForm.max_tokens" value="500" />
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
import { reactive, watch } from 'vue'

interface Message {
  role: string
  content: string
}

interface ModelForm {
  name: string
  endpoint: string
  api_key: string
  model: string
}

interface CaseForm {
  name: string
  messages: Message[]
  max_tokens: number
}

interface Props {
  visible: boolean
  type: 'model' | 'case'
  isEditing: boolean
  modelForm: ModelForm
  caseForm: CaseForm
}

const props = defineProps<Props>()

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
</style>
