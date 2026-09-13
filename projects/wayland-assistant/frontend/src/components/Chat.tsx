import { useState } from "react";
import { streamChat, type ChatMessage, type SourceRef } from "../api";

interface DisplayMessage extends ChatMessage {
  sources?: SourceRef[];
}

export default function Chat() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const question = input.trim();
    if (!question || busy) return;

    const history = [...messages, { role: "user" as const, content: question }];
    setMessages(history);
    setInput("");
    setBusy(true);

    let assistantText = "";
    let assistantSources: SourceRef[] = [];
    setMessages([...history, { role: "assistant", content: "" }]);

    try {
      await streamChat(history, {
        onSources: (sources) => {
          assistantSources = sources;
          setMessages([...history, { role: "assistant", content: assistantText, sources: assistantSources }]);
        },
        onToken: (text) => {
          assistantText += text;
          setMessages([...history, { role: "assistant", content: assistantText, sources: assistantSources }]);
        },
        onDone: () => setBusy(false),
        onError: (message) => {
          assistantText = `Error: ${message}`;
          setMessages([...history, { role: "assistant", content: assistantText }]);
          setBusy(false);
        },
      });
    } catch (err) {
      setMessages([...history, { role: "assistant", content: `Error: ${String(err)}` }]);
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <div className="messages">
        {messages.length === 0 && (
          <p className="hint">Ask about Wayland protocols, extensions, or wlroots compositor APIs.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="message-content">{m.content}</div>
            {m.sources && m.sources.length > 0 && (
              <div className="sources">
                {m.sources.map((s, j) => (
                  <a key={j} href={s.url} target="_blank" rel="noreferrer" className="source-chip">
                    [{j + 1}] {s.heading_path}
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. How do I implement layer-shell in a wlroots compositor?"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
