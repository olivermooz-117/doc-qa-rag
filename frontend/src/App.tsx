import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import {
  ArrowUp,
  Check,
  FileText,
  LibraryBig,
  LoaderCircle,
  MessageSquareText,
  Plus,
  Sparkles,
  Upload,
} from 'lucide-react'
import './App.css'

import {
  askQuestion,
  checkHealth,
  getDocuments,
  uploadDocument,
} from './api/client'
import type { ChatMessage, Document } from './types/api'

type ApiStatus = 'checking' | 'online' | 'offline'

interface Notice {
  type: 'success' | 'error'
  text: string
}

function App() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [apiStatus, setApiStatus] =
    useState<ApiStatus>('checking')
  const [uploading, setUploading] = useState(false)
  const [asking, setAsking] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)

  const fileInput = useRef<HTMLInputElement>(null)
  const messageEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true

    async function loadDocuments() {
      try {
        const items = await getDocuments()

        if (!active) {
          return
        }

        setDocuments(items)
        setApiStatus('online')
      } catch {
        if (active) {
          setApiStatus('offline')
        }
      }
    }

    void loadDocuments()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    messageEnd.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [messages])

  async function handleUpload(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0]

    if (!file) {
      return
    }

    setUploading(true)
    setNotice(null)

    try {
      const result = await uploadDocument(file)

      setApiStatus('online')

      const uploadedDocument: Document = {
        id: result.id,
        filename: result.filename,
        chunk_count: result.chunks_created,
        uploaded_at: new Date().toISOString(),
      }

      setDocuments((current) => [
        uploadedDocument,
        ...current.filter(
          (document) => document.id !== result.id,
        ),
      ])

      setNotice({
        type: 'success',
        text: `${result.filename} is ready · ${result.chunks_created} chunks`,
      })
    } catch (error) {
      setApiStatus('offline')

      setNotice({
        type: 'error',
        text:
          error instanceof Error
            ? error.message
            : 'The PDF could not be uploaded.',
      })
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  async function handleAsk(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    const text = question.trim()

    if (!text || asking || !documents.length) {
      return
    }

    const requestId = `${Date.now()}-${Math.random()}`

    setQuestion('')
    setAsking(true)

    setMessages((current) => [
      ...current,
      {
        id: `${requestId}-question`,
        role: 'user',
        text,
      },
      {
        id: requestId,
        role: 'assistant',
        pending: true,
      },
    ])

    try {
      const result = await askQuestion(text)

      setApiStatus('online')

      setMessages((current) =>
        current.map((message) =>
          message.id === requestId
            ? {
                ...message,
                pending: false,
                text: result.answer,
                sources: result.sources,
              }
            : message,
        ),
      )
    } catch (error) {
      setApiStatus('offline')

      setMessages((current) =>
        current.map((message) =>
          message.id === requestId
            ? {
                ...message,
                pending: false,
                error:
                  error instanceof Error
                    ? error.message
                    : 'The question could not be answered.',
              }
            : message,
        ),
      )
    } finally {
      setAsking(false)
    }
  }

  function handleQuestionKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  async function handleHealthCheck() {
    setApiStatus('checking')

    try {
      await checkHealth()
      setApiStatus('online')
    } catch {
      setApiStatus('offline')
    }
  }

  const chunkTotal = documents.reduce(
    (total, document) => total + document.chunk_count,
    0,
  )

  const canAsk = documents.length > 0 && !asking

  return (
    <div className="app-shell">
      <header className="topbar">
        <a
          className="brand"
          href="#top"
          aria-label="Doc QA home"
        >
          <span className="brand-mark">
            <FileText size={17} strokeWidth={2.2} />
          </span>

          <span>
            doc<span className="brand-divider">/</span>qa
          </span>
        </a>

        <button
          className={`connection-status ${apiStatus}`}
          type="button"
          onClick={() => void handleHealthCheck()}
          title="Check API connection"
        >
          <span className="status-dot" />

          {apiStatus === 'checking'
            ? 'Connecting'
            : apiStatus === 'online'
              ? 'Connected'
              : 'Offline'}
        </button>
      </header>

      <main className="workspace" id="top">
        <aside
          className="library-panel"
          aria-label="Document library"
        >
          <div className="library-heading">
            <div className="section-label">
              <LibraryBig size={15} />
              Library
            </div>

            <button
              className="icon-button add-button"
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
              aria-label="Add a PDF"
              title="Add a PDF"
            >
              {uploading ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <Plus size={19} />
              )}
            </button>

            <input
              ref={fileInput}
              className="visually-hidden"
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleUpload}
              aria-label="Choose a PDF to upload"
            />
          </div>

          <div className="library-count">
            <span>
              {documents.length}{' '}
              {documents.length === 1
                ? 'document'
                : 'documents'}
            </span>

            <span>{chunkTotal} chunks</span>
          </div>

          <div className="document-list" aria-live="polite">
            {documents.map((document, index) => (
              <article
                className="document-row"
                key={document.id}
                style={
                  {
                    '--row-index': index,
                  } as CSSProperties
                }
              >
                <span className="document-icon">
                  <FileText size={17} />
                </span>

                <span className="document-copy">
                  <span
                    className="document-name"
                    title={document.filename}
                  >
                    {document.filename}
                  </span>

                  <span className="document-meta">
                    {document.chunk_count}{' '}
                    {document.chunk_count === 1
                      ? 'chunk'
                      : 'chunks'}
                  </span>
                </span>

                <Check
                  className="document-check"
                  size={15}
                  aria-label="Indexed"
                />
              </article>
            ))}

            {documents.length === 0 && (
              <div className="library-empty">
                <span className="empty-file">
                  <FileText size={18} />
                </span>

                <p>
                  {apiStatus === 'offline'
                    ? 'Library unavailable'
                    : 'No documents yet'}
                </p>

                <span>
                  {apiStatus === 'offline'
                    ? 'Start the API to reconnect.'
                    : 'Add a PDF to begin.'}
                </span>
              </div>
            )}
          </div>

          <button
            className="upload-button"
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Upload size={16} />
            )}

            {uploading ? 'Indexing PDF…' : 'Add PDF'}
          </button>

          {notice && (
            <p className={`upload-notice ${notice.type}`} role="status">
              {notice.text}
            </p>
          )}

          <div className="library-footnote">
            <span className="footnote-rule" />
            <span>PDF documents · semantic search</span>
          </div>
        </aside>

        <section
          className="chat-panel"
          aria-label="Document question and answer"
        >
          <div className="chat-heading">
            <div>
              <div className="eyebrow">YOUR READING ROOM</div>

              <h1>
                Ask your documents
                <span className="heading-period">.</span>
              </h1>
            </div>

            <span className="mode-indicator">
              <Sparkles size={14} />
              GROUNDED
            </span>
          </div>

          <div
            className={`conversation ${
              messages.length
                ? 'has-messages'
                : 'empty-conversation'
            }`}
            aria-live="polite"
          >
            {messages.length === 0 ? (
              <div className="welcome-state">
                <div className="welcome-glyph">
                  <MessageSquareText
                    size={25}
                    strokeWidth={1.55}
                  />
                </div>

                <h2>
                  {documents.length
                    ? 'Your documents are in.'
                    : 'A clearer way through your PDFs.'}
                </h2>

                <p>
                  {documents.length
                    ? 'Ask a question and get an answer tied to the passages that support it.'
                    : 'Add a PDF, then ask about anything inside it. Answers include the passages they came from.'}
                </p>

                <div className="welcome-rule">
                  <span />
                </div>
              </div>
            ) : (
              <div className="message-thread">
                {messages.map((message) => (
                  <article
                    className={`message ${message.role}`}
                    key={message.id}
                  >
                    <div className="message-label">
                      {message.role === 'user'
                        ? 'YOU'
                        : 'DOC QA'}
                    </div>

                    <div
                      className={`message-body ${
                        message.error
                          ? 'message-error'
                          : ''
                      }`}
                    >
                      {message.pending ? (
                        <span className="thinking">
                          <LoaderCircle
                            className="spin"
                            size={17}
                          />
                          Searching your library
                        </span>
                      ) : (
                        message.error || message.text
                      )}
                    </div>

                    {message.sources &&
                      message.sources.length > 0 && (
                        <div className="source-list">
                          <div className="source-heading">
                            SOURCES{' '}
                            <span>
                              {message.sources.length}
                            </span>
                          </div>

                          {message.sources.map(
                            (source, index) => (
                              <details
                                className="source-item"
                                key={`${source.document}-${source.chunk}-${index}`}
                              >
                                <summary>
                                  <FileText size={15} />

                                  <span className="source-name">
                                    {source.document}
                                  </span>

                                  <span className="source-index">
                                    CHUNK {source.chunk + 1}
                                  </span>
                                </summary>

                                <p>{source.content}</p>
                              </details>
                            ),
                          )}
                        </div>
                      )}
                  </article>
                ))}

                <div ref={messageEnd} />
              </div>
            )}
          </div>

          <form className="composer" onSubmit={handleAsk}>
            <label
              className="visually-hidden"
              htmlFor="question"
            >
              Ask a question about your PDFs
            </label>

            <textarea
              id="question"
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              onKeyDown={handleQuestionKeyDown}
              placeholder={
                documents.length
                  ? 'Ask something specific…'
                  : 'Add a PDF before asking a question'
              }
              rows={1}
              disabled={!canAsk}
            />

            <div className="composer-bottom">
              <span className="composer-hint">
                {asking
                  ? 'Finding relevant passages'
                  : 'Answers use your uploaded sources only'}
              </span>

              <button
                className="send-button"
                type="submit"
                disabled={
                  !question.trim() || !canAsk
                }
                aria-label="Send question"
                title="Send question"
              >
                {asking ? (
                  <LoaderCircle
                    className="spin"
                    size={17}
                  />
                ) : (
                  <ArrowUp size={18} />
                )}
              </button>
            </div>
          </form>

          <p className="privacy-note">
            Your questions are answered from your library, not the
            open web.
          </p>
        </section>
      </main>
    </div>
  )
}

export default App