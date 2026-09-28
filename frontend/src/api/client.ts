import type {
  ApiError,
  AskResponse,
  Document,
  UploadResponse,
} from '../types/api'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'
).replace(/\/$/, '')

async function readJson<T>(response: Response): Promise<T> {
  const payload = (await response.json().catch(() => ({}))) as
    | T
    | ApiError

  if (!response.ok) {
    const errorPayload = payload as ApiError

    throw new Error(
      errorPayload.message ||
        errorPayload.error ||
        `Request failed (${response.status})`,
    )
  }

  return payload as T
}

export async function getDocuments(): Promise<Document[]> {
  const response = await fetch(`${API_BASE_URL}/api/documents`)
  const payload = await readJson<{ documents: Document[] }>(response)

  return payload.documents
}

export async function uploadDocument(
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/api/upload`, {
    method: 'POST',
    body: formData,
  })

  return readJson<UploadResponse>(response)
}

export async function askQuestion(
  question: string,
): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
  })

  return readJson<AskResponse>(response)
}

export async function checkHealth(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/health`)
  await readJson<{ status: string }>(response)
}