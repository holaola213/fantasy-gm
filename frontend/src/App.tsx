import { useState } from "react";

import { BootstrapImportPanel } from "./features/bootstrap/BootstrapImportPanel";
import { DraftPage } from "./features/draft/DraftPage";
import { LeagueSettingsPage } from "./features/league/LeagueSettingsPage";
import { PlayersPage } from "./features/players/PlayersPage";
import { ProjectionsPage } from "./features/projections/ProjectionsPage";
import { ValuationsPage } from "./features/valuations/ValuationsPage";

type Page = "players" | "league" | "projections" | "valuations" | "draft";

export default function App() {
  const [page, setPage] = useState<Page>("players");
  const [dataRefreshKey, setDataRefreshKey] = useState(0);

  function refreshData() {
    setDataRefreshKey((current) => current + 1);
  }

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
                  : page === "projections"
                    ? "Projections"
                    : page === "valuations"
                      ? "Valuations"
                      : "Draft"}
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
            <button
              className={page === "valuations" ? "active" : ""}
              onClick={() => setPage("valuations")}
              type="button"
            >
              Valuations
            </button>
            <button
              className={page === "draft" ? "active" : ""}
              onClick={() => setPage("draft")}
              type="button"
            >
              Draft
            </button>
          </nav>
        </header>
        <BootstrapImportPanel
          refreshKey={dataRefreshKey}
          onImported={refreshData}
        />
        {page === "players" ? <PlayersPage refreshKey={dataRefreshKey} /> : null}
        {page === "league" ? <LeagueSettingsPage /> : null}
        {page === "projections" ? (
          <ProjectionsPage refreshKey={dataRefreshKey} />
        ) : null}
        {page === "valuations" ? <ValuationsPage /> : null}
        {page === "draft" ? (
          <DraftPage onCreateLeague={() => setPage("league")} />
        ) : null}
      </section>
    </main>
  );
}
