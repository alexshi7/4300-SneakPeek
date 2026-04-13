"""
inspect_svd.py  —  diagnostic tool for the Foot Locker SVD model

Run from the src/ directory:
    python inspect_svd.py
    python inspect_svd.py "everyday runner plush cushion"

Outputs:
  1. Top positive / negative terms for every latent dimension
  2. Query activation profile — which dimensions the query fires on (+ or -)
  3. Top-5 shoe matches with the driving dimension highlighted
"""

import sys
import os
import math
import numpy as np
from collections import Counter

# Allow importing shoe_search from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shoe_search as ss


def _print_dimensions(model, top_n=6):
    Vt_k = model["Vt_k"]       # (k, n_terms)
    idx_to_vocab = {i: w for w, i in model["vocab_idx"].items()}
    k = Vt_k.shape[0]

    print("=" * 70)
    print(f"LATENT DIMENSIONS  (k={k}, vocab={Vt_k.shape[1]} terms)")
    print("=" * 70)

    for dim in range(k):
        row = Vt_k[dim]
        pos_idx = np.argsort(row)[::-1][:top_n]
        neg_idx = np.argsort(row)[:top_n]

        pos_words = [f"{idx_to_vocab[i]} ({row[i]:+.3f})" for i in pos_idx]
        neg_words = [f"{idx_to_vocab[i]} ({row[i]:+.3f})" for i in neg_idx]

        print(f"\nDim {dim+1:2d}  (+) {', '.join(pos_words)}")
        print(f"        (-) {', '.join(neg_words)}")


def _query_activation(model, query_text, top_n=5):
    """
    Project a query into SVD space and show which dimensions it activates
    positively and negatively.
    """
    vocab_idx = model["vocab_idx"]
    idf       = model["idf"]
    n_terms   = len(vocab_idx)
    Vt_k      = model["Vt_k"]
    s_k       = model["s_k"]
    idx_to_vocab = {i: w for w, i in vocab_idx.items()}

    counts = Counter(ss._tokenize(query_text))
    q = np.zeros(n_terms)
    for tok, cnt in counts.items():
        idx = vocab_idx.get(tok)
        if idx is not None:
            q[idx] = cnt * idf[idx]

    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        print("Query has no overlap with the Foot Locker vocabulary.")
        return None
    q = q / q_norm

    q_svd = (q @ Vt_k.T) / (s_k + 1e-9)
    q_svd_norm = np.linalg.norm(q_svd)
    if q_svd_norm == 0:
        print("Query projects to zero in SVD space.")
        return None
    q_svd = q_svd / q_svd_norm

    print("\n" + "=" * 70)
    print(f"QUERY ACTIVATION PROFILE  →  \"{query_text}\"")
    print("=" * 70)

    ranked = np.argsort(np.abs(q_svd))[::-1][:top_n]
    for dim in ranked:
        sign   = "+" if q_svd[dim] >= 0 else "-"
        row    = Vt_k[dim]
        # show top concept words in the direction of activation
        if q_svd[dim] >= 0:
            top_idx = np.argsort(row)[::-1][:4]
        else:
            top_idx = np.argsort(row)[:4]
        concept = ", ".join(idx_to_vocab[i] for i in top_idx)
        print(f"  Dim {dim+1:2d}  activation={sign}{abs(q_svd[dim]):.4f}  concept: [{concept}]")

    return q_svd


def _top_shoe_matches(model, q_svd, top_n=5):
    shoe_vecs = model["shoe_vecs"]   # (n_shoes, k)
    shoes     = model["shoes"]
    Vt_k      = model["Vt_k"]
    idx_to_vocab = {i: w for w, i in model["vocab_idx"].items()}

    sims         = np.clip(shoe_vecs @ q_svd, 0.0, 1.0)
    contributions = shoe_vecs * q_svd              # (n_shoes, k) element-wise

    top_shoe_idx = np.argsort(sims)[::-1][:top_n]

    print("\n" + "=" * 70)
    print("TOP SHOE MATCHES VIA SVD")
    print("=" * 70)

    for rank, si in enumerate(top_shoe_idx, 1):
        name   = shoes[si]
        score  = sims[si]
        c_row  = contributions[si]

        # Top positive contributing dimension
        pos_dim = int(np.argmax(c_row))
        neg_dim = int(np.argmin(c_row))

        def dim_label(d):
            row = Vt_k[d]
            if q_svd[d] >= 0:
                top_idx = np.argsort(row)[::-1][:3]
            else:
                top_idx = np.argsort(row)[:3]
            words = ", ".join(idx_to_vocab[i] for i in top_idx)
            sign  = "+" if q_svd[d] >= 0 else "-"
            return f"Dim {d+1} [{sign}] ({words})"

        print(f"\n  #{rank}  {name}  (score={score:.4f})")
        print(f"       Driving match:    {dim_label(pos_dim)}  contrib={c_row[pos_dim]:+.4f}")
        if c_row[neg_dim] < -0.001:
            print(f"       Counter-dim:      {dim_label(neg_dim)}  contrib={c_row[neg_dim]:+.4f}")


def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "stylish retro chunky streetwear"

    print("Loading catalog and building SVD model…")
    ss.load_catalog()
    model = ss._load_fl_svd()

    if model is None:
        print("SVD model unavailable — is footlocker_reviews_cleaned.csv present?")
        sys.exit(1)

    _print_dimensions(model)
    q_svd = _query_activation(model, query)
    if q_svd is not None:
        _top_shoe_matches(model, q_svd)


if __name__ == "__main__":
    main()
