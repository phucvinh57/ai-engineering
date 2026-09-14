import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import { sendFeedback, streamChat, type ChatMessage, type SourceRef } from "../api";
import { resetSession } from "../session";

interface DisplayMessage extends ChatMessage {
  sources?: SourceRef[];
  thinking?: string;
  thinkingDone?: boolean;
  traceId?: string;
  feedback?: 0 | 1 | null;
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

function FeedbackBar({ message, onRate }: { message: DisplayMessage; onRate: (value: 0 | 1) => void }) {
  if (!message.traceId) return null;
  return (
    <div className="feedback">
      <button
        type="button"
        aria-label="Helpful"
        aria-pressed={message.feedback === 1}
        className={message.feedback === 1 ? "active" : ""}
        onClick={() => onRate(1)}
      >
        👍
      </button>
      <button
        type="button"
        aria-label="Not helpful"
        aria-pressed={message.feedback === 0}
        className={message.feedback === 0 ? "active" : ""}
        onClick={() => onRate(0)}
      >
        👎
      </button>
    </div>
  );
}

export default function Chat() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // A page reload keeps sessionStorage's session id while this component
    // remounts with no messages, which would otherwise let one Langfuse
    // session span two unrelated conversations.
    if (messages.length === 0) resetSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Rebuilds only the last element instead of the whole array, so per-message
  // state (traceId, feedback) set after streaming ends isn't clobbered by a
  // later render, and so we're not reallocating the full history on every token.
  function patchLast(patch: Partial<DisplayMessage>) {
    setMessages((prev) =>
      prev.map((m, i) => (i === prev.length - 1 ? { ...m, ...patch } : m))
    );
  }

  async function send() {
    const question = input.trim();
    if (!question || busy) return;

    const history = [...messages, { role: "user" as const, content: question }];
    setMessages(history);
    setInput("");
    setBusy(true);

    let assistantText = "";
    let assistantThinking = "";
    setMessages([...history, { role: "assistant", content: "" }]);

    try {
      await streamChat(history, {
        onStart: ({ traceId }) => patchLast({ traceId }),
        onSources: (sources) => patchLast({ sources }),
        onThinking: (text) => {
          assistantThinking += text;
          patchLast({ thinking: assistantThinking, thinkingDone: false });
        },
        onToken: (text) => {
          assistantText += text;
          patchLast({ content: assistantText, thinkingDone: true });
        },
        onDone: ({ traceId }) => {
          patchLast({ traceId, feedback: null });
          setBusy(false);
        },
        onError: (message) => {
          patchLast({ content: `Error: ${message}` });
          setBusy(false);
        },
      });
    } catch (err) {
      patchLast({ content: `Error: ${String(err)}` });
      setBusy(false);
    }
  }

  async function rate(index: number, value: 0 | 1) {
    const target = messages[index];
    if (!target?.traceId || target.feedback === value) return;

    const previous = target.feedback ?? null;
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, feedback: value } : m)));

    const comment = value === 0 ? (window.prompt("What went wrong? (optional)") ?? undefined) : undefined;
    const ok = await sendFeedback(target.traceId, value, comment);
    if (!ok) {
      setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, feedback: previous } : m)));
    }
  }

  return (
    <div className="panel">
      <div className="messages">
        {messages.length === 0 && (
          <p className="hint">Ask about the Tauri Rust/JS APIs, plugins, or the permissions system.</p>
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
            {m.role === "assistant" && <FeedbackBar message={m} onRate={(value) => rate(i, value)} />}
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
          placeholder="e.g. How do I read a file from the frontend with the fs plugin?"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
