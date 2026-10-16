import { useEffect, useState, FormEvent } from "react";

type Todo = { id: number; text: string; done: boolean };

export default function App() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [text, setText] = useState("");

  async function load() {
    const r = await fetch("/api/todos");
    setTodos(await r.json());
  }
  useEffect(() => { load(); }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    await fetch("/api/todos", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text }),
    });
    setText("");
    load();
  }

  async function remove(id: number) {
    await fetch(`/api/todos/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <main style={{
      fontFamily: "system-ui, sans-serif",
      maxWidth: "32rem",
      margin: "3rem auto",
      padding: "0 1rem",
    }}>
      <h1>sample-fastapi todos</h1>
      <p style={{ color: "#666" }}>
        Pattern 2: FastAPI + Vite SPA &mdash; Postgres on dev-db-net,
        per-project Caddy splitting <code>/api/*</code> from the SPA.
      </p>

      <form onSubmit={add} style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="Add a todo..."
          maxLength={255}
          autoFocus
          style={{ flex: 1, padding: "0.4rem" }}
        />
        <button type="submit">Add</button>
      </form>

      <ul style={{ listStyle: "none", padding: 0 }}>
        {todos.length === 0 && <li style={{ color: "#999" }}>(no todos yet)</li>}
        {todos.map(t => (
          <li key={t.id} style={{
            display: "flex",
            justifyContent: "space-between",
            padding: "0.4rem 0",
            borderBottom: "1px solid #eee",
          }}>
            <span>{t.text}</span>
            <button onClick={() => remove(t.id)}>delete</button>
          </li>
        ))}
      </ul>
    </main>
  );
}
