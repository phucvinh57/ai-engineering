export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SourceRef {
  heading_path: string;
  url: string;
  source: string;
  score: number;
}

export interface SearchResult {
  text: string;
  heading_path: string;
  url: string;
  source: string;
  score: number;
}

type ChatCallbacks = {
  onSources: (sources: SourceRef[]) => void;
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
};

export async function streamChat(messages: ChatMessage[], callbacks: ChatCallbacks): Promise<void> {
  const resp = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });

  if (!resp.ok || !resp.body) {
    callbacks.onError(`Request failed: ${resp.status}`);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const raw of events) {
      if (!raw.trim()) continue;
      const lines = raw.split("\n");
      let eventName = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) data = line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data);

      if (eventName === "sources") callbacks.onSources(parsed.sources ?? []);
      else if (eventName === "token") callbacks.onToken(parsed.text ?? "");
      else if (eventName === "done") callbacks.onDone();
    }
  }
}

export async function search(query: string, topK = 8): Promise<SearchResult[]> {
  const resp = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!resp.ok) throw new Error(`Search failed: ${resp.status}`);
  const data = await resp.json();
  return data.results ?? [];
}

export interface Stats {
  total_chunks: number;
  chunks_by_source: Record<string, number>;
  last_fetch_at: string | null;
}

export async function getStats(): Promise<Stats> {
  const resp = await fetch("/api/stats");
  if (!resp.ok) throw new Error(`Stats failed: ${resp.status}`);
  return resp.json();
}
