import { useState } from "react";
import { search, type SearchResult } from "../api";

export default function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSearch() {
    if (!query.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResults(await search(query.trim()));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          runSearch();
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. difference between wl_shell and xdg_shell"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !query.trim()}>
          Search
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <div className="results">
        {results.map((r, i) => (
          <div key={i} className="result">
            <div className="result-header">
              <span className="result-rank">#{i + 1}</span>
              <a href={r.url} target="_blank" rel="noreferrer">
                {r.heading_path}
              </a>
              <span className="result-score">{r.score.toFixed(3)}</span>
            </div>
            <p className="result-snippet">{r.text.slice(0, 400)}...</p>
          </div>
        ))}
      </div>
    </div>
  );
}
