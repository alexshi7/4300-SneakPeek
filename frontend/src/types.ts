export interface Sneaker {
  id: string
  shoe_name: string
  category: string
  match_score: number
  review_count: number
  signature_player: string | null
  review_signals: Record<string, number>
  top_terms: string[]
  match_reasons: string[]
  sample_reviews: string[]
  footlocker_url: string
  specs: {
    weight_oz?: string | number
    heel_stack_mm?: string | number
    forefoot_stack_mm?: string | number
    price_usd?: string | number
    traction_score?: string | number
    breathability_score?: string | number
    ankle_support?: boolean
    top_style?: string
  }
}

export interface SearchResponse {
  results: Sneaker[]
  applied_filters: {
    query: string
    category: string
    use_case: string
    requested_attributes: string[]
  }
}
