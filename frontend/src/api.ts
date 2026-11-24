import type {
  AccuracyRow,
  ChatMessage,
  Conversation,
  DocListItem,
  MeetingDetail,
  MeetingInfo,
  TaskSource,
  DocPerson,
  DocumentInfo,
  Group,
  LabelPreview,
  Org,
  SkillOption,
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

/** Akışlı sohbet cevabı: NDJSON satırlarını okur, her parçada onDelta çağrılır. */
async function streamMessage(
  id: number,
  text: string,
  onDelta: (piece: string) => void,
): Promise<ChatMessage[]> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const uid = getUserId()
  if (uid) headers.set('X-User-Id', uid)
  const res = await fetch(`/api/conversations/${id}/messages/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ text }),
  })
  if (!res.ok || !res.body) throw new ApiError(res.status, `İstek başarısız (${res.status})`)
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let done: ChatMessage[] | null = null
  for (;;) {
    const { value, done: end } = await reader.read()
    if (value) buf += dec.decode(value, { stream: true })
    let nl: number
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim()
      buf = buf.slice(nl + 1)
      if (!line) continue
      const ev = JSON.parse(line) as { type: 'delta'; text: string } | { type: 'done'; messages: ChatMessage[] }
      if (ev.type === 'delta') onDelta(ev.text)
      else done = ev.messages
    }
    if (end) break
  }
  if (!done) throw new ApiError(500, 'Cevap yarıda kesildi')
  return done
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const uid = getUserId()
  if (uid) headers.set('X-User-Id', uid)
  if (typeof init.body === 'string') headers.set('Content-Type', 'application/json')
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
  startConversation: (text: string, defer = false) =>
    post<{ conversation: Conversation; messages: ChatMessage[] }>('/api/conversations', { text, defer }),
  streamMessage,
  messages: (id: number) =>
    request<{ conversation: Conversation; messages: ChatMessage[] }>(`/api/conversations/${id}/messages`),
  send: (id: number, text: string) => post<{ messages: ChatMessage[] }>(`/api/conversations/${id}/messages`, { text }),

  uploadDocument: (form: FormData) => post<DocumentInfo>('/api/documents', form),
  documents: () => request<DocListItem[]>('/api/documents'),
  deleteDocument: (id: number) =>
    request<{ deleted: number; kept_tasks: number; removed_tasks: number }>(`/api/documents/${id}`, { method: 'DELETE' }),
  document: (id: number) => request<DocumentInfo>(`/api/documents/${id}`),
  extract: (id: number) => post<Task[]>(`/api/documents/${id}/extract`),
  documentTasks: (id: number) => request<Task[]>(`/api/documents/${id}/tasks`),
  exportDocument: (id: number) =>
    post<{ exported: { id: number; key: string }[]; announced: number }>(`/api/documents/${id}/export`),
  documentPeople: (id: number) => request<DocPerson[]>(`/api/documents/${id}/people`),
  importPeople: (id: number, names: string[]) => post<{ added: string[] }>(`/api/documents/${id}/people/import`, { names }),
  decide: (
    taskId: number,
    action: 'pick' | 'accept' | 'reject' | 'undo' | 'promote' | 'dismiss' | 'share',
    assignee_id?: string,
    reason?: 'not_task' | 'not_now',
  ) => post<Task>(`/api/tasks/${taskId}/decision`, { action, assignee_id, reason }),

  labelPreview: (form: FormData) => post<LabelPreview>('/api/labeling/preview', form),
  labelSave: (body: { title: string; split: 'train' | 'test'; text: string; sentences: string[]; labels: string[] }) =>
    post<{ saved: string; tasks: number; sentences: number }>('/api/labeling/save', body),
  labelStats: () => request<{ train_sentences: number; test_documents: number }>('/api/labeling/stats'),

  teamMembers: () => request<User[]>('/api/team/members'),

  taskSource: (id: number) => request<TaskSource>(`/api/tasks/${id}/source`),
  meetings: () => request<MeetingInfo[]>('/api/meetings'),
  meeting: (id: number) => request<MeetingDetail>(`/api/meetings/${id}`),
  createMeeting: (title: string, participants: string[]) => post<MeetingDetail>('/api/meetings', { title, participants }),
  startRecording: (id: number) => post<{ id: number; offset_s: number }>(`/api/meetings/${id}/recordings`),
  uploadChunk: (rid: number, seq: number, blob: Blob) =>
    request<{ chunks: number }>(`/api/meetings/recordings/${rid}/chunks?seq=${seq}`, {
      method: 'POST',
      body: blob,
      headers: { 'Content-Type': 'application/octet-stream' },
    }),
  uploadMeetingAudio: (id: number, form: FormData) => post<{ id: number; bytes: number }>(`/api/meetings/${id}/audio`, form),
  endMeeting: (id: number) => post<MeetingDetail>(`/api/meetings/${id}/end`),
  retryMeeting: (id: number) => post<MeetingDetail>(`/api/meetings/${id}/retry`),
  skillOptions: () => request<SkillOption[]>('/api/team/skills'),
  addMember: (body: { name: string; role: string; skills?: string[]; base_load_days?: number }) =>
    post<User>('/api/team/members', body),
  updateMember: (id: string, body: { role?: string; skills?: string[]; base_load_days?: number }) =>
    request<User>(`/api/team/members/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  removeMember: (id: string) => request<{ removed: string }>(`/api/team/members/${id}`, { method: 'DELETE' }),
  teamLoad: () => request<TeamLoad>('/api/team/load'),
  accuracy: () => request<AccuracyRow[]>('/api/stats/accuracy'),
  corrections: () => request<{ label: string; count: number }[]>('/api/stats/corrections'),
}
