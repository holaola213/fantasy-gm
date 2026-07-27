import { useEffect, useMemo, useState } from "react";

import { DraftAssistantPanel } from "./DraftAssistantPanel";
import type {
  AvailablePlayer,
  AvailablePlayerResponse,
  DraftAssistant,
  DraftBoard,
  DraftPick,
  DraftSession,
  DraftSort,
  FantasyTeam,
  LeagueResponse,
  SortDirection,
  TeamSetup,
} from "./types";

export function DraftPage({
  onCreateLeague,
}: {
  onCreateLeague: () => void;
}) {
  const [draft, setDraft] = useState<DraftSession | null>(null);
  const [board, setBoard] = useState<DraftBoard | null>(null);
  const [league, setLeague] = useState<LeagueResponse | null>(null);
  const [teams, setTeams] = useState<TeamSetup[]>([]);
  const [draftName, setDraftName] = useState("2026 League Draft");
  const [userDraftPosition, setUserDraftPosition] = useState(1);
  const [availablePlayers, setAvailablePlayers] = useState<AvailablePlayer[]>([]);
  const [assistant, setAssistant] = useState<DraftAssistant | null>(null);
  const [availableTotal, setAvailableTotal] = useState(0);
  const [availableErrorMessage, setAvailableErrorMessage] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [team, setTeam] = useState("");
  const [position, setPosition] = useState("");
  const [sort, setSort] = useState<DraftSort>("projected_fantasy_points");
  const [direction, setDirection] = useState<SortDirection>("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingAvailable, setIsLoadingAvailable] = useState(false);
  const [isLoadingAssistant, setIsLoadingAssistant] = useState(false);
  const [isRefreshingAssistant, setIsRefreshingAssistant] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [draftingPlayerId, setDraftingPlayerId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  useEffect(() => {
    void loadInitialState();
  }, []);

  useEffect(() => {
    if (!noticeMessage) {
      return;
    }
    const timeout = window.setTimeout(() => {
      setNoticeMessage(null);
    }, 3500);
    return () => window.clearTimeout(timeout);
  }, [noticeMessage]);

  useEffect(() => {
    if (!draft || draft.status === "setup") {
      setAvailablePlayers([]);
      setAvailableTotal(0);
      setAssistant(null);
      return;
    }

    let isMounted = true;
    const controller = new AbortController();

    async function loadAvailablePlayers() {
      setIsLoadingAvailable(true);
      const params = new URLSearchParams({ sort, direction });
      if (search.trim()) {
        params.set("search", search.trim());
      }
      if (team.trim()) {
        params.set("team", team.trim());
      }
      if (position) {
        params.set("position", position);
      }

      try {
        const response = await fetch(`/api/valuations?available_only=true&${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(await errorDetail(response));
        }
        const data = (await response.json()) as AvailablePlayerResponse;
        if (isMounted) {
          setAvailablePlayers(data.items);
          setAvailableTotal(data.total);
          setAvailableErrorMessage(null);
          setErrorMessage(null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setAvailablePlayers([]);
          setAvailableErrorMessage(
            error instanceof Error
              ? error.message
              : "Player values are temporarily unavailable."
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingAvailable(false);
        }
      }
    }

    void loadAvailablePlayers();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [draft, search, team, position, sort, direction]);

  useEffect(() => {
    if (!draft || draft.status !== "in_progress") {
      setAssistant(null);
      return;
    }

    let isMounted = true;
    const controller = new AbortController();
    const hasAssistant = assistant !== null;

    async function loadAssistant() {
      await refreshAssistant({
        clearOnFailure: !hasAssistant,
        isMounted: () => isMounted,
        mode: hasAssistant ? "refresh" : "initial",
        signal: controller.signal,
      });
    }

    void loadAssistant();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [draft]);

  const pickedByTeam = useMemo(() => {
    const grouped = new Map<number, DraftPick[]>();
    for (const pick of board?.picks ?? []) {
      grouped.set(pick.fantasy_team_id, [
        ...(grouped.get(pick.fantasy_team_id) ?? []),
        pick,
      ]);
    }
    return grouped;
  }, [board]);

  async function loadInitialState() {
    setIsLoading(true);
    setErrorMessage(null);
    await loadLeague();
    await loadDraft();
    setIsLoading(false);
  }

  async function loadLeague() {
    try {
      const response = await fetch("/api/league");
      if (!response.ok) {
        throw new Error("League request failed");
      }
      const data = (await response.json()) as LeagueResponse;
      setLeague(data);
      setDraftName(`${data.season} League Draft`);
      setTeams(defaultTeams(data.team_count));
      setUserDraftPosition(1);
    } catch {
      setLeague(null);
    }
  }

  async function loadDraft() {
    const response = await fetch("/api/draft");
    if (response.status === 404) {
      setDraft(null);
      setBoard(null);
      return;
    }
    if (!response.ok) {
      setErrorMessage("Unable to load draft.");
      return;
    }
    const data = (await response.json()) as DraftSession;
    setDraft(data);
    if (data.status === "setup") {
      await loadSetupTeams(data);
    }
    await loadBoard();
  }

  async function loadSetupTeams(currentDraft: DraftSession) {
    const response = await fetch("/api/draft/teams");
    if (!response.ok) {
      return;
    }
    const data = (await response.json()) as FantasyTeam[];
    setDraftName(currentDraft.name);
    setTeams(
      data
        .map((item) => ({
          name: item.name,
          draft_position: item.draft_position,
        }))
        .sort((left, right) => left.draft_position - right.draft_position),
    );
    setUserDraftPosition(
      data.find((item) => item.is_user_team)?.draft_position ?? 1,
    );
  }

  async function loadBoard() {
    const data = await loadBoardData();
    if (!data) {
      return;
    }
    setBoard(data);
    setDraft(data.draft);
  }

  async function loadBoardData() {
    const response = await fetch("/api/draft/board");
    if (!response.ok) {
      return null;
    }
    const data = (await response.json()) as DraftBoard;
    return data;
  }

  async function refreshAssistant({
    clearOnFailure,
    isMounted,
    mode,
    signal,
  }: {
    clearOnFailure: boolean;
    isMounted: () => boolean;
    mode: "initial" | "refresh";
    signal?: AbortSignal;
  }) {
    if (mode === "refresh") {
      setIsRefreshingAssistant(true);
    } else {
      setIsLoadingAssistant(true);
    }
    try {
      const response = await fetch("/api/draft/assistant", { signal });
      if (!response.ok) {
        throw new Error(await errorDetail(response));
      }
      const data = (await response.json()) as DraftAssistant;
      if (isMounted()) {
        setAssistant(data);
        setErrorMessage(null);
      }
      return data;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return null;
      }
      if (isMounted()) {
        if (clearOnFailure) {
          setAssistant(null);
        }
        setErrorMessage(assistantErrorMessage(error));
      }
      return null;
    } finally {
      if (isMounted()) {
        setIsLoadingAssistant(false);
        setIsRefreshingAssistant(false);
      }
    }
  }

  function updateTeamName(index: number, value: string) {
    setTeams((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index ? { ...item, name: value } : item,
      ),
    );
    setNoticeMessage(null);
  }

  function validateSetup() {
    if (!draftName.trim()) {
      return "Draft name is required.";
    }
    if (teams.some((item) => !item.name.trim())) {
      return "Every team needs a name.";
    }
    return null;
  }

  async function saveSetup(method: "POST" | "PUT") {
    const validation = validateSetup();
    if (validation) {
      setErrorMessage(validation);
      return;
    }
    setIsSaving(true);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const response = await fetch(
        method === "POST" ? "/api/draft" : "/api/draft/setup",
        {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: draftName,
            teams,
            user_draft_position: userDraftPosition,
          }),
        },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Draft setup request failed");
      }
      const data = (await response.json()) as DraftSession;
      setDraft(data);
      await loadBoard();
      setNoticeMessage(method === "POST" ? "Draft created." : "Draft setup saved.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to save draft setup.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function startDraft() {
    setIsSaving(true);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const response = await fetch("/api/draft/start", { method: "POST" });
      if (!response.ok) {
        throw new Error("Unable to start draft.");
      }
      const data = (await response.json()) as DraftSession;
      setDraft(data);
      await loadBoard();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to start draft.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function draftPlayer(playerId: number) {
    if (isSaving || draftingPlayerId !== null) {
      return;
    }
    const playerName = findDraftablePlayerName(playerId);
    setIsSaving(true);
    setDraftingPlayerId(playerId);
    setErrorMessage(null);
    try {
      const response = await fetch("/api/draft/picks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_id: playerId }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Unable to draft player.");
      }
      const nextBoard = await loadBoardData();
      const nextAssistant = await refreshAssistant({
        clearOnFailure: false,
        isMounted: () => true,
        mode: assistant ? "refresh" : "initial",
      });
      if (nextBoard) {
        setBoard(nextBoard);
        setDraft(nextBoard.draft);
      }
      if (!nextAssistant && !nextBoard) {
        throw new Error("Unable to refresh draft.");
      }
      setNoticeMessage(`${playerName} drafted.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to draft player.");
    } finally {
      setIsSaving(false);
      setDraftingPlayerId(null);
    }
  }

  async function undoLatestPick() {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const response = await fetch("/api/draft/picks/latest", { method: "DELETE" });
      if (!response.ok) {
        throw new Error("Unable to undo latest pick.");
      }
      await loadBoard();
      setNoticeMessage("Latest pick removed.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to undo latest pick.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function resetDraft() {
    const confirmed = window.confirm(
      "Reset the entire draft?\n\nAll drafted players will be removed and the draft will return to setup.",
    );
    if (!confirmed) {
      return;
    }
    setIsSaving(true);
    setErrorMessage(null);
    setNoticeMessage(null);
    setAssistant(null);
    setAvailablePlayers([]);
    setAvailableTotal(0);
    try {
      const response = await fetch("/api/draft/reset", { method: "POST" });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Unable to reset draft.");
      }
      const data = (await response.json()) as DraftSession;
      setDraft(data);
      await loadSetupTeams(data);
      await loadBoard();
      setNoticeMessage("Draft reset. All recorded picks were removed.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to reset draft.");
    } finally {
      setIsSaving(false);
    }
  }

  function findDraftablePlayerName(playerId: number) {
    const recommendation = assistant?.recommendations.find(
      (item) => item.player_id === playerId,
    );
    if (recommendation) {
      return recommendation.player_name;
    }
    const assistantPlayer = [
      ...(assistant?.best_available ?? []),
      ...(assistant?.roster_fit_options ?? []),
      ...(assistant?.best_by_position.flatMap((section) => section.items) ?? []),
    ].find((item) => item.player_id === playerId);
    if (assistantPlayer) {
      return assistantPlayer.player_name;
    }
    return (
      availablePlayers.find((player) => player.player_id === playerId)?.player_name ??
      "Player"
    );
  }

  async function deleteDraft() {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const response = await fetch("/api/draft", { method: "DELETE" });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Unable to delete draft.");
      }
      setDraft(null);
      setBoard(null);
      setNoticeMessage("Draft deleted.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to delete draft.");
    } finally {
      setIsSaving(false);
    }
  }

  function changeSort(nextSort: DraftSort) {
    if (sort === nextSort) {
      setDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSort(nextSort);
    setDirection(
      nextSort === "player" ||
        nextSort === "team" ||
        nextSort === "position" ||
        nextSort === "overall_rank"
        ? "asc"
        : "desc",
    );
  }

  if (isLoading) {
    return <p className="state-message">Loading draft...</p>;
  }

  if (!league && !draft) {
    return (
      <section className="onboarding-panel" aria-labelledby="draft-onboarding-heading">
        <div>
          <h2 id="draft-onboarding-heading">Draft Assistant</h2>
          <p>Before creating a draft you'll need a league configuration.</p>
          <p>League settings determine:</p>
          <ul>
            <li>scoring rules</li>
            <li>roster construction</li>
            <li>replacement levels</li>
            <li>draft recommendations</li>
          </ul>
        </div>
        <button onClick={onCreateLeague} type="button">
          Create League
        </button>
      </section>
    );
  }

  return (
    <div className="draft-page">
      {errorMessage ? <p className="state-message error">{errorMessage}</p> : null}
      {noticeMessage ? (
        <p className="draft-toast success" role="status">
          {noticeMessage}
        </p>
      ) : null}

      {!draft ? (
        <DraftSetupForm
          draftName={draftName}
          isSaving={isSaving}
          teams={teams}
          userDraftPosition={userDraftPosition}
          onDraftNameChange={setDraftName}
          onTeamNameChange={updateTeamName}
          onUserDraftPositionChange={setUserDraftPosition}
          onSave={() => void saveSetup("POST")}
        />
      ) : null}

      {draft?.status === "setup" ? (
        <>
          <DraftSummary
            availableTotal={availableTotal}
            isAvailableUnavailable={false}
            board={board}
            draft={draft}
            setupTeamName={
              teams.find((item) => item.draft_position === userDraftPosition)?.name
            }
          />
          <DraftSetupForm
            draftName={draftName}
            isSaving={isSaving}
            teams={teams}
            userDraftPosition={userDraftPosition}
            onDraftNameChange={setDraftName}
            onTeamNameChange={updateTeamName}
            onUserDraftPositionChange={setUserDraftPosition}
            onSave={() => void saveSetup("PUT")}
          />
          <div className="actions split-actions">
            <button disabled={isSaving} onClick={() => void deleteDraft()} type="button">
              Delete Draft
            </button>
            <button disabled={isSaving} onClick={() => void resetDraft()} type="button">
              Reset Draft
            </button>
            <button disabled={isSaving} onClick={() => void startDraft()} type="button">
              Start Draft
            </button>
          </div>
        </>
      ) : null}

      {draft && draft.status !== "setup" && board ? (
        <>
          <DraftSummary
            availableTotal={availableTotal}
            isAvailableUnavailable={Boolean(availableErrorMessage)}
            board={board}
            draft={draft}
          />
          {draft.status === "completed" ? (
            <p className="state-message success">Draft completed.</p>
          ) : null}
          <div className="board-layout">
            <section>
              {draft.status === "in_progress" ? (
                <>
                  <DraftAssistantPanel
                    assistant={assistant}
                    isLoading={isLoadingAssistant}
                    isRefreshing={isRefreshingAssistant}
                    isSaving={isSaving}
                    draftingPlayerId={draftingPlayerId}
                    onDraftPlayer={(playerId) => void draftPlayer(playerId)}
                  />
                  <AvailablePlayersTable
                    direction={direction}
                    errorMessage={availableErrorMessage}
                    isLoading={isLoadingAvailable}
                    isSaving={isSaving}
                    draftingPlayerId={draftingPlayerId}
                    players={availablePlayers}
                    position={position}
                    search={search}
                    sort={sort}
                    team={team}
                    total={availableTotal}
                    onDraftPlayer={(playerId) => void draftPlayer(playerId)}
                    onPositionChange={setPosition}
                    onSearchChange={setSearch}
                    onSort={changeSort}
                    onTeamChange={setTeam}
                  />
                </>
              ) : null}
              <DraftPicksTable picks={board.picks} />
            </section>
            <aside className="team-rosters">
              <div className="section-header">
                <h2>Teams</h2>
                <div className="draft-control-actions">
                  <button
                    disabled={isSaving || board.picks.length === 0}
                    onClick={() => void undoLatestPick()}
                    type="button"
                  >
                    Undo Latest Pick
                  </button>
                  <button disabled={isSaving} onClick={() => void resetDraft()} type="button">
                    Reset Draft
                  </button>
                </div>
              </div>
              {board.teams.map((item) => (
                <section className="team-roster" key={item.id}>
                  <h3>
                    {item.draft_position}. {item.name}
                    {item.is_user_team ? " (You)" : ""}
                  </h3>
                  <ul>
                    {(pickedByTeam.get(item.id) ?? []).map((pick) => (
                      <li key={pick.id}>
                        {pick.overall_pick}. {pick.player_name}
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </aside>
          </div>
        </>
      ) : null}
    </div>
  );
}

function DraftSetupForm({
  draftName,
  isSaving,
  teams,
  userDraftPosition,
  onDraftNameChange,
  onTeamNameChange,
  onUserDraftPositionChange,
  onSave,
}: {
  draftName: string;
  isSaving: boolean;
  teams: TeamSetup[];
  userDraftPosition: number;
  onDraftNameChange: (value: string) => void;
  onTeamNameChange: (index: number, value: string) => void;
  onUserDraftPositionChange: (value: number) => void;
  onSave: () => void;
}) {
  return (
    <section className="editor-section">
      <div className="form-grid">
        <label>
          Draft Name
          <input
            value={draftName}
            onChange={(event) => onDraftNameChange(event.target.value)}
          />
        </label>
        <label>
          Your Draft Position
          <select
            value={userDraftPosition}
            onChange={(event) => onUserDraftPositionChange(Number(event.target.value))}
          >
            {teams.map((team) => (
              <option key={team.draft_position} value={team.draft_position}>
                {team.draft_position}
              </option>
            ))}
          </select>
        </label>
      </div>
      <table>
        <thead>
          <tr>
            <th>Draft Position</th>
            <th>Team Name</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team, index) => (
            <tr key={team.draft_position}>
              <td>{team.draft_position}</td>
              <td>
                <input
                  value={team.name}
                  onChange={(event) => onTeamNameChange(index, event.target.value)}
                  aria-label={`Team ${team.draft_position} name`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="actions">
        <button disabled={isSaving} onClick={onSave} type="button">
          {isSaving ? "Saving..." : "Save Draft Setup"}
        </button>
      </div>
    </section>
  );
}

function DraftSummary({
  availableTotal,
  isAvailableUnavailable,
  board,
  draft,
  setupTeamName,
}: {
  availableTotal: number;
  isAvailableUnavailable: boolean;
  board: DraftBoard | null;
  draft: DraftSession;
  setupTeamName?: string;
}) {
  const totalPicks = draft.team_count * draft.rounds;
  const playersDrafted = board?.picks.length ?? 0;
  const userTeam = board?.teams.find((team) => team.is_user_team)?.name ?? setupTeamName;
  const playersRemaining =
    draft.status === "in_progress"
      ? availableTotal
      : Math.max(totalPicks - playersDrafted, 0);

  return (
    <section className="summary-panel" aria-labelledby="draft-status-heading">
      <h2 id="draft-status-heading">Draft Status</h2>
      <div className="summary-grid">
        <div>
          <span>Status</span>
          <strong>{draft.status.replace("_", " ")}</strong>
        </div>
        <div>
          <span>Round</span>
          <strong>
            {draft.current_round ?? draft.rounds} / {draft.rounds}
          </strong>
        </div>
        <div>
          <span>Overall Pick</span>
          <strong>
            {draft.current_pick_number ?? totalPicks} / {totalPicks}
          </strong>
        </div>
        {draft.status === "in_progress" ? (
          <div>
            <span>On the Clock</span>
            <strong>{board?.on_clock_team?.name ?? "None"}</strong>
          </div>
        ) : null}
        <div>
          <span>Your Team</span>
          <strong>{userTeam?.trim() || "Not selected"}</strong>
        </div>
        {draft.status === "setup" ? (
          <div>
            <span>Teams</span>
            <strong>{draft.team_count}</strong>
          </div>
        ) : null}
        <div>
          <span>Players Drafted</span>
          <strong>{playersDrafted}</strong>
        </div>
        <div>
          <span>Players Remaining</span>
          <strong>{isAvailableUnavailable ? "Unavailable" : playersRemaining}</strong>
        </div>
      </div>
    </section>
  );
}

function AvailablePlayersTable({
  direction,
  draftingPlayerId,
  errorMessage,
  isLoading,
  isSaving,
  players,
  position,
  search,
  sort,
  team,
  total,
  onDraftPlayer,
  onPositionChange,
  onSearchChange,
  onSort,
  onTeamChange,
}: {
  direction: SortDirection;
  draftingPlayerId: number | null;
  errorMessage: string | null;
  isLoading: boolean;
  isSaving: boolean;
  players: AvailablePlayer[];
  position: string;
  search: string;
  sort: DraftSort;
  team: string;
  total: number;
  onDraftPlayer: (playerId: number) => void;
  onPositionChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onSort: (sort: DraftSort) => void;
  onTeamChange: (value: string) => void;
}) {
  return (
    <section className="editor-section">
      <div className="section-header">
        <h2>Available Player Values</h2>
      </div>
      <div className="filters" aria-label="Draft player filters">
        <label>
          Search
          <input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Player name"
          />
        </label>
        <label>
          Team
          <input
            value={team}
            onChange={(event) => onTeamChange(event.target.value)}
            placeholder="Team abbreviation"
          />
        </label>
        <label>
          Position
          <select value={position} onChange={(event) => onPositionChange(event.target.value)}>
            <option value="">All positions</option>
            {["PG", "SG", "SF", "PF", "C"].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      </div>
      {isLoading ? <p className="state-message">Loading available players...</p> : null}
      {!isLoading && errorMessage ? (
        <p className="state-message error">{errorMessage}</p>
      ) : null}
      {!isLoading && !errorMessage && players.length === 0 ? (
        <p className="state-message">No available players match the current filters.</p>
      ) : null}
      {!isLoading && !errorMessage && players.length > 0 ? (
        <>
          <p className="result-count">{total} available players</p>
          <table>
            <thead>
              <tr>
                <SortableHeader label="Player" sortKey="player" currentSort={sort} direction={direction} onSort={onSort} />
                <SortableHeader label="Team" sortKey="team" currentSort={sort} direction={direction} onSort={onSort} />
                <SortableHeader label="Position" sortKey="position" currentSort={sort} direction={direction} onSort={onSort} />
                <th>Eligible</th>
                <th>Slots</th>
                <SortableHeader label="Overall Rank" sortKey="overall_rank" currentSort={sort} direction={direction} onSort={onSort} />
                <SortableHeader label="Fantasy PPG" sortKey="fantasy_points_per_game" currentSort={sort} direction={direction} onSort={onSort} />
                <SortableHeader label="Projected Total" sortKey="projected_fantasy_points" currentSort={sort} direction={direction} onSort={onSort} />
                <SortableHeader label="Overall VOR" sortKey="overall_vor" currentSort={sort} direction={direction} onSort={onSort} />
                <th>Value Position</th>
                <th>Pick</th>
              </tr>
            </thead>
            <tbody>
              {players.map((player) => (
                <tr key={player.player_id}>
                  <td>{player.player_name}</td>
                  <td>{player.team ?? "Unsigned"}</td>
                  <td>{player.primary_position ?? "Unknown"}</td>
                  <td>{player.eligible_positions.join(", ") || "None"}</td>
                  <td>{player.compatible_roster_slots.join(", ") || "None"}</td>
                  <td>{player.overall_rank ?? "None"}</td>
                  <td>{formatNumber(player.fantasy_points_per_game)}</td>
                  <td>{formatNumber(player.projected_fantasy_points)}</td>
                  <td>{formatNumber(player.overall_vor)}</td>
                  <td>{player.best_value_position ?? "None"}</td>
                  <td>
                    <button
                      disabled={isSaving}
                      onClick={() => onDraftPlayer(player.player_id)}
                      type="button"
                    >
                      {draftingPlayerId === player.player_id ? "Drafting..." : "Draft"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}

function DraftPicksTable({ picks }: { picks: DraftPick[] }) {
  return (
    <section className="editor-section">
      <div className="section-header">
        <h2>Draft Board</h2>
      </div>
      {picks.length === 0 ? (
        <p className="state-message">No picks have been recorded.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Pick</th>
              <th>Team</th>
              <th>Player</th>
              <th>NBA Team</th>
              <th>Eligibility</th>
            </tr>
          </thead>
          <tbody>
            {picks.map((pick) => (
              <tr key={pick.id}>
                <td>{pick.overall_pick}</td>
                <td>{pick.fantasy_team_name}</td>
                <td>{pick.player_name}</td>
                <td>{pick.team ?? "Unsigned"}</td>
                <td>{pick.eligible_positions.join(", ") || "None"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
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
  sortKey: DraftSort;
  currentSort: DraftSort;
  direction: SortDirection;
  onSort: (sort: DraftSort) => void;
}) {
  const isActive = currentSort === sortKey;
  return (
    <th aria-sort={isActive ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button className="table-sort" onClick={() => onSort(sortKey)} type="button">
        {label}
        {isActive ? ` (${direction})` : ""}
      </button>
    </th>
  );
}

function defaultTeams(teamCount: number): TeamSetup[] {
  return Array.from({ length: teamCount }, (_, index) => ({
    name: `Team ${index + 1}`,
    draft_position: index + 1,
  }));
}

async function errorDetail(response: Response) {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string") {
      return data.detail;
    }
  } catch {
    // Fall through to a stable generic message.
  }
  return "Request failed.";
}

function assistantErrorMessage(error: unknown) {
  if (!(error instanceof Error)) {
    return "Draft assistant is temporarily unavailable.";
  }
  if (error.message === "insufficient eligible player pool") {
    return (
      "The active projection set does not contain enough player position "
      + "eligibility for draft recommendations."
    );
  }
  return error.message;
}

function formatNumber(value: string | null) {
  if (value === null) {
    return "None";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(Number(value));
}
