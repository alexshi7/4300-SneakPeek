import { useEffect, useState } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import Chat from './Chat'
import { SearchResponse, Sneaker } from './types'

const CATEGORY_OPTIONS = ['basketball', 'running', 'lifestyle']

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [catalogSize, setCatalogSize] = useState<number>(0)
  const [category, setCategory] = useState<string>('basketball')
  const [query, setQuery] = useState<string>('basketball shoe')
  const [useCase, setUseCase] = useState<string>(
    "I'm a tall point guard who wants lightweight shoes with good traction, a star-player connection, and strong style."
  )
  const [sneakers, setSneakers] = useState<Sneaker[]>([])
  const [requestedAttributes, setRequestedAttributes] = useState<string[]>([])

  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(data => {
        setUseLlm(data.use_llm)
        setCatalogSize(data.catalog_size || 0)
      })
  }, [])

  const runSearch = async (
    nextQuery: string = query,
    nextCategory: string = category,
    nextUseCase: string = useCase
  ): Promise<void> => {
    const params = new URLSearchParams({
      query: nextQuery,
      category: nextCategory,
      use_case: nextUseCase,
    })
    const response = await fetch(`/api/sneakers?${params.toString()}`)
    const data: SearchResponse = await response.json()
    setSneakers(data.results)
    setRequestedAttributes(data.applied_filters.requested_attributes)
  }

  useEffect(() => {
    if (useLlm !== null) {
      void runSearch()
    }
  }, [useLlm])

  if (useLlm === null) return <></>

  return (
    <div className={`full-body-container ${useLlm ? 'llm-mode' : ''}`}>
      <div className="top-text">
        <div className="google-colors">
          <h1 id="google-4">S</h1>
          <h1 id="google-3">n</h1>
          <h1 id="google-0-1">e</h1>
          <h1 id="google-0-2">a</h1>
          <h1 id="google-4">k</h1>
          <h1 id="google-3">P</h1>
          <h1 id="google-0-1">e</h1>
          <h1 id="google-0-2">e</h1>
          <h1 id="google-4">k</h1>
        </div>
        <p className="subheading">
          Match a shoe category plus a detailed use case against {catalogSize} review-backed sneakers.
        </p>

        <div className="category-row">
          {CATEGORY_OPTIONS.map(option => (
            <button
              key={option}
              type="button"
              className={`category-chip ${category === option ? 'active' : ''}`}
              onClick={() => setCategory(option)}
            >
              {option}
            </button>
          ))}
        </div>

        <div className="input-box" onClick={() => document.getElementById('search-input')?.focus()}>
          <img src={SearchIcon} alt="search" />
          <input
            id="search-input"
            placeholder="Enter the broad shoe search, like basketball shoe or retro runner"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>

        <textarea
          className="use-case-box"
          placeholder="Describe your use case and priorities."
          value={useCase}
          onChange={e => setUseCase(e.target.value)}
        />

        <button className="search-button" type="button" onClick={() => void runSearch()}>
          Find Matches
        </button>

        {requestedAttributes.length > 0 && (
          <p className="request-summary">
            Interpreted priorities: {requestedAttributes.join(', ')}
          </p>
        )}
      </div>

      <div id="answer-box">
        {sneakers.map(sneaker => (
          <article key={sneaker.id} className="episode-item">
            <div className="card-topline">
              <span className="category-pill">{sneaker.category}</span>
              <span className="episode-rating">Match {sneaker.match_score}</span>
            </div>
            <h3 className="episode-title">{sneaker.shoe_name}</h3>
            <p className="episode-desc">
              Reviews analyzed: {sneaker.review_count}
              {sneaker.signature_player ? ` • Signature: ${sneaker.signature_player}` : ''}
            </p>
            <p className="episode-desc">
              {[
                sneaker.specs.price_usd ? `Price: $${sneaker.specs.price_usd}` : '',
                sneaker.specs.traction_score ? `Traction: ${sneaker.specs.traction_score}` : '',
                sneaker.specs.top_style ? `Top: ${sneaker.specs.top_style}` : '',
              ]
                .filter(Boolean)
                .join(' • ')}
            </p>
            <p className="episode-desc">
              Top review evidence: {sneaker.match_reasons.join(' • ') || 'General text overlap'}
            </p>
            <div className="signal-row">
              <span>Lightweight {sneaker.review_signals.lightweight || 0}</span>
              <span>Traction {sneaker.review_signals.traction || 0}</span>
              <span>Style {sneaker.review_signals.stylish || 0}</span>
              <span>Support {sneaker.review_signals.support || 0}</span>
            </div>
            <p className="episode-desc review-snippet">
              "{sneaker.sample_reviews[0] || 'No sample review available.'}"
            </p>
            {sneaker.footlocker_url && (
              <a className="shoe-link" href={sneaker.footlocker_url} target="_blank" rel="noreferrer">
                View source reviews
              </a>
            )}
          </article>
        ))}
      </div>

      {useLlm && <Chat onSearchTerm={(term: string) => setUseCase(term)} />}
    </div>
  )
}

export default App
