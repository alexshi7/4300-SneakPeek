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
import { SearchResponse, Sneaker } from './types'

const CATEGORY_OPTIONS = ['basketball', 'running', 'lifestyle'] as const
type Category = (typeof CATEGORY_OPTIONS)[number]

const VERSION_LABEL = 'Version 5.0'
const CATEGORY_DEFAULTS: Record<Category, string> = {
  basketball: "I'm a tall point guard who wants lightweight shoes with good traction, a star-player connection, and strong style.",
  lifestyle:  'y2k dad shoe that is comfortable',
  running:    'I want a shoe for trail running in the woods',
}
const CATEGORY_SUGGESTIONS: Record<Category, string> = {
  basketball: 'Suggestions: Traction, cushion, containment, ankle support, court grip, …',
  running:    'Suggestions: Cushion, durability, lightweight, breathability, stability, …',
  lifestyle:  'Suggestions: Comfort, stylish, casual, versatile, y2k, …',
}
const DEFAULT_USE_CASE = CATEGORY_DEFAULTS['basketball']
const SEARCH_ERROR_MESSAGE = 'Unable to load sneaker matches right now. Try the search again in a moment.'

interface SpecEntry {
  label: string
  value: string
}

interface LatentAxis {
  label: string
  dimension?: number
  queryValue?: number
  shoeValue?: number
  value: number
}

const CARD_POSITIONS = ['10% 20%', '62% 24%', '82% 68%', '22% 72%', '50% 58%', '72% 14%']

const capitalizeLabel = (value: string): string => value.charAt(0).toUpperCase() + value.slice(1)

const clamp = (value: number, min: number, max: number): number => Math.min(Math.max(value, min), max)

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
  if (reason.includes("Expert's Note")) return 'penalty'
  if (reason.includes('SVD')) return 'svd'
  if (reason.includes('Name')) return 'name'
  return 'default'
}

const formatAxisLabel = (value: string): string =>
  value
    .replace(/[_-]+/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

const CATEGORY_FALLBACK_AXES: Record<string, string[]> = {
  basketball: ['Traction', 'Cushion', 'Support', 'Lockdown', 'Weight', 'Court Feel'],
  running:    ['Cushion', 'Energy', 'Breathability', 'Stability', 'Pace', 'Distance'],
  lifestyle:  ['Style', 'Comfort', 'Fit', 'Materials', 'Versatility', 'Look'],
}

const buildLatentAxes = (sneaker: Sneaker): LatentAxis[] => {
  if (sneaker.svd_profile && sneaker.svd_profile.length >= 3) {
    const maxValue = Math.max(
      ...sneaker.svd_profile.flatMap(axis => [axis.query_value, axis.shoe_value]),
      0.01
    )
    return sneaker.svd_profile.slice(0, 6).map(axis => ({
      label: formatAxisLabel(axis.label || `Dimension ${axis.dimension}`),
      dimension: axis.dimension,
      queryValue: clamp(axis.query_value / maxValue, 0.08, 1),
      shoeValue: clamp(axis.shoe_value / maxValue, 0, 1),
      value: clamp(axis.shoe_value / maxValue, 0, 1),
    }))
  }

  const numericSignals = Object.entries(sneaker.review_signals)
    .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && Number.isFinite(entry[1]))
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 6)

  if (numericSignals.length >= 3) {
    const maxSignal = Math.max(...numericSignals.map(([, value]) => Math.abs(value)), 1)
    return numericSignals.map(([label, value]) => ({
      label: formatAxisLabel(label),
      value: clamp(Math.abs(value) / maxSignal, 0.12, 1),
    }))
  }

  const terms = sneaker.top_terms.slice(0, 6)
  const matchWeight = clamp(sneaker.match_score / 100, 0.2, 1)

  const termAxes = terms.map((term, index) => {
    const rankWeight = 1 - index / Math.max(terms.length, 1)
    const wave = 0.08 * Math.sin((index + 1) * 1.7 + sneaker.shoe_name.length)
    return {
      label: formatAxisLabel(term),
      value: clamp(matchWeight * 0.62 + rankWeight * 0.3 + wave, 0.16, 1),
    }
  })

  // Pad with category-specific fallback labels so we always reach 6 axes
  const fallbacks = CATEGORY_FALLBACK_AXES[sneaker.category] ?? CATEGORY_FALLBACK_AXES['lifestyle']
  const existingLabels = new Set(termAxes.map(a => a.label.toLowerCase()))
  const padding = fallbacks
    .filter(label => !existingLabels.has(label.toLowerCase()))
    .slice(0, Math.max(0, 6 - termAxes.length))
    .map((label, index) => ({
      label,
      value: clamp(0.22 + 0.06 * Math.sin(index * 2.1 + sneaker.shoe_name.length), 0.16, 0.45),
    }))

  return [...termAxes, ...padding].slice(0, 6)
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

interface RadarTooltip { label: string; dimension?: number; queryValue?: number; shoeValue?: number; value: number; x: number; y: number }

function SvdRadarChart({ sneaker, featured }: { sneaker: Sneaker; featured: boolean }): JSX.Element | null {
  const [tooltip, setTooltip] = useState<RadarTooltip | null>(null)
  const axes = buildLatentAxes(sneaker)
  if (axes.length < 3) return null

  const center = 108
  const radius = featured ? 62 : 50
  const labelRadius = featured ? 86 : 70
  const levels = [0.2, 0.4, 0.6, 0.8, 1]
  const pointsFor = (scale: number): string =>
    axes
      .map((_, index) => {
        const angle = -Math.PI / 2 + (2 * Math.PI * index) / axes.length
        const x = center + Math.cos(angle) * radius * scale
        const y = center + Math.sin(angle) * radius * scale
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  const profilePoints = axes
    .map((axis, index) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * index) / axes.length
      const x = center + Math.cos(angle) * radius * axis.value
      const y = center + Math.sin(angle) * radius * axis.value
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const queryPoints = axes
    .map((axis, index) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * index) / axes.length
      const value = axis.queryValue ?? axis.value
      const x = center + Math.cos(angle) * radius * value
      const y = center + Math.sin(angle) * radius * value
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const hasQueryOverlay = axes.some(axis => axis.queryValue !== undefined)

  const TIP_W = hasQueryOverlay ? 88 : 62
  const TIP_H = 26
  const tipX = clamp(tooltip?.x ?? 0, TIP_W / 2 + 2, 216 - TIP_W / 2 - 2)
  const tipY = (tooltip?.y ?? 0) < 40 ? (tooltip?.y ?? 0) + 14 : (tooltip?.y ?? 0) - TIP_H - 6

  return (
    <figure className={`svd-profile ${featured ? 'featured-profile' : ''}`}>
      <figcaption>
        <span>SVD query match</span>
        <strong>{featured ? sneaker.shoe_name : 'Same axes'}</strong>
      </figcaption>

      <svg className="svd-radar" viewBox="0 0 216 216" role="img" aria-labelledby={`${sneaker.id}-svd-title`}>
        <title id={`${sneaker.id}-svd-title`}>SVD query and shoe latent profile for {sneaker.shoe_name}</title>
        {levels.map(level => (
          <polygon key={level} className="svd-grid-ring" points={pointsFor(level)} />
        ))}

        {axes.map((axis, index) => {
          const angle = -Math.PI / 2 + (2 * Math.PI * index) / axes.length
          const x = center + Math.cos(angle) * radius
          const y = center + Math.sin(angle) * radius
          const labelX = center + Math.cos(angle) * labelRadius
          const labelY = center + Math.sin(angle) * labelRadius
          const anchor = Math.abs(labelX - center) < 8 ? 'middle' : labelX > center ? 'start' : 'end'

          return (
            <g key={`${axis.label}-${index}`}>
              <line className="svd-axis-line" x1={center} y1={center} x2={x} y2={y} />
              <text className="svd-axis-label" x={labelX} y={labelY} textAnchor={anchor} dominantBaseline="middle">
                {truncateText(axis.label, featured ? 14 : 11)}
              </text>
            </g>
          )
        })}

        <polygon className="svd-profile-area" points={profilePoints} />
        <polyline className="svd-profile-line" points={`${profilePoints} ${profilePoints.split(' ')[0]}`} />
        {hasQueryOverlay && (
          <polyline className="svd-query-line" points={`${queryPoints} ${queryPoints.split(' ')[0]}`} />
        )}

        {axes.map((axis, index) => {
          const angle = -Math.PI / 2 + (2 * Math.PI * index) / axes.length
          const x = center + Math.cos(angle) * radius * axis.value
          const y = center + Math.sin(angle) * radius * axis.value
          return (
            <circle
              key={`${axis.label}-point`}
              className="svd-profile-point"
              cx={x}
              cy={y}
              r={featured ? 5 : 4.5}
              onMouseEnter={() => setTooltip({
                label: axis.label,
                dimension: axis.dimension,
                queryValue: axis.queryValue,
                shoeValue: axis.shoeValue,
                value: axis.value,
                x,
                y,
              })}
              onMouseLeave={() => setTooltip(null)}
            />
          )
        })}

        {tooltip && (
          <g className="svd-tooltip-group" style={{ pointerEvents: 'none' }}>
            <rect
              x={tipX - TIP_W / 2} y={tipY}
              width={TIP_W} height={TIP_H}
              rx={3} ry={3}
              className="svd-tooltip-bg"
            />
            <text x={tipX} y={tipY + 10} textAnchor="middle" className="svd-tooltip-label">
              {tooltip.dimension ? `Dim ${tooltip.dimension}` : truncateText(tooltip.label, 10)}
            </text>
            <text x={tipX} y={tipY + 21} textAnchor="middle" className="svd-tooltip-value">
              {tooltip.queryValue !== undefined
                ? `Q ${Math.round(tooltip.queryValue * 100)} / S ${Math.round((tooltip.shoeValue ?? 0) * 100)}`
                : `${Math.round(tooltip.value * 100)}%`}
            </text>
          </g>
        )}
      </svg>
      {hasQueryOverlay && (
        <div className="svd-legend" aria-hidden="true">
          <span><i className="svd-legend-query" />Query</span>
          <span><i className="svd-legend-shoe" />Shoe</span>
        </div>
      )}
    </figure>
  )
}

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [catalogSize, setCatalogSize] = useState<number>(0)
  const [category, setCategory] = useState<Category>('basketball')
  const [useCase, setUseCase] = useState<string>(DEFAULT_USE_CASE)
  const [sneakers, setSneakers] = useState<Sneaker[]>([])
  const [requestedAttributes, setRequestedAttributes] = useState<string[]>([])
  const [isSearching, setIsSearching] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [llmExplanations, setLlmExplanations] = useState<Record<string, string>>({})
  const [llmLoading, setLlmLoading] = useState<Record<string, boolean>>({})
  const [irQuery, setIrQuery] = useState<string>('')
  const [ragSummary, setRagSummary] = useState<string>('')
  const [ragSummaryLoading, setRagSummaryLoading] = useState<boolean>(false)
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

  const fetchRagSummary = async (
    originalQuery: string,
    expandedIrQuery: string,
    results: Sneaker[]
  ): Promise<void> => {
    if (!results.length) return
    setRagSummaryLoading(true)
    setRagSummary('')
    try {
      const response = await fetch('/api/rag-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: originalQuery, ir_query: expandedIrQuery, results }),
      })
      if (!response.ok || !response.body) throw new Error('RAG summary request failed')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        for (const line of decoder.decode(value).split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const chunk = JSON.parse(line.slice(6)) as { content?: string }
              if (chunk.content) setRagSummary(prev => prev + chunk.content)
            } catch { /* ignore malformed chunks */ }
          }
        }
      }
    } catch {
      const fallbackNames = results.slice(0, 4).map((shoe, index) => `${index + 1}. ${shoe.shoe_name}`).join(' ')
      setRagSummary(`RAG summary is temporarily unavailable, but retrieval completed. Ranked IR top 4: ${fallbackNames}`)
    } finally {
      setRagSummaryLoading(false)
    }
  }

  const runSearch = async (
    nextQuery: string = category,
    nextCategory: string = category,
    nextUseCase: string = useCase,
    useRag: boolean = false
  ): Promise<void> => {
    setIsSearching(true)
    setErrorMessage(null)
    setRagSummary('')
    setIrQuery('')

    try {
      const params = new URLSearchParams({
        query: nextQuery,
        category: nextCategory,
        use_case: nextUseCase,
        use_rag: String(useRag),
      })

      const response = await fetch(`/api/sneakers?${params.toString()}`)
      if (!response.ok) {
        throw new Error('Search request failed')
      }

      const data: SearchResponse = await response.json()
      const expandedIrQuery = data.ir_query || nextUseCase
      startTransition(() => {
        setSneakers(data.results)
        setRequestedAttributes(data.applied_filters.requested_attributes)
        setIrQuery(expandedIrQuery)
      })
      if (useLlm && useRag && data.results.length) {
        void fetchRagSummary(nextUseCase, expandedIrQuery, data.results)
      }
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
    void runSearch(category, category, useCase, false)
  }

  const handleRagSubmit = (): void => {
    void runSearch(category, category, useCase, true)
  }

  const handleCategorySelect = (nextCategory: Category): void => {
    const defaultText = CATEGORY_DEFAULTS[nextCategory]
    setCategory(nextCategory)
    setUseCase(defaultText)
    void runSearch(nextCategory, nextCategory, defaultText)
  }

  const explainShoe = async (shoe: Sneaker): Promise<void> => {
    const id = shoe.id
    if (llmLoading[id] || llmExplanations[id]) return
    setLlmLoading(prev => ({ ...prev, [id]: true }))
    setLlmExplanations(prev => ({ ...prev, [id]: '' }))

    try {
      const response = await fetch('/api/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: useCase, shoe }),
      })
      if (!response.ok || !response.body) throw new Error('Explain request failed')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        for (const line of decoder.decode(value).split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const chunk = JSON.parse(line.slice(6)) as { content?: string }
              if (chunk.content) {
                setLlmExplanations(prev => ({ ...prev, [id]: (prev[id] ?? '') + chunk.content }))
              }
            } catch { /* ignore malformed chunks */ }
          }
        }
      }
    } catch {
      setLlmExplanations(prev => ({ ...prev, [id]: 'Unable to generate explanation. Try again.' }))
    } finally {
      setLlmLoading(prev => ({ ...prev, [id]: false }))
    }
  }

  const topPick = sneakers[0]
  const topPickSpecs = topPick ? buildSpecEntries(topPick).slice(0, 4) : []
  const shortUseCase = truncateText(useCase.trim(), 108)
  const heroNote = errorMessage
    ? errorMessage
    : requestedAttributes.length > 0
      ? `Priority: ${requestedAttributes.join(', ')}.`
      : 'Search by feel, traction, cushioning, support, or style.'
  const resultsNote = topPick
    ? `Showing ${sneakers.length} ${category} matches for "${shortUseCase}". ${requestedAttributes.length > 0 ? `Prioritizing ${requestedAttributes.join(', ')}.` : ''}`
    : 'Pick a category and run a search to build the shortlist.'
  const scannerImage = topPick?.image_url || '/example8.jpg'
  const scannerLabel = topPick?.shoe_name || 'Sneaker scan preview'


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
    <div className={`app-shell theme-${category} ${useLlm ? 'llm-mode' : ''}`}>
      <div className="page-glow page-glow-left" aria-hidden="true" />
      <div className="page-glow page-glow-right" aria-hidden="true" />

      <div className="info-widget">
        <button className="info-btn" aria-label="How it works">?</button>
        <div className="info-popover">
          <p className="info-popover-heading">How it works</p>
          <dl className="info-popover-list">
            <dt>Search</dt>
            <dd>TF-IDF cosine similarity over 40k+ customer reviews, blended with per-category SVD (latent semantic) scoring.</dd>
            <dt>Match %</dt>
            <dd>Saturating curve (raw^0.4) so scores feel honest — no shoe is ever a perfect 100.</dd>
            <dt>Radar chart</dt>
            <dd>Shows the shoe's SVD latent profile. Hover dots for dimension scores.</dd>
            <dt>Search with RAG/LLM</dt>
            <dd>LLM rewrites your query into IR keywords, runs retrieval, then synthesizes a ranked summary from the top results.</dd>
            <dt>RAG/LLM on cards</dt>
            <dd>Explains a single shoe's IR match using its review evidence — no re-retrieval.</dd>
            <dt>Data</dt>
            <dd>Specs from RunRepeat. Reviews from Foot Locker and Amazon.</dd>
          </dl>
        </div>
      </div>

      <header className="hero-shell">
        <div className="hero-media" aria-hidden="true">
          <div className="star-field star-field-near" />
          <div className="star-field star-field-far" />
          <div key={category} className="category-atmosphere">
            <span className="theme-line theme-line-one" />
            <span className="theme-line theme-line-two" />
            <span className="theme-line theme-line-three" />
            <span className="theme-pulse theme-pulse-one" />
            <span className="theme-pulse theme-pulse-two" />
          </div>
        </div>

        <div className="hero-content">
          <div className="hero-copy-column">
            <div className="hero-meta">
              <span>{VERSION_LABEL}</span>
              <span>{catalogSize} review-backed sneakers</span>
              <span>{useLlm ? 'AI refine on' : 'Review-ranked shortlist'}</span>
            </div>

            <p className="brand-mark">SneakPeek</p>
            <h1 className="hero-title">Find the sneaker that fits how you move.</h1>
            <p className="hero-copy">
              Describe the technology, specifications, support, and style you want. SneakPeek turns real review language into a
              short, evidence-backed list for shoes you might need!{' '}
              <span className="hero-rag-promo">Results now have a RAG/LLM feature!</span>
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
                  <span className="category-chip-mark" aria-hidden="true" />
                  <span>{option}</span>
                </button>
              ))}
            </div>

            <p className="category-suggestions">{CATEGORY_SUGGESTIONS[category]}</p>

            <form className="search-panel" onSubmit={handleSubmit}>
              <label className="query-label" htmlFor="use-case-input">
                Describe the shoe you want
              </label>

              <div className="query-field" onClick={() => textareaRef.current?.focus()}>
                <img src={SearchIcon} alt="" aria-hidden="true" />
                <textarea
                  ref={textareaRef}
                  id="use-case-input"
                  className={`use-case-box${useCase === CATEGORY_DEFAULTS[category] ? ' use-case-default' : ''}`}
                  value={useCase}
                  onChange={event => setUseCase(event.target.value)}
                  onFocus={() => {
                    if (useCase === CATEGORY_DEFAULTS[category]) setUseCase('')
                  }}
                  onBlur={() => {
                    if (!useCase.trim()) setUseCase(CATEGORY_DEFAULTS[category] ?? '')
                  }}
                  onKeyDown={event => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      void runSearch(category, category, useCase, false)
                    }
                  }}
                  rows={3}
                  spellCheck={false}
                />
              </div>

              <div className="hero-actions">
                <button className="search-button" type="submit" disabled={isSearching}>
                  {isSearching ? 'Scanning…' : 'Find Matches'}
                </button>
                {useLlm && (
                  <button
                    className="search-button search-button-rag"
                    type="button"
                    disabled={isSearching || ragSummaryLoading}
                    onClick={handleRagSubmit}
                  >
                    {ragSummaryLoading ? 'Thinking…' : 'Search with RAG/LLM'}
                  </button>
                )}
                <p className="search-note">{heroNote}</p>
              </div>
            </form>
          </div>

          <aside className="hero-pick-panel" aria-live="polite">
            <div className="scanner-stage" aria-label={scannerLabel}>
              <div className="scanner-orbit orbit-one" aria-hidden="true" />
              <div className="scanner-orbit orbit-two" aria-hidden="true" />
              <div className="scanner-orbit orbit-three" aria-hidden="true" />

              <div className="scanner-shoe-shell">
                <img className="scanner-shoe scanner-shoe-main" src={scannerImage} alt="" />
                <span className="scanner-beam" aria-hidden="true" />
              </div>

              <div className="scanner-node node-one" aria-hidden="true" />
              <div className="scanner-node node-two" aria-hidden="true" />
              <div className="scanner-node node-three" aria-hidden="true" />

              <div className="scanner-readout" aria-hidden="true">
                <span>Fit vector</span>
                <strong>{topPick ? `${topPick.match_score}%` : 'Live'}</strong>
              </div>

            </div>

            <p className="panel-kicker">{topPick ? 'Current top match' : 'Search preview'}</p>
            {topPick ? (
              <>
                <div className="hero-pick-head">
                  <div>
                    <h2>{topPick.shoe_name}</h2>
                    {topPick.signature_player && <p>Signature: {topPick.signature_player}</p>}
                  </div>
                  <span className="hero-match-score">{topPick.match_score}%</span>
                </div>

                {topPickSpecs.length > 0 && (
                  <dl className="hero-spec-grid">
                    {topPickSpecs.map(entry => (
                      <div key={entry.label}>
                        <dt>{entry.label}</dt>
                        <dd>{entry.value}</dd>
                      </div>
                    ))}
                  </dl>
                )}

                <p className="hero-evidence">{truncateText(topPick.review_evidence, 150)}</p>
              </>
            ) : (
              <div className="hero-pick-empty">
                <p>Your best match will appear here after SneakPeek scans the review set.</p>
              </div>
            )}
          </aside>
        </div>
      </header>

      <main className="page-content">
        <section key={category} className="results-shell">
          <div className="results-bar">
            <div className="results-heading">
              <p className="section-kicker">Matches</p>
              <h2>{topPick ? `${capitalizeLabel(category)} shortlist` : 'No matches loaded'}</h2>
            </div>
            <p className="results-note">{resultsNote}</p>
          </div>

          {useLlm && (ragSummary || ragSummaryLoading) && (
            <div className="rag-summary-panel">
              <div className="rag-summary-header">
                <span className="rag-summary-label">RAG/LLM Answer</span>
                {irQuery && irQuery !== useCase && (
                  <span className="rag-summary-ir-query">
                    IR Enhanced query: <em>{irQuery}</em>
                  </span>
                )}
              </div>
              <p className="rag-summary-text">
                {ragSummary || <span className="rag-summary-thinking">Synthesizing results…</span>}
              </p>
              {sneakers.length > 0 && (
                <ol className="rag-top-four">
                  {sneakers.slice(0, 4).map(sneaker => (
                    <li key={sneaker.id}>
                      <span>{sneaker.shoe_name}</span>
                      <strong>{sneaker.match_score}%</strong>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}

          {sneakers.length > 0 ? (
            <div className="result-grid">
              {sneakers.map((sneaker, index) => {
                const hasPenalty = sneaker.match_reasons.some(reason => reason.includes("Expert's Note"))
                const specEntries = buildSpecEntries(sneaker).slice(0, 2)
                const reasonEntries = sneaker.match_reasons
                  .filter(r => !r.includes('SVD'))
                  .slice(0, 2)
                const evidenceText = truncateText(sneaker.review_evidence, 110)
                const reviewSnippet = truncateText(
                  sneaker.sample_reviews[0] || 'No sample review available.',
                  110
                )
                const visualStyle = {
                  '--card-shoe-position': CARD_POSITIONS[index % CARD_POSITIONS.length],
                } as CSSProperties

                return (
                  <article key={sneaker.id} className="result-card">
                    <div className="result-card-copy">
                      <div className="result-card-head">
                        <div>
                          <p className="result-category">{sneaker.category}</p>
                          <h3>{sneaker.shoe_name}</h3>
                        </div>
                        <div className="result-score-row">
                          <span className="result-score">
                            {`${sneaker.match_score}% match`}
                          </span>
                          {useLlm && (
                            <button
                              className="rag-btn"
                              disabled={llmLoading[sneaker.id]}
                              onClick={() => void explainShoe(sneaker)}
                            >
                              {llmLoading[sneaker.id] ? '...' : 'RAG/LLM'}
                            </button>
                          )}
                        </div>
                      </div>

                      {sneaker.signature_player && (
                        <p className="result-signature">Signature: {sneaker.signature_player}</p>
                      )}

                      <p className="result-copy">{evidenceText}</p>

                      {sneaker.top_terms.length > 0 && (
                        <div className="ir-terms-row">
                          <span className="ir-terms-label">IR matched</span>
                          {sneaker.top_terms.slice(0, 4).map(term => (
                            <span key={term} className="ir-term-chip">{term}</span>
                          ))}
                        </div>
                      )}

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

                      {llmExplanations[sneaker.id] && (
                        <p className="rag-explanation">{llmExplanations[sneaker.id]}</p>
                      )}
                    </div>

                    <div className="result-card-side">
                      <ShoeVisual
                        imageUrl={sneaker.image_url}
                        shoeName={sneaker.shoe_name}
                        visualStyle={visualStyle}
                        featured={false}
                      />

                      <SvdRadarChart sneaker={sneaker} featured={false} />

                      {specEntries.length > 0 && (
                        <dl className="spec-list compact">
                          {specEntries.map(entry => (
                            <div key={entry.label}>
                              <dt>{entry.label}</dt>
                              <dd>{entry.value}</dd>
                            </div>
                          ))}
                        </dl>
                      )}

                      <p className="mini-review">"{reviewSnippet}"</p>

                      {hasPenalty && sneaker.expert_penalty_detail && (
                        <details className="penalty-detail">
                          <summary>See expert's note</summary>
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

      </main>
    </div>
  )
}

export default App
