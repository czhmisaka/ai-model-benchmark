import { ref } from 'vue'

export interface DialogOptions {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  /** 输入框初始值（type='prompt' 时生效） */
  defaultValue?: string
  /** 输入框 placeholder */
  placeholder?: string
  /** 危险操作按钮标红 */
  danger?: boolean
}

export interface DialogState {
  visible: boolean
  type: 'confirm' | 'prompt'
  title: string
  message: string
  confirmText: string
  cancelText: string
  inputValue: string
  placeholder: string
  danger: boolean
  /** Promise resolver（内部使用） */
  _resolve: ((value: string | null | boolean) => void) | null
}

const state = ref<DialogState>({
  visible: false,
  type: 'confirm',
  title: '',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  inputValue: '',
  placeholder: '',
  danger: false,
  _resolve: null,
})

/**
 * 全局对话框（替代浏览器原生 alert/confirm/prompt）
 *
 * 用法：
 *   const { confirm, prompt } = useDialog()
 *   const ok = await confirm('确定删除？', { title: '删除', danger: true })
 *   const name = await prompt('请输入名称：', { title: '新建', inputValue: '默认名' })
 */
export function useDialog() {
  function confirm(message: string, options: Partial<Omit<DialogState, 'type' | '_resolve'>> = {}): Promise<boolean> {
    return new Promise((resolve) => {
      state.value = {
        visible: true,
        type: 'confirm',
        title: options.title || '确认操作',
        message,
        confirmText: options.confirmText || '确定',
        cancelText: options.cancelText || '取消',
        inputValue: '',
        placeholder: '',
        danger: options.danger || false,
        _resolve: resolve as (value: string | null | boolean) => void,
      }
    })
  }

  function prompt(message: string, options: Partial<Omit<DialogState, 'type' | '_resolve'>> = {}): Promise<string | null> {
    return new Promise((resolve) => {
      state.value = {
        visible: true,
        type: 'prompt',
        title: options.title || '请输入',
        message,
        confirmText: options.confirmText || '确定',
        cancelText: options.cancelText || '取消',
        inputValue: options.inputValue || '',
        placeholder: options.placeholder || '',
        danger: options.danger || false,
        _resolve: resolve as (value: string | null | boolean) => void,
      }
    })
  }

  function _resolveWith(value: string | null | boolean) {
    if (state.value._resolve) {
      state.value._resolve(value)
      state.value._resolve = null
    }
    state.value.visible = false
  }

  return {
    state: state,
    confirm,
    prompt,
    _resolveWith,
  }
}

// 全局单例（跨组件共享状态）
export const dialogState = state
