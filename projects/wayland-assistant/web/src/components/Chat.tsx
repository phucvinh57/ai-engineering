import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import { streamChat, type ChatMessage, type SourceRef } from "../api";

interface DisplayMessage extends ChatMessage {
  sources?: SourceRef[];
  thinking?: string;
  thinkingDone?: boolean;
}

function ThinkingBlock({ text, done }: { text: string; done: boolean }) {
  const [expanded, setExpanded] = useState(true);
  const collapsedOnDone = useRef(false);

  useEffect(() => {
    if (done && !collapsedOnDone.current) {
      collapsedOnDone.current = true;
      setExpanded(false);
    }
  }, [done]);

  return (
    <div className="thinking">
      <button type="button" className="thinking-toggle" onClick={() => setExpanded((v) => !v)}>
        <span className={`thinking-caret ${expanded ? "open" : ""}`}>▸</span>
        {done ? "Thinking" : "Thinking…"}
      </button>
      {expanded && <div className="thinking-content">{text}</div>}
    </div>
  );
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
    let assistantThinking = "";
    let assistantSources: SourceRef[] = [];
    setMessages([...history, { role: "assistant", content: "" }]);

    try {
      await streamChat(history, {
        onSources: (sources) => {
          assistantSources = sources;
          setMessages([
            ...history,
            {
              role: "assistant",
              content: assistantText,
              sources: assistantSources,
              thinking: assistantThinking,
              thinkingDone: false,
            },
          ]);
        },
        onThinking: (text) => {
          assistantThinking += text;
          setMessages([
            ...history,
            {
              role: "assistant",
              content: assistantText,
              sources: assistantSources,
              thinking: assistantThinking,
              thinkingDone: false,
            },
          ]);
        },
        onToken: (text) => {
          assistantText += text;
          setMessages([
            ...history,
            {
              role: "assistant",
              content: assistantText,
              sources: assistantSources,
              thinking: assistantThinking,
              thinkingDone: true,
            },
          ]);
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
            {m.role === "assistant" && !!m.thinking && (
              <ThinkingBlock text={m.thinking} done={!!m.thinkingDone} />
            )}
            <div className="message-content">
              {m.role === "assistant" ? (
                <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{m.content}</ReactMarkdown>
              ) : (
                m.content
              )}
            </div>
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
