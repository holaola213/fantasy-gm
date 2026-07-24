import { useEffect, useState } from "react";

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

type ProjectionPlayer = {
  player_id: number;
  full_name: string;
  team: string | null;
  primary_position: string | null;
  games: number;
  minutes_per_game: number;
  fantasy_points_per_game: number;
  projected_fantasy_points: number;
};

type ProjectionPlayersResponse = {
  items: ProjectionPlayer[];
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

export function ProjectionsPage() {
  const [projectionSets, setProjectionSets] = useState<ProjectionSet[]>([]);
  const [selectedSetId, setSelectedSetId] = useState("");
  const [players, setPlayers] = useState<ProjectionPlayer[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [team, setTeam] = useState("");
  const [position, setPosition] = useState("");
  const [sort, setSort] = useState<ProjectionSort>("projected_fantasy_points");
  const [direction, setDirection] = useState<SortDirection>("desc");
  const [isLoadingSets, setIsLoadingSets] = useState(true);
  const [isLoadingPlayers, setIsLoadingPlayers] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function loadProjectionSets() {
      try {
        const response = await fetch("/api/projection-sets", {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Projection sets request failed");
        }

        const data = (await response.json()) as ProjectionSetsResponse;
        if (isMounted) {
          setProjectionSets(data.items);
          setSelectedSetId(data.items[0]?.id ? String(data.items[0].id) : "");
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

    void loadProjectionSets();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

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
      const params = new URLSearchParams({
        sort,
        direction,
      });
      if (search.trim()) {
        params.set("search", search.trim());
      }
      if (team.trim()) {
        params.set("team", team.trim());
      }
      if (position.trim()) {
        params.set("position", position.trim());
      }

      try {
        const response = await fetch(
          `/api/projection-sets/${selectedSetId}/players?${params.toString()}`,
          { signal: controller.signal },
        );

        if (response.status === 409) {
          throw new Error("league-required");
        }
        if (!response.ok) {
          throw new Error("Projection players request failed");
        }

        const data = (await response.json()) as ProjectionPlayersResponse;
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
          setErrorMessage(
            error instanceof Error && error.message === "league-required"
              ? "League configuration is required before projections can be scored."
              : "Unable to load projected players.",
          );
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
  }, [selectedSetId, search, team, position, sort, direction]);

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
        <p className="state-message">No projection sets are available.</p>
      ) : null}

      {projectionSets.length > 0 ? (
        <>
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
              <table>
                <thead>
                  <tr>
                    <SortableHeader
                      label="Player"
                      sortKey="player"
                      currentSort={sort}
                      direction={direction}
                      onSort={changeSort}
                    />
                    <SortableHeader
                      label="Team"
                      sortKey="team"
                      currentSort={sort}
                      direction={direction}
                      onSort={changeSort}
                    />
                    <SortableHeader
                      label="Position"
                      sortKey="position"
                      currentSort={sort}
                      direction={direction}
                      onSort={changeSort}
                    />
                    <SortableHeader
                      label="Games"
                      sortKey="games"
                      currentSort={sort}
                      direction={direction}
                      onSort={changeSort}
                    />
                    <SortableHeader
                      label="Minutes"
                      sortKey="minutes_per_game"
                      currentSort={sort}
                      direction={direction}
                      onSort={changeSort}
                    />
                    <SortableHeader
                      label="Fantasy PPG"
                      sortKey="fantasy_points_per_game"
                      currentSort={sort}
                      direction={direction}
                      onSort={changeSort}
                    />
                    <SortableHeader
                      label="Projected Total"
                      sortKey="projected_fantasy_points"
                      currentSort={sort}
                      direction={direction}
                      onSort={changeSort}
                    />
                  </tr>
                </thead>
                <tbody>
                  {players.map((player) => (
                    <tr key={player.player_id}>
                      <td>{player.full_name}</td>
                      <td>{player.team ?? "Unsigned"}</td>
                      <td>{player.primary_position ?? "Unknown"}</td>
                      <td>{formatNumber(player.games)}</td>
                      <td>{formatNumber(player.minutes_per_game)}</td>
                      <td>{formatNumber(player.fantasy_points_per_game)}</td>
                      <td>{formatNumber(player.projected_fantasy_points)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function SortableHeader({
  label,
  sortKey,
  currentSort,
  direction,
  onSort,
}: {
  label: string;
  sortKey: ProjectionSort;
  currentSort: ProjectionSort;
  direction: SortDirection;
  onSort: (sortKey: ProjectionSort) => void;
}) {
  const isActive = currentSort === sortKey;
  return (
    <th aria-sort={isActive ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button
        className="table-sort"
        onClick={() => onSort(sortKey)}
        type="button"
      >
        {label}
        {isActive ? ` (${direction})` : ""}
      </button>
    </th>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(value);
}
