<template>
  <div class="settings">
    <h1 class="page-title">系统设置</h1>
    
    <div class="settings-section">
      <h2>API 配置</h2>
      <div class="form-group">
        <label>API Key</label>
        <input type="password" v-model="settings.apiKey" placeholder="输入 API Key" />
      </div>
      <div class="form-group">
        <label>API Endpoint</label>
        <input type="text" v-model="settings.endpoint" placeholder="https://api.minimax.chat" />
      </div>
    </div>
    
    <div class="settings-section">
      <h2>模型配置</h2>
      <div class="model-list">
        <div v-for="(model, i) in settings.models" :key="i" class="model-item">
          <input v-model="model.name" placeholder="模型名称" />
          <input v-model="model.model" placeholder="模型ID" />
          <button @click="removeModel(i)" class="btn-remove">删除</button>
        </div>
        <button @click="addModel" class="btn-add">+ 添加模型</button>
      </div>
    </div>
    
    <div class="settings-section">
      <h2>测试配置</h2>
      <div class="form-group">
        <label>默认并发数</label>
        <input type="number" v-model="settings.defaultConcurrency" min="1" max="200" />
      </div>
      <div class="form-group">
        <label>默认轮次</label>
        <input type="number" v-model="settings.defaultRounds" min="1" max="100" />
      </div>
      <div class="form-group">
        <label>请求超时 (秒)</label>
        <input type="number" v-model="settings.timeout" min="10" max="300" />
      </div>
    </div>
    
    <div class="settings-section">
      <h2>通知配置</h2>
      <div class="form-group">
        <label>
          <input type="checkbox" v-model="settings.notifyOnComplete" />
          测试完成后发送通知
        </label>
      </div>
      <div class="form-group">
        <label>Webhook URL</label>
        <input type="text" v-model="settings.webhookUrl" placeholder="钉钉/飞书 Webhook" />
      </div>
    </div>
    
    <div class="settings-actions">
      <button @click="saveSettings" class="btn-primary">保存设置</button>
      <button @click="resetSettings" class="btn-secondary">重置</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'

const settings = reactive({
  apiKey: '',
  endpoint: 'https://api.minimax.chat',
  models: [
    { name: 'MiniMax Text 01', model: 'MiniMax-Text-01' },
    { name: 'MiniMax M2.5', model: 'MiniMax-M2.5-HighSpeed' }
  ],
  defaultConcurrency: 10,
  defaultRounds: 5,
  timeout: 120,
  notifyOnComplete: false,
  webhookUrl: ''
})

function addModel() {
  settings.models.push({ name: '', model: '' })
}

function removeModel(index: number) {
  settings.models.splice(index, 1)
}

function saveSettings() {
  localStorage.setItem('app_settings', JSON.stringify(settings))
  alert('设置已保存')
}

function resetSettings() {
  if (confirm('确定要重置所有设置吗？')) {
    settings.apiKey = ''
    settings.endpoint = 'https://api.minimax.chat'
    settings.models = [
      { name: 'MiniMax Text 01', model: 'MiniMax-Text-01' }
    ]
    settings.defaultConcurrency = 10
    settings.defaultRounds = 5
    settings.timeout = 120
    settings.notifyOnComplete = false
    settings.webhookUrl = ''
  }
}
</script>

<style lang="scss" scoped>
.settings {
  .page-title {
    margin-bottom: 24px;
    font-size: 24px;
    font-weight: 600;
  }
}

.settings-section {
  background: var(--white);
  padding: 24px;
  border-radius: 8px;
  margin-bottom: 16px;
  
  h2 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--gray-200);
  }
}

.form-group {
  margin-bottom: 16px;
  
  label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    font-weight: 500;
    
    input[type="checkbox"] {
      width: auto;
    }
  }
  
  input {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--gray-300);
    border-radius: 6px;
    
    &:focus {
      outline: none;
      border-color: var(--primary);
    }
  }
}

.model-list {
  .model-item {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
    
    input {
      flex: 1;
      padding: 10px 12px;
      border: 1px solid var(--gray-300);
      border-radius: 6px;
    }
  }
  
  .btn-add {
    padding: 10px 16px;
    background: var(--primary-dim);
    color: var(--primary);
    border: none;
    border-radius: 6px;
    cursor: pointer;
    
    &:hover {
      background: rgba(255, 69, 0, 0.25);
    }
  }
  
  .btn-remove {
    padding: 10px 16px;
    background: var(--error);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
}

.settings-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.btn-primary, .btn-secondary {
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.btn-primary {
  background: var(--primary);
  color: white;
  
  &:hover {
    background: #ff5722;
  }
}

.btn-secondary {
  background: var(--gray-200);
  
  &:hover {
    background: var(--gray-300);
  }
}
</style>