import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  askQuestion,
  getDocuments,
  uploadDocument,
} from './client'

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function stubFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('API client', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads documents from the API', async () => {
    const documents = [
      {
        id: 1,
        filename: 'handbook.pdf',
        uploaded_at: null,
        chunk_count: 2,
      },
    ]
    const fetchMock = stubFetch(jsonResponse({ documents }))

    await expect(getDocuments()).resolves.toEqual(documents)
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/documents$/)
  })

  it('uploads a PDF as multipart form data', async () => {
    const file = new File(['pdf content'], 'handbook.pdf', {
      type: 'application/pdf',
    })
    const result = {
      id: 2,
      filename: 'handbook.pdf',
      uploaded_at: null,
      chunk_count: 3,
      chunks_created: 3,
    }
    const fetchMock = stubFetch(jsonResponse(result))

    await expect(uploadDocument(file)).resolves.toEqual(result)

    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/upload$/)
    expect(options?.method).toBe('POST')
    const body = options?.body
    if (!(body instanceof FormData)) {
      throw new Error('Expected the PDF upload body to be FormData')
    }
    expect(body.get('file')).toBe(file)
  })

  it('sends questions as JSON and surfaces API error messages', async () => {
    const fetchMock = stubFetch(jsonResponse({ answer: 'Found it', sources: [] }))

    await expect(askQuestion('Where is it?')).resolves.toEqual({
      answer: 'Found it',
      sources: [],
    })

    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/ask$/)
    expect(options?.method).toBe('POST')
    expect(options?.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(options?.body).toBe(JSON.stringify({ question: 'Where is it?' }))

    stubFetch(jsonResponse({ message: 'Question limit reached' }, 400))
    await expect(askQuestion('Too long')).rejects.toThrow(
      'Question limit reached',
    )
  })
})