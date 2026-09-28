import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App.tsx'
import {
  askQuestion,
  checkHealth,
  getDocuments,
  uploadDocument,
} from './api/client'

vi.mock('./api/client', () => ({
  askQuestion: vi.fn(),
  checkHealth: vi.fn(),
  getDocuments: vi.fn(),
  uploadDocument: vi.fn(),
}))

describe('document QA workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getDocuments).mockResolvedValue([])
    vi.mocked(checkHealth).mockResolvedValue()
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    })
  })

  afterEach(() => {
    cleanup()
  })

  it('renders the documents returned by the API', async () => {
    vi.mocked(getDocuments).mockResolvedValue([
      {
        id: 1,
        filename: 'handbook.pdf',
        uploaded_at: null,
        chunk_count: 2,
      },
    ])

    render(<App />)

    expect(await screen.findByText('handbook.pdf')).toBeTruthy()
    expect(screen.getAllByText('2 chunks')).toHaveLength(2)
  })

  it('uploads a PDF, asks a question, and renders its source', async () => {
    const user = userEvent.setup()
    vi.mocked(uploadDocument).mockResolvedValue({
      id: 2,
      filename: 'manual.pdf',
      uploaded_at: null,
      chunk_count: 2,
      chunks_created: 2,
    })
    vi.mocked(askQuestion).mockResolvedValue({
      answer: 'Restart the service after uploading.',
      sources: [
        {
          id: 8,
          document_id: 2,
          document: 'manual.pdf',
          page: 4,
          chunk: 0,
          content: 'Restart the service after uploading.',
          distance: 0.1,
          citation: 'manual.pdf, page 4',
        },
      ],
    })

    render(<App />)

    await user.upload(
      screen.getByLabelText('Choose a PDF to upload'),
      new File(['pdf content'], 'manual.pdf', { type: 'application/pdf' }),
    )

    expect(
      await screen.findByText('manual.pdf is ready · 2 chunks'),
    ).toBeTruthy()

    await user.type(
      screen.getByRole('textbox', {
        name: 'Ask a question about your PDFs',
      }),
      'How do I restart it?',
    )
    await user.click(screen.getByRole('button', { name: 'Send question' }))

    expect(askQuestion).toHaveBeenCalledWith('How do I restart it?')
    expect(
      await screen.findByText('Restart the service after uploading.', {
        selector: '.message.assistant .message-body',
      }),
    ).toBeTruthy()

    const sourceSummary = screen.getByText('manual.pdf', {
      selector: '.source-name',
    })
    await user.click(sourceSummary)
    const sourceDetails = sourceSummary.closest('details')
    expect(sourceDetails).not.toBeNull()
    expect(
      within(sourceDetails as HTMLDetailsElement).getByText(
        'Restart the service after uploading.',
      ),
    ).toBeTruthy()
  })

  it('keeps question entry disabled until a document is available', async () => {
    render(<App />)

    const question = await screen.findByRole('textbox', {
      name: 'Ask a question about your PDFs',
    })
    expect((question as HTMLTextAreaElement).disabled).toBe(true)
    expect(
      (screen.getByRole('button', { name: 'Send question' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })
})