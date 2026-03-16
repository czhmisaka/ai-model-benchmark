import { ref } from 'vue'

export interface Model {
  name: string
  endpoint: string
  api_key: string
  model: string
  enabled?: boolean
}

export interface TestCase {
  id: string
  name: string
  messages: { role: string; content: string }[]
  max_tokens: number
  temperature?: number
  stream?: boolean
}

export interface Config {
  models: Model[]
  test_cases: TestCase[]
}

export function useConfig() {
  const config = ref<Config | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  async function loadConfig() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/config')
      config.value = await res.json()
    } catch (e) {
      error.value = 'Failed to load config'
      console.error('Failed to load config:', e)
    } finally {
      loading.value = false
    }
  }
  
  // Model 操作
  async function addModel(data: Omit<Model, 'enabled'>) {
    if (!data.name || !data.endpoint || !data.model) {
      throw new Error('Please fill all fields')
    }
    const res = await fetch('/config/models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...data, enabled: true })
    })
    const result = await res.json()
    if (result.error) throw new Error(result.error)
    config.value!.models = result.models
    return result
  }
  
  async function updateModel(name: string, data: Partial<Model>) {
    const res = await fetch(`/config/models/${encodeURIComponent(name)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...data, enabled: true })
    })
    const result = await res.json()
    if (result.error) throw new Error(result.error)
    config.value!.models = result.models
    return result
  }
  
  async function deleteModel(name: string) {
    const res = await fetch(`/config/models/${encodeURIComponent(name)}`, { method: 'DELETE' })
    const result = await res.json()
    config.value!.models = result.models
    return result
  }
  
  // Test Case 操作
  async function addTestCase(data: Omit<TestCase, 'id'>) {
    if (!data.name || !data.messages?.some((m: any) => m.content?.trim())) {
      throw new Error('Please fill all fields')
    }
    const res = await fetch('/config/test-cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...data, stream: true, temperature: 0.7 })
    })
    const result = await res.json()
    if (result.error) throw new Error(result.error)
    config.value!.test_cases = result.test_cases
    return result
  }
  
  async function updateTestCase(id: string, data: Partial<TestCase>) {
    const res = await fetch(`/config/test-cases/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...data, stream: true, temperature: 0.7 })
    })
    const result = await res.json()
    if (result.error) throw new Error(result.error)
    config.value!.test_cases = result.test_cases
    return result
  }
  
  async function deleteTestCase(id: string) {
    const res = await fetch(`/config/test-cases/${id}`, { method: 'DELETE' })
    const result = await res.json()
    config.value!.test_cases = result.test_cases
    return result
  }
  
  return {
    config,
    loading,
    error,
    loadConfig,
    addModel,
    updateModel,
    deleteModel,
    addTestCase,
    updateTestCase,
    deleteTestCase
  }
}