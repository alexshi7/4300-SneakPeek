import {
  startTransition,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
} from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import Chat from './Chat'
import { SearchResponse, Sneaker } from './types'

const CATEGORY_OPTIONS = ['basketball', 'running', 'lifestyle']
const VERSION_LABEL = 'Version 4.1'
const DEFAULT_USE_CASE =
  "I'm a tall point guard who wants lightweight shoes with good traction, a star-player connection, and strong style."
const SEARCH_ERROR_MESSAGE = 'Unable to load sneaker matches right now. Try the search again in a moment.'

interface SpecEntry {
  label: string
  value: string
}

const CARD_POSITIONS = ['10% 20%', '62% 24%', '82% 68%', '22% 72%', '50% 58%', '72% 14%']

const capitalizeLabel = (value: string): string => value.charAt(0).toUpperCase() + value.slice(1)

const truncateText = (value: string, maxLength: number): string => {
  if (value.length <= maxLength) return value
  return `${value.slice(0, maxLength).trimEnd()}...`
}

const appendUnit = (value: string | number, unit: string): string => {
  const text = String(value).trim()
  return text.toLowerCase().includes(unit.toLowerCase()) ? text : `${text} ${unit}`
}

const formatPrice = (value: string | number): string => {
  const text = String(value).trim()
  return text.startsWith('$') ? text : `$${text}`
}

const buildSpecEntries = (sneaker: Sneaker): SpecEntry[] => {
  const entries: SpecEntry[] = []
  const { specs } = sneaker

  if (specs.price_usd !== undefined) {
    entries.push({ label: 'Price', value: formatPrice(specs.price_usd) })
  }
  if (specs.weight_oz !== undefined) {
    entries.push({ label: 'Weight', value: appendUnit(specs.weight_oz, 'oz') })
  }
  if (specs.heel_stack_mm !== undefined) {
    entries.push({ label: 'Heel stack', value: appendUnit(specs.heel_stack_mm, 'mm') })
  }
  if (specs.forefoot_stack_mm !== undefined) {
    entries.push({ label: 'Forefoot stack', value: appendUnit(specs.forefoot_stack_mm, 'mm') })
  }
  if (specs.traction_score !== undefined) {
    entries.push({ label: 'Traction', value: String(specs.traction_score) })
  }
  if (specs.breathability_score !== undefined) {
    entries.push({ label: 'Breathability', value: String(specs.breathability_score) })
  }
  if (specs.top_style) {
    entries.push({ label: 'Style', value: specs.top_style })
  }
  if (specs.ankle_support !== undefined) {
    entries.push({ label: 'Ankle support', value: specs.ankle_support ? 'Yes' : 'No' })
  }

  return entries
}

const getReasonTone = (reason: string): string => {
  if (reason.includes('Penalty')) return 'penalty'
  if (reason.includes('SVD')) return 'svd'
  if (reason.includes('Name')) return 'name'
  return 'default'
}

function ShoeVisual({
  imageUrl,
  shoeName,
  visualStyle,
  featured,
}: {
  imageUrl?: string
  shoeName: string
  visualStyle: CSSProperties
  featured: boolean
}): JSX.Element {
  const [hasImageError, setHasImageError] = useState(false)

  if (!imageUrl || hasImageError) {
    return (
      <div
        className={`result-card-visual ${featured ? 'featured-visual' : ''}`}
        style={visualStyle}
        aria-hidden="true"
      />
    )
  }

  return (
    <img
      className={`result-card-image ${featured ? 'featured-image' : ''}`}
      src={imageUrl}
      alt={shoeName}
      loading="lazy"
      onError={() => {
        setHasImageError(true)
      }}
    />
  )
}

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [catalogSize, setCatalogSize] = useState<number>(0)
  const [category, setCategory] = useState<string>('basketball')
  const [useCase, setUseCase] = useState<string>(DEFAULT_USE_CASE)
  const [sneakers, setSneakers] = useState<Sneaker[]>([])
  const [requestedAttributes, setRequestedAttributes] = useState<string[]>([])
  const [isSearching, setIsSearching] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState<boolean>(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    fetch('/api/config')
      .then(async response => {
        if (!response.ok) {
          throw new Error('Config request failed')
        }

        return response.json()
      })
      .then(data => {
        setUseLlm(Boolean(data.use_llm))
        setCatalogSize(data.catalog_size || 0)
      })
      .catch(() => {
        setUseLlm(false)
        setErrorMessage(SEARCH_ERROR_MESSAGE)
      })
  }, [])

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    textarea.style.height = '0px'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`
  }, [useCase])

  const runSearch = async (
    nextQuery: string = category,
    nextCategory: string = category,
    nextUseCase: string = useCase
  ): Promise<void> => {
    setIsSearching(true)
    setErrorMessage(null)

    try {
      const params = new URLSearchParams({
        query: nextQuery,
        category: nextCategory,
        use_case: nextUseCase,
      })

      const response = await fetch(`/api/sneakers?${params.toString()}`)
      if (!response.ok) {
        throw new Error('Search request failed')
      }

      const data: SearchResponse = await response.json()
      startTransition(() => {
        setSneakers(data.results)
        setRequestedAttributes(data.applied_filters.requested_attributes)
      })
    } catch {
      startTransition(() => {
        setSneakers([])
        setRequestedAttributes([])
      })
      setErrorMessage(SEARCH_ERROR_MESSAGE)
    } finally {
      setIsSearching(false)
    }
  }

  useEffect(() => {
    if (useLlm !== null) {
      void runSearch()
    }
  }, [useLlm])

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault()
    void runSearch(category, category, useCase)
  }

  const handleCategorySelect = (nextCategory: string): void => {
    setCategory(nextCategory)
    void runSearch(nextCategory, nextCategory, useCase)
  }

  const topPick = sneakers[0]
  const shortUseCase = truncateText(useCase.trim(), 108)
  const heroNote = errorMessage
    ? errorMessage
    : requestedAttributes.length > 0
      ? `Priority: ${requestedAttributes.join(', ')}.`
      : 'Search by feel, traction, cushioning, support, or style.'
  const resultsNote = topPick
    ? `Showing ${sneakers.length} ${category} matches for "${shortUseCase}". ${requestedAttributes.length > 0 ? `Prioritizing ${requestedAttributes.join(', ')}.` : ''}`
    : 'Pick a category and run a search to build the shortlist.'

  if (useLlm === null) {
    return (
      <div className="app-loading">
        <div className="app-loading-inner">
          <p className="loading-brand">SneakPeek</p>
          <p className="loading-copy">Loading review-backed sneaker intelligence...</p>
          <div className="loading-dash" aria-hidden="true" />
        </div>
      </div>
    )
  }

  return (
    <div className={`app-shell ${useLlm ? 'llm-mode' : ''}`}>
      <div className="page-glow page-glow-left" aria-hidden="true" />
      <div className="page-glow page-glow-right" aria-hidden="true" />

      <header className="hero-shell">
        <div className="hero-media" aria-hidden="true" />

        <div className="hero-content">
          <div className="hero-meta">
            <span>{VERSION_LABEL}</span>
            <span>{catalogSize} review-backed sneakers</span>
            <span>{useLlm ? 'AI refine on' : 'Review-ranked shortlist'}</span>
          </div>

          <p className="brand-mark">SneakPeek</p>
          <h1 className="hero-title"></h1>
          <p className="hero-copy">
            Keep the search simple. Pick a lane and describe what matters most. SneakPeek turns real sneaker reviews
            into a tight shortlist instead of a wall of options.
          </p>

          <div className="category-row" role="tablist" aria-label="Sneaker category">
            {CATEGORY_OPTIONS.map(option => (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={category === option}
                className={`category-chip ${category === option ? 'active' : ''}`}
                onClick={() => handleCategorySelect(option)}
              >
                {option}
              </button>
            ))}
          </div>

          <form className="search-panel" onSubmit={handleSubmit}>
            <label className="query-label" htmlFor="use-case-input">
              Describe the shoe you want
            </label>

            <div className="query-field" onClick={() => textareaRef.current?.focus()}>
              <img src={SearchIcon} alt="" aria-hidden="true" />
              <textarea
                ref={textareaRef}
                id="use-case-input"
                className="use-case-box"
                value={useCase}
                onChange={event => setUseCase(event.target.value)}
                onKeyDown={event => {
                  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                    event.preventDefault()
                    void runSearch(category, category, useCase)
                  }
                }}
                rows={3}
                spellCheck={false}
              />
            </div>

            <div className="hero-actions">
              <button className="search-button" type="submit" disabled={isSearching}>
                {isSearching ? 'Scanning Reviews...' : 'Find Matches'}
              </button>
              <p className="search-note">{heroNote}</p>
            </div>
          </form>
        </div>
      </header>

      <main className="page-content">
        <section className="results-shell">
          <div className="results-bar">
            <div className="results-heading">
              <p className="section-kicker">Matches</p>
              <h2>{topPick ? `${capitalizeLabel(category)} shortlist` : 'No matches loaded'}</h2>
            </div>
            <p className="results-note">{resultsNote}</p>
          </div>

          {sneakers.length > 0 ? (
            <div className="result-grid">
              {sneakers.map((sneaker, index) => {
                const isFeatured = index === 0
                const hasPenalty = sneaker.match_reasons.some(reason => reason.includes('Penalty'))
                const specEntries = buildSpecEntries(sneaker).slice(0, isFeatured ? 4 : 2)
                const reasonEntries = sneaker.match_reasons.slice(0, isFeatured ? 3 : 2)
                const evidenceText = truncateText(sneaker.review_evidence, isFeatured ? 220 : 110)
                const reviewSnippet = truncateText(
                  sneaker.sample_reviews[0] || 'No sample review available.',
                  isFeatured ? 180 : 110
                )
                const visualStyle = {
                  '--card-shoe-position': CARD_POSITIONS[index % CARD_POSITIONS.length],
                } as CSSProperties

                return (
                  <article key={sneaker.id} className={`result-card ${isFeatured ? 'featured' : ''}`}>
                    <div className="result-card-copy">
                      <div className="result-card-head">
                        <div>
                          <p className="result-category">{sneaker.category}</p>
                          <h3>{sneaker.shoe_name}</h3>
                        </div>
                        {/* Peer Fix: Clearer top match indicator instead of forced 100% */}
                        <span className="result-score">
                          {isFeatured ? '🏆 Top Match' : `Match ${sneaker.match_score}%`}
                        </span>
                      </div>

                      {sneaker.signature_player && (
                        <p className="result-signature">Signature: {sneaker.signature_player}</p>
                      )}

                      <p className="result-copy">{evidenceText}</p>

                      {reasonEntries.length > 0 && (
                        <ul className="reason-chip-row">
                          {reasonEntries.map((reason, reasonIndex) => (
                            <li
                              key={reasonIndex}
                              className={`reason-chip reason-chip-${getReasonTone(reason)}`}
                            >
                              {reason}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    <div className="result-card-side">
                      <ShoeVisual
                        imageUrl={sneaker.image_url}
                        shoeName={sneaker.shoe_name}
                        visualStyle={visualStyle}
                        featured={isFeatured}
                      />

                      {specEntries.length > 0 && (
                        <dl className={`spec-list ${isFeatured ? '' : 'compact'}`}>
                          {specEntries.map(entry => (
                            <div key={entry.label}>
                              <dt>{entry.label}</dt>
                              <dd>{entry.value}</dd>
                            </div>
                          ))}
                        </dl>
                      )}

                      {isFeatured ? (
                        <blockquote className="review-quote">"{reviewSnippet}"</blockquote>
                      ) : (
                        <p className="mini-review">"{reviewSnippet}"</p>
                      )}

                      {hasPenalty && sneaker.expert_penalty_detail && (
                        <details className="penalty-detail">
                          <summary>See penalty detail</summary>
                          <p className="penalty-detail-text">{sneaker.expert_penalty_detail}</p>
                        </details>
                      )}

                      {sneaker.footlocker_url && (
                        <a className="shoe-link" href={sneaker.footlocker_url} target="_blank" rel="noreferrer">
                          View source reviews
                        </a>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <div className="empty-state">
              <h3>No matches loaded</h3>
              <p>{errorMessage || 'Try a different category or tighten the use case to surface a stronger fit.'}</p>
            </div>
          )}
        </section>

        {useLlm && (
          <div className="chat-floating">
            <button
              className="chat-toggle-btn"
              onClick={() => setChatOpen(o => !o)}
              aria-label={chatOpen ? 'Close AI chat' : 'Open AI chat'}
            >
              {chatOpen ? '✕' : 'Ask AI'}
            </button>
            {chatOpen && (
              <Chat
                sneakers={sneakers} 
                onSearchTerm={(term: string) => {
                  const refinedTerm = term.trim()
                  if (!refinedTerm) return
                  setUseCase(refinedTerm)
                  void runSearch(category, category, refinedTerm)
                }}
              />
            )}
          </div>
        )}
      </main>
    </div>
  )
}

export default App
