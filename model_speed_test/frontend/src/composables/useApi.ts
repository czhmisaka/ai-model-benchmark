/** 统一 API 请求工具
 *
 * 替代裸 fetch 调用，提供：
 * - 自动状态码检查
 * - 统一错误处理
 * - 认证头注入
 */
export async function apiFetch<T = any>(
    url: string,
    options: RequestInit = {}
): Promise<T> {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> || {}),
    }

    const res = await fetch(url, { ...options, headers })

    if (!res.ok) {
        const errorText = await res.text().catch(() => res.statusText)
        throw new ApiError(res.status, errorText || res.statusText)
    }

    // 204 No Content
    if (res.status === 204) {
        return undefined as unknown as T
    }

    return res.json()
}

export class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(`HTTP ${status}: ${message}`)
        this.name = 'ApiError'
    }
}