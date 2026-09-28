export interface Document {
  id: number
  filename: string
  uploaded_at: string | null
  chunk_count: number
}

export interface UploadResponse extends Document {
  chunks_created: number
}

export interface Source {
  id: number
  document_id: number
  document: string
  page: number | null
  chunk: number
  content: string
  distance: number
  citation: string
}

export interface AskResponse {
  answer: string
  sources: Source[]
}

export interface ApiError {
  error?: string
  message?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text?: string
  pending?: boolean
  error?: string
  sources?: Source[]
}