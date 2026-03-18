import { useState, useEffect } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Sneaker } from './types' // Changed from Episode to Sneaker
import Chat from './Chat'

function App(): JSX.Element {
  const [useLlm, setUseLlm] = useState<boolean | null>(null)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [sneakers, setSneakers] = useState<Sneaker[]>([]) // Changed state

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(data => setUseLlm(data.use_llm))
  }, [])

  const handleSearch = async (value: string): Promise<void> => {
    setSearchTerm(value)
    if (value.trim() === '') { setSneakers([]); return }
    
    // We will update your backend route to /api/sneakers later!
    const response = await fetch(`/api/sneakers?query=${encodeURIComponent(value)}`)
    const data: Sneaker[] = await response.json()
    setSneakers(data)
  }

  if (useLlm === null) return <></>

  return (
    <div className={`full-body-container ${useLlm ? 'llm-mode' : ''}`}>
      {/* Search bar */}
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
        <div className="input-box" onClick={() => document.getElementById('search-input')?.focus()}>
          <img src={SearchIcon} alt="search" />
          <input
            id="search-input"
            placeholder="Search for your perfect sneaker (e.g., lightweight running, retro hoops)..."
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Search results - Sneaker Cards */}
      <div id="answer-box">
        {sneakers.map((sneaker, index) => (
          <div key={index} className="episode-item"> 
            <h3 className="episode-title">{sneaker.shoe_name}</h3>
            <p className="episode-desc"><strong>Style:</strong> {sneaker.style}</p>
            <p className="episode-desc"><strong>Best Price:</strong> ${sneaker.best_price}</p>
            <p className="episode-rating">Audience Score: {sneaker.audience_score}/100</p>
          </div>
        ))}
      </div>

      {/* Chat Component */}
      {useLlm && <Chat onSearchTerm={handleSearch} />}
    </div>
  )
}

export default App
