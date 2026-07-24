import { useEffect, useMemo, useState } from "react";

type ConnectionState = "checking" | "connected" | "disconnected";

type Player = {
  id: number;
  full_name: string;
  team: string | null;
  primary_position: string | null;
  is_active: boolean;
};

type PlayerListResponse = {
  items: Player[];
  total: number;
  limit: number;
  offset: number;
};

export function PlayersPage() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("checking");
  const [players, setPlayers] = useState<Player[]>([]);
  const [initialPlayers, setInitialPlayers] = useState<Player[]>([]);
  const [initialTotal, setInitialTotal] = useState(0);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [team, setTeam] = useState("");
  const [position, setPosition] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasLoadedInitialPlayers, setHasLoadedInitialPlayers] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function loadInitialPlayers() {
      try {
        const response = await fetch("/api/players", {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Players request failed");
        }

        const data = (await response.json()) as PlayerListResponse;

        if (isMounted) {
          setPlayers(data.items);
          setInitialPlayers(data.items);
          setInitialTotal(data.total);
          setTotal(data.total);
          setConnectionState("connected");
          setErrorMessage(null);
          setHasLoadedInitialPlayers(true);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setPlayers([]);
          setInitialPlayers([]);
          setInitialTotal(0);
          setConnectionState("disconnected");
          setErrorMessage("Unable to load players from the backend.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadInitialPlayers();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!hasLoadedInitialPlayers) {
      return;
    }

    let isMounted = true;
    const controller = new AbortController();

    async function loadFilteredPlayers() {
      if (!search.trim() && !team && !position) {
        setPlayers(initialPlayers);
        setTotal(initialTotal);
        return;
      }

      setIsLoading(true);

      const params = new URLSearchParams();
      if (search.trim()) {
        params.set("search", search.trim());
      }
      if (team) {
        params.set("team", team);
      }
      if (position) {
        params.set("position", position);
      }

      try {
        const query = params.toString();
        const response = await fetch(`/api/players${query ? `?${query}` : ""}`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Players request failed");
        }

        const data = (await response.json()) as PlayerListResponse;

        if (isMounted) {
          setPlayers(data.items);
          setTotal(data.total);
          setConnectionState("connected");
          setErrorMessage(null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setPlayers([]);
          setConnectionState("disconnected");
          setErrorMessage("Unable to load players from the backend.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadFilteredPlayers();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [
    hasLoadedInitialPlayers,
    initialPlayers,
    initialTotal,
    search,
    team,
    position,
  ]);

  const teamOptions = useMemo(
    () =>
      Array.from(
        new Set(initialPlayers.map((player) => player.team).filter(Boolean)),
      ).sort() as string[],
    [initialPlayers],
  );

  const positionOptions = useMemo(
    () =>
      Array.from(
        new Set(
          initialPlayers
            .map((player) => player.primary_position)
            .filter(Boolean),
        ),
      ).sort() as string[],
    [initialPlayers],
  );

  const label =
    connectionState === "checking"
      ? "Checking backend"
      : connectionState === "connected"
        ? "Backend connected"
        : "Backend disconnected";

  return (
    <>
      <div className={`status-indicator ${connectionState}`}>
        <span aria-hidden="true" />
        <strong>{label}</strong>
      </div>

      <div className="filters" aria-label="Player filters">
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
          <select value={team} onChange={(event) => setTeam(event.target.value)}>
            <option value="">All teams</option>
            {teamOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Position
          <select
            value={position}
            onChange={(event) => setPosition(event.target.value)}
          >
            <option value="">All positions</option>
            {positionOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </div>

      {errorMessage ? <p className="state-message error">{errorMessage}</p> : null}
      {isLoading ? <p className="state-message">Loading players...</p> : null}
      {!isLoading && !errorMessage && players.length === 0 ? (
        <p className="state-message">No players match the current filters.</p>
      ) : null}

      {!isLoading && !errorMessage && players.length > 0 ? (
        <>
          <p className="result-count">{total} matching players</p>
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th>Team</th>
                <th>Position</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {players.map((player) => (
                <tr key={player.id}>
                  <td>{player.full_name}</td>
                  <td>{player.team ?? "Unsigned"}</td>
                  <td>{player.primary_position ?? "Unknown"}</td>
                  <td>{player.is_active ? "Active" : "Inactive"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </>
  );
}
