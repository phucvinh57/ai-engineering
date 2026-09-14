// Client-generated identifiers used only to group Langfuse traces into
// sessions and (anonymously) into users -- never sent anywhere but our own
// backend, and never the real signed-in identity of anyone using this tool.
const SESSION_KEY = "ta_session_id";
const USER_KEY = "ta_user_id";

function readOrCreate(storage: Storage, key: string, make: () => string): string {
  try {
    const existing = storage.getItem(key);
    if (existing) return existing;
    const created = make();
    storage.setItem(key, created);
    return created;
  } catch {
    // Private browsing / blocked storage: fall back to a value that's
    // stable for this call but won't persist -- feedback/session grouping
    // just degrades, it never breaks the chat itself.
    return make();
  }
}

/** One id per tab per conversation -- a new tab starts a new session, which
 * matches Chat.tsx's per-mount message state. */
export function getSessionId(): string {
  return readOrCreate(sessionStorage, SESSION_KEY, () => crypto.randomUUID());
}

export function resetSession(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // ignore
  }
}

/** A stable anonymous id across tabs/reloads, deliberately not tied to any
 * real identity. */
export function getUserId(): string {
  return readOrCreate(localStorage, USER_KEY, () => `anon-${crypto.randomUUID()}`);
}
