import { useState } from "react";

import { LeagueSettingsPage } from "./features/league/LeagueSettingsPage";
import { PlayersPage } from "./features/players/PlayersPage";
import { ProjectionsPage } from "./features/projections/ProjectionsPage";

type Page = "players" | "league" | "projections";

export default function App() {
  const [page, setPage] = useState<Page>("players");

  return (
    <main className="app-shell">
      <section className="app-panel">
        <header className="page-header">
          <div>
            <p className="eyebrow">Fantasy GM</p>
            <h1>
              {page === "players"
                ? "Players"
                : page === "league"
                  ? "League Settings"
                  : "Projections"}
            </h1>
          </div>
          <nav className="app-nav" aria-label="Application navigation">
            <button
              className={page === "players" ? "active" : ""}
              onClick={() => setPage("players")}
              type="button"
            >
              Players
            </button>
            <button
              className={page === "league" ? "active" : ""}
              onClick={() => setPage("league")}
              type="button"
            >
              League Settings
            </button>
            <button
              className={page === "projections" ? "active" : ""}
              onClick={() => setPage("projections")}
              type="button"
            >
              Projections
            </button>
          </nav>
        </header>
        {page === "players" ? <PlayersPage /> : null}
        {page === "league" ? <LeagueSettingsPage /> : null}
        {page === "projections" ? <ProjectionsPage /> : null}
      </section>
    </main>
  );
}
