import { useEffect, useState } from "react";

type ConnectionState = "checking" | "connected" | "disconnected";

type HealthResponse = {
  status: string;
  database: string;
};

export default function App() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function checkBackend() {
      try {
        const response = await fetch("/api/health");

        if (!response.ok) {
          throw new Error("Backend health check failed");
        }

        const data = (await response.json()) as HealthResponse;

        if (isMounted) {
          setHealth(data);
          setConnectionState("connected");
        }
      } catch {
        if (isMounted) {
          setHealth(null);
          setConnectionState("disconnected");
        }
      }
    }

    void checkBackend();

    return () => {
      isMounted = false;
    };
  }, []);

  const label =
    connectionState === "checking"
      ? "Checking backend"
      : connectionState === "connected"
        ? "Backend connected"
        : "Backend disconnected";

  return (
    <main className="app-shell">
      <section className="status-panel" aria-live="polite">
        <p className="eyebrow">Fantasy GM</p>
        <h1>Milestone 0</h1>
        <div className={`status-indicator ${connectionState}`}>
          <span aria-hidden="true" />
          <strong>{label}</strong>
        </div>
        {health ? (
          <p className="status-detail">Database: {health.database}</p>
        ) : (
          <p className="status-detail">Waiting for a healthy API response.</p>
        )}
      </section>
    </main>
  );
}
