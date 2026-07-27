import { useEffect, useState } from "react";

import { ExplainedTerm } from "../../shared/ExplainedTerm";
import { helpText } from "../../shared/helpText";
import { useDebouncedValue } from "../../shared/useDebouncedValue";

type ProjectionSource = {
  id: number;
  key: string;
  name: string;
  description: string | null;
  is_active: boolean;
};

type ProjectionSet = {
  id: number;
  source_id: number;
  source: ProjectionSource;
  name: string;
  season: number;
  projection_type: "season";
  as_of_date: string;
  imported_at: string;
  is_active: boolean;
  notes: string | null;
};

type ProjectionSetsResponse = {
  items: ProjectionSet[];
};

type RawProjectionPlayer = {
  player_id: number;
  full_name: string;
  team: string | null;
  primary_position: string | null;
  games: number;
  minutes_per_game: number;
  fgm: number;
  fga: number;
  ftm: number;
  fta: number;
  rebounds: number;
  assists: number;
  steals: number;
  blocks: number;
  turnovers: number;
  points: number | null;
};

type ScoredProjectionPlayer = RawProjectionPlayer & {
  fantasy_points_per_game: number;
  projected_fantasy_points: number;
};

type ProjectionPlayersResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

type ProjectionSort =
  | "player"
  | "team"
  | "position"
  | "games"
  | "minutes_per_game"
  | "fantasy_points_per_game"
  | "projected_fantasy_points";

type SortDirection = "asc" | "desc";

export function ProjectionsPage({ refreshKey }: { refreshKey: number }) {
  const [projectionSets, setProjectionSets] = useState<ProjectionSet[]>([]);
  const [selectedSetId, setSelectedSetId] = useState("");
  const [players, setPlayers] = useState<RawProjectionPlayer[]>([]);
  const [total, setTotal] = useState(0);
  const [hasLeague, setHasLeague] = useState(false);
  const [search, setSearch] = useState("");
  const [team, setTeam] = useState("");
  const [position, setPosition] = useState("");
  const [sort, setSort] = useState<ProjectionSort>("projected_fantasy_points");
  const [direction, setDirection] = useState<SortDirection>("desc");
  const [isLoadingSets, setIsLoadingSets] = useState(true);
  const [isLoadingPlayers, setIsLoadingPlayers] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const debouncedSearch = useDebouncedValue(search, 300);
  const debouncedTeam = useDebouncedValue(team, 300);
  const debouncedPosition = useDebouncedValue(position, 300);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function loadProjectionContext() {
      setIsLoadingSets(true);
      try {
        const [setsResponse, leagueResponse] = await Promise.all([
          fetch("/api/projection-sets", { signal: controller.signal }),
          fetch("/api/league", { signal: controller.signal }),
        ]);

        if (!setsResponse.ok) {
          throw new Error("Projection sets request failed");
        }

        const data = (await setsResponse.json()) as ProjectionSetsResponse;
        if (isMounted) {
          setProjectionSets(data.items);
          setSelectedSetId(data.items[0]?.id ? String(data.items[0].id) : "");
          setHasLeague(leagueResponse.ok);
          setErrorMessage(null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setErrorMessage("Unable to load projection sets.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingSets(false);
        }
      }
    }

    void loadProjectionContext();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [refreshKey]);

  useEffect(() => {
    if (!selectedSetId) {
      setPlayers([]);
      setTotal(0);
      return;
    }

    let isMounted = true;
    const controller = new AbortController();

    async function loadProjectionPlayers() {
      setIsLoadingPlayers(true);
      const params = new URLSearchParams();
      if (hasLeague) {
        params.set("sort", sort);
        params.set("direction", direction);
      }
      if (debouncedSearch.trim()) {
        params.set("search", debouncedSearch.trim());
      }
      if (debouncedTeam.trim()) {
        params.set("team", debouncedTeam.trim());
      }
      if (debouncedPosition.trim()) {
        params.set("position", debouncedPosition.trim());
      }

      const path = hasLeague
        ? `/api/projection-sets/${selectedSetId}/players`
        : `/api/projection-sets/${selectedSetId}/raw-players`;

      try {
        const response = await fetch(`${path}?${params.toString()}`, {
          signal: controller.signal,
        });

        if (response.status === 409 && hasLeague) {
          setHasLeague(false);
          return;
        }
        if (!response.ok) {
          throw new Error("Projection players request failed");
        }

        const data = (await response.json()) as ProjectionPlayersResponse<
          RawProjectionPlayer | ScoredProjectionPlayer
        >;
        if (isMounted) {
          setPlayers(data.items);
          setTotal(data.total);
          setErrorMessage(null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setPlayers([]);
          setTotal(0);
          setErrorMessage("Unable to load projected players.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingPlayers(false);
        }
      }
    }

    void loadProjectionPlayers();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [
    selectedSetId,
    hasLeague,
    debouncedSearch,
    debouncedTeam,
    debouncedPosition,
    sort,
    direction,
  ]);

  const selectedSet = projectionSets.find(
    (projectionSet) => String(projectionSet.id) === selectedSetId,
  );

  function changeSort(nextSort: ProjectionSort) {
    if (sort === nextSort) {
      setDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSort(nextSort);
    setDirection(
      nextSort === "player" || nextSort === "team" || nextSort === "position"
        ? "asc"
        : "desc",
    );
  }

  if (isLoadingSets) {
    return <p className="state-message">Loading projection sets...</p>;
  }

  return (
    <div className="projections-page">
      {errorMessage ? <p className="state-message error">{errorMessage}</p> : null}
      {projectionSets.length === 0 ? (
        <p className="state-message">
          No projection data has been imported yet. Import bootstrap data to browse
          preseason projections.
        </p>
      ) : null}

      {projectionSets.length > 0 ? (
        <>
          {!hasLeague ? (
            <p className="state-message notice">
              League configuration is required to calculate fantasy points and
              valuations. Raw projections are available below.
            </p>
          ) : null}

          <div className="form-grid">
            <label>
              Projection Set
              <select
                value={selectedSetId}
                onChange={(event) => setSelectedSetId(event.target.value)}
              >
                {projectionSets.map((projectionSet) => (
                  <option key={projectionSet.id} value={projectionSet.id}>
                    {projectionSet.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Source
              <input value={selectedSet?.source.name ?? ""} readOnly />
            </label>
            <label>
              Season
              <input value={selectedSet?.season ?? ""} readOnly />
            </label>
            <label>
              As Of Date
              <input value={selectedSet?.as_of_date ?? ""} readOnly />
            </label>
          </div>

          <div className="filters" aria-label="Projection filters">
            <label>
              Search
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Player name"
              />
            </label>
            <label>
              Team
              <input
                value={team}
                onChange={(event) => setTeam(event.target.value)}
                placeholder="DEN"
              />
            </label>
            <label>
              Position
              <input
                value={position}
                onChange={(event) => setPosition(event.target.value)}
                placeholder="PG"
              />
            </label>
          </div>

          {isLoadingPlayers ? (
            <p className="state-message">Loading projected players...</p>
          ) : null}
          {!isLoadingPlayers && !errorMessage && players.length === 0 ? (
            <p className="state-message">
              No projected players match the current filters.
            </p>
          ) : null}
          {!isLoadingPlayers && !errorMessage && players.length > 0 ? (
            <>
              <p className="result-count">{total} matching projected players</p>
              {hasLeague ? (
                <ScoredProjectionTable
                  direction={direction}
                  players={players as ScoredProjectionPlayer[]}
                  sort={sort}
                  onSort={changeSort}
                />
              ) : (
                <RawProjectionTable players={players} />
              )}
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function RawProjectionTable({ players }: { players: RawProjectionPlayer[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Player</th>
          <th>Team</th>
          <th>Position</th>
          <th>
            <HeaderWithHelp label="Games" help={helpText.projectedGames} />
          </th>
          <th>
            <HeaderWithHelp label="Minutes" help={helpText.projectedMinutes} />
          </th>
          <th>FG</th>
          <th>FGA</th>
          <th>FT</th>
          <th>FTA</th>
          <th>REB</th>
          <th>AST</th>
          <th>STL</th>
          <th>BLK</th>
          <th>TOV</th>
          <th>PTS</th>
        </tr>
      </thead>
      <tbody>
        {players.map((player) => (
          <tr key={player.player_id}>
            <td>{player.full_name}</td>
            <td>{player.team ?? "Unknown"}</td>
            <td>{player.primary_position ?? "Unknown"}</td>
            <td>{formatNumber(player.games)}</td>
            <td>{formatNumber(player.minutes_per_game)}</td>
            <td>{formatNumber(player.fgm)}</td>
            <td>{formatNumber(player.fga)}</td>
            <td>{formatNumber(player.ftm)}</td>
            <td>{formatNumber(player.fta)}</td>
            <td>{formatNumber(player.rebounds)}</td>
            <td>{formatNumber(player.assists)}</td>
            <td>{formatNumber(player.steals)}</td>
            <td>{formatNumber(player.blocks)}</td>
            <td>{formatNumber(player.turnovers)}</td>
            <td>{formatNumber(player.points)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ScoredProjectionTable({
  direction,
  players,
  sort,
  onSort,
}: {
  direction: SortDirection;
  players: ScoredProjectionPlayer[];
  sort: ProjectionSort;
  onSort: (sortKey: ProjectionSort) => void;
}) {
  return (
    <table>
      <thead>
        <tr>
          <SortableHeader label="Player" sortKey="player" currentSort={sort} direction={direction} onSort={onSort} />
          <SortableHeader label="Team" sortKey="team" currentSort={sort} direction={direction} onSort={onSort} />
          <SortableHeader label="Position" sortKey="position" currentSort={sort} direction={direction} onSort={onSort} />
          <SortableHeader label="Games" help={helpText.projectedGames} sortKey="games" currentSort={sort} direction={direction} onSort={onSort} />
          <SortableHeader label="Minutes" help={helpText.projectedMinutes} sortKey="minutes_per_game" currentSort={sort} direction={direction} onSort={onSort} />
          <SortableHeader label="Fantasy PPG" help={helpText.fantasyPpg} sortKey="fantasy_points_per_game" currentSort={sort} direction={direction} onSort={onSort} />
          <SortableHeader label="Projected Total" help={helpText.projectedTotal} sortKey="projected_fantasy_points" currentSort={sort} direction={direction} onSort={onSort} />
        </tr>
      </thead>
      <tbody>
        {players.map((player) => (
          <tr key={player.player_id}>
            <td>{player.full_name}</td>
            <td>{player.team ?? "Unknown"}</td>
            <td>{player.primary_position ?? "Unknown"}</td>
            <td>{formatNumber(player.games)}</td>
            <td>{formatNumber(player.minutes_per_game)}</td>
            <td>{formatNumber(player.fantasy_points_per_game)}</td>
            <td>{formatNumber(player.projected_fantasy_points)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SortableHeader({
  label,
  help,
  sortKey,
  currentSort,
  direction,
  onSort,
}: {
  label: string;
  help?: string;
  sortKey: ProjectionSort;
  currentSort: ProjectionSort;
  direction: SortDirection;
  onSort: (sortKey: ProjectionSort) => void;
}) {
  const isActive = currentSort === sortKey;
  return (
    <th aria-sort={isActive ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      {help ? (
        <ExplainedTerm
          as="button"
          className="table-sort"
          onClick={() => onSort(sortKey)}
          text={help}
          type="button"
        >
          {label}
          {isActive ? ` (${direction})` : ""}
        </ExplainedTerm>
      ) : (
        <button
          className="table-sort"
          onClick={() => onSort(sortKey)}
          type="button"
        >
          {label}
          {isActive ? ` (${direction})` : ""}
        </button>
      )}
    </th>
  );
}

function HeaderWithHelp({ label, help }: { label: string; help: string }) {
  return (
    <span className="table-heading">
      <ExplainedTerm text={help}>{label}</ExplainedTerm>
    </span>
  );
}

function formatNumber(value: number | null) {
  if (value === null) {
    return "Unknown";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(value);
}
