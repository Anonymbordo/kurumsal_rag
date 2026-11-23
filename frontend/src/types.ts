export interface Org {
  name: string
  accent: string
  primary: string
  logo_url: string | null
  model_label: string
  llm_provider: string
  show_workstreams: boolean
}

export interface UserBrief {
  id: string
  name: string
  initials: string
  role: string
}

export interface User extends UserBrief {
  team_id: string
  team_name: string
  is_lead: boolean
  skills: string[]
  load: number
}

export interface Person extends UserBrief {
  load: number
}

export interface Task {
  id: number
  key: string | null
  order_no: number
  document_id: number | null
  title: string
  detail: string
  tags: string[]
  est_days: number
  due_date: string | null
  source: { ref: string; quote: string; start: number; end: number }
  suggested: Person | null
  alternative: Person | null
  assignee: Person | null
  confidence: 1 | 2 | 3
  forcing: boolean
  reasons: string[]
  detect_score: number | null
  workstream: string | null
  is_outlier: boolean
  kind: 'task' | 'announcement'
  unknown_mentions: string[]
  status: 'suggested' | 'accepted' | 'rejected' | 'exported' | 'done' | 'candidate' | 'dismissed' | 'announcement' | 'announced'
  reject_reason: 'not_task' | 'not_now' | null
  status_label: string
  lead_picked_first: boolean
}

export interface DocumentInfo {
  id: number
  title: string
  doc_type: string
  sprint: string
  uploaded_by: UserBrief | null
  related_task_key: string | null
  created_at: string
  char_count: number
  text?: string
}

export interface Group {
  id: string
  name: string
  short: string
  color: string
  member_count: number
}

export interface Conversation {
  id: number
  title: string
  updated_at: string
}

export interface TaskCardItem {
  id: number
  key: string
  title: string
  tag: string
  tone: 'new' | 'active' | 'done'
  assigned_by: string
  due: string
  source: string
  document_id: number | null
  note: string
}

export interface DocCardItem {
  id: number
  title: string
  shared_by: string
  at: string
  related: string | null
}

export type Block =
  | { type: 'tasks'; items: TaskCardItem[] }
  | { type: 'documents'; items: DocCardItem[] }

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
  blocks: Block[]
  sources: string[]
  created_at: string
}

export interface TeamLoad {
  limit: number
  members: { id: string; name: string; role: string; before: number; after: number; new_tasks: number }[]
}

export interface AccuracyRow {
  level: number
  label: string
  total: number
  unchanged_pct: number | null
}

export interface LabelPreview {
  title: string
  text: string
  sentences: string[]
  suggestions: number[] | null
  anonymized: Record<string, number>
}

export interface DocPerson {
  name: string
  role: string
  user_id: string | null
  skills: string[]
  is_lead: boolean
}

export interface SkillOption {
  id: string
  label: string
}
