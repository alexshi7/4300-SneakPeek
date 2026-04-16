import { useEffect, useRef, useState } from 'react'
import SearchIcon from './assets/mag.png'

interface Message {
  text: string
  isUser: boolean
}

interface ChatProps {
  onSearchTerm: (term: string) => void
}

function Chat({ onSearchTerm }: ChatProps): JSX.Element {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const setAssistantError = (text: string): void => {
    setMessages(prev => {
      const lastMessage = prev[prev.length - 1]
      if (lastMessage && !lastMessage.isUser && lastMessage.text === '') {
        return [...prev.slice(0, -1), { text, isUser: false }]
      }

      return [...prev, { text, isUser: false }]
    })
  }

  const sendMessage = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault()

    const text = input.trim()
    if (!text || loading) return

    setMessages(prev => [...prev, { text, isUser: true }])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        setAssistantError(`Error: ${data?.error || response.status}`)
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      let assistantText = ''
      setMessages(prev => [...prev, { text: '', isUser: false }])

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue

          try {
            const data = JSON.parse(line.slice(6))

            if (data.search_term !== undefined) {
              onSearchTerm(data.search_term)
            }

            if (data.error) {
              setAssistantError(`Error: ${data.error}`)
              return
            }

            if (data.content !== undefined) {
              assistantText += data.content
              setMessages(prev => [...prev.slice(0, -1), { text: assistantText, isUser: false }])
            }
          } catch {
            continue
          }
        }
      }
    } catch {
      setAssistantError('Something went wrong. Check the console.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-shell">
      <div id="messages" aria-live="polite">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <p>Ask for more cushioning, better traction, a different player profile, or a cleaner lifestyle option.</p>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`message ${message.isUser ? 'user' : 'assistant'}`}>
            <p>{message.text}</p>
          </div>
        ))}

        {loading && (
          <div className="loading-indicator visible">
            <span className="loading-dot" />
            <span className="loading-dot" />
            <span className="loading-dot" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="chat-bar">
        <form className="input-row" onSubmit={sendMessage}>
          <img src={SearchIcon} alt="" aria-hidden="true" />
          <input
            type="text"
            placeholder="Ask the AI to refine the shortlist"
            value={input}
            onChange={event => setInput(event.target.value)}
            disabled={loading}
            autoComplete="off"
          />
          <button type="submit" disabled={loading || input.trim().length === 0}>
            Send
          </button>
        </form>
      </div>
    </div>
  )
}

export default Chat
