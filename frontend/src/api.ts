import type {
  AccuracyRow,
  ChatMessage,
  Conversation,
  DocumentInfo,
  Group,
  Org,
  Task,
  TeamLoad,
  User,
} from './types'

const USER_KEY = 'ga:user'

export function getUserId(): string | null {
  try {
    return localStorage.getItem(USER_KEY)
  } catch {
    return null
  }
}

export function setUserId(id: string) {
  try {
    localStorage.setItem(USER_KEY, id)
  } catch {
    /* depolama kapalıysa oturum boyunca varsayılan kullanıcıyla devam edilir */
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const uid = getUserId()
  if (uid) headers.set('X-User-Id', uid)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const res = await fetch(path, { ...init, headers })
  if (!res.ok) {
    let msg = `İstek başarısız (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') msg = body.detail
    } catch {
      /* gövde JSON değil */
    }
    throw new ApiError(res.status, msg)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body ?? {}) })

export const api = {
  org: () => request<Org>('/api/org'),
  me: () => request<User>('/api/me'),
  users: () => request<User[]>('/api/users'),
  groups: () => request<Group[]>('/api/groups'),
  myTasks: () => request<Task[]>('/api/tasks/mine'),

  conversations: () => request<Conversation[]>('/api/conversations'),
  startConversation: (text: string) =>
    post<{ conversation: Conversation; messages: ChatMessage[] }>('/api/conversations', { text }),
  messages: (id: number) =>
    request<{ conversation: Conversation; messages: ChatMessage[] }>(`/api/conversations/${id}/messages`),
  send: (id: number, text: string) => post<{ messages: ChatMessage[] }>(`/api/conversations/${id}/messages`, { text }),

  uploadDocument: (form: FormData) => post<DocumentInfo>('/api/documents', form),
  document: (id: number) => request<DocumentInfo>(`/api/documents/${id}`),
  extract: (id: number) => post<Task[]>(`/api/documents/${id}/extract`),
  documentTasks: (id: number) => request<Task[]>(`/api/documents/${id}/tasks`),
  exportDocument: (id: number) => post<{ exported: { id: number; key: string }[] }>(`/api/documents/${id}/export`),
  decide: (taskId: number, action: 'pick' | 'accept' | 'reject' | 'undo', assignee_id?: string) =>
    post<Task>(`/api/tasks/${taskId}/decision`, { action, assignee_id }),

  teamMembers: () => request<User[]>('/api/team/members'),
  teamLoad: () => request<TeamLoad>('/api/team/load'),
  accuracy: () => request<AccuracyRow[]>('/api/stats/accuracy'),
  corrections: () => request<{ label: string; count: number }[]>('/api/stats/corrections'),
}
