import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { newGame } from "../api/client";

export function NewGamePage() {
  const nav = useNavigate();
  const [pc, setPc] = useState(2);
  const [seed, setSeed] = useState<string>("");
  const [ai, setAi] = useState("basic");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function start() {
    setErr(null);
    setLoading(true);
    try {
      const s = seed.trim() === "" ? null : parseInt(seed, 10);
      if (s !== null && Number.isNaN(s)) {
        setErr("Seed must be a number");
        return;
      }
      const g = await newGame({
        player_count: pc,
        human_player_id: "P1",
        ai_strategy: ai,
        seed: s,
      });
      nav(`/play/${g.game_id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-label="Table setup console" className="game-surface page-console lobby-console">
      <header className="surface-hero">
        <p className="surface-hero__topline">Deal Breaker setup terminal</p>
        <h1 className="page-title">New Game</h1>
        <p className="surface-hero__copy">
          Configure a fresh local table, take seat <strong>P1</strong>, and open
          the neon play surface when the deal is ready.
        </p>
      </header>

      <div className="setup-grid">
        <section className="pixel-panel surface-panel">
          <p className="surface-kicker">Table parameters</p>
          <div className="form-stack">
            <label>
              Players{" "}
              <select
                value={pc}
                onChange={(e) => setPc(parseInt(e.target.value, 10))}
              >
                <option value={2}>2</option>
                <option value={3}>3</option>
                <option value={4}>4</option>
                <option value={5}>5</option>
              </select>
            </label>
            <label>
              AI{" "}
              <select value={ai} onChange={(e) => setAi(e.target.value)}>
                <option value="basic">basic</option>
                <option value="aggressive">aggressive</option>
                <option value="defensive">defensive</option>
                <option value="set_completion">set_completion</option>
                <option value="random">random</option>
              </select>
            </label>
            <label>
              Seed (optional){" "}
              <input
                className="seed-input"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                placeholder="e.g. 42"
              />
            </label>
            <button
              className="pixel-button"
              type="button"
              onClick={start}
              disabled={loading}
            >
              {loading ? "Starting…" : "Start & open table"}
            </button>
          </div>
          {err && <p className="error">{err}</p>}
        </section>

        <aside className="pixel-card setup-card">
          <p className="surface-kicker">Seat preview</p>
          <div className="setup-card__stats">
            <div className="setup-stat">
              <span>Human</span>
              <span>P1</span>
            </div>
            <div className="setup-stat">
              <span>Players</span>
              <span>{pc}</span>
            </div>
            <div className="setup-stat">
              <span>AI deck</span>
              <span>{ai}</span>
            </div>
            <div className="setup-stat">
              <span>Seed</span>
              <span>{seed.trim() || "random"}</span>
            </div>
          </div>
          <p className="muted">
            Use the play table to act when it is your turn and let AIs advance
            between human turns.
          </p>
        </aside>
      </div>
    </section>
  );
}
