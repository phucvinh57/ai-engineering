import { useState } from "react";
import Chat from "./components/Chat";
import Search from "./components/Search";

type Tab = "chat" | "search";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");

  return (
    <div className="app">
      <header>
        <h1>Wayland Assistant</h1>
        <nav>
          <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>
            Chat
          </button>
          <button className={tab === "search" ? "active" : ""} onClick={() => setTab("search")}>
            Search
          </button>
        </nav>
      </header>
      <main>{tab === "chat" ? <Chat /> : <Search />}</main>
    </div>
  );
}
