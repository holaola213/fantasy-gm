import { useEffect, useMemo, useState } from "react";

type DraftStatus = "setup" | "in_progress" | "completed";
type SortDirection = "asc" | "desc";
type DraftSort =
  | "player"
  | "team"
  | "position"
  | "fantasy_points_per_game"
  | "projected_fantasy_points"
  | "overall_vor"
  | "overall_rank";

type LeagueResponse = {
  name: string;
  season: number;
  team_count: number;
};

type DraftSession = {
  id: number;
  league_id: number;
  projection_set_id: number;
  name: string;
  season: number;
  draft_type: "snake";
  status: DraftStatus;
  team_count: number;
  rounds: number;
  current_pick_number: number | null;
  current_round: number | null;
  current_pick_in_round: number | null;
};

type FantasyTeam = {
  id: number;
  draft_session_id: number;
  name: string;
  draft_position: number;
  is_user_team: boolean;
};

type DraftPick = {
  id: number;
  fantasy_team_id: number;
  player_id: number;
  player_name: string;
  team: string | null;
  primary_position: string | null;
  eligible_positions: string[];
  compatible_roster_slots: string[];
  fantasy_team_name: string;
  round_number: number;
  pick_in_round: number;
  overall_pick: number;
};

type DraftBoard = {
  draft: DraftSession;
  on_clock_team: FantasyTeam | null;
  teams: FantasyTeam[];
  picks: DraftPick[];
  recent_picks: DraftPick[];
};

type AvailablePlayer = {
  player_id: number;
  player_name: string;
  team: string | null;
  primary_position: string | null;
  eligible_positions: string[];
  compatible_roster_slots: string[];
  fantasy_points_per_game: string;
  projected_fantasy_points: string;
  overall_vor: string | null;
  best_value_position: string | null;
  overall_rank: number | null;
};

type AvailablePlayerResponse = {
  items: AvailablePlayer[];
  total: number;
  limit: number;
  offset: number;
};

type SlotInstance = {
  slot: string;
  slot_index: number;
};

type AssistantReason = {
  code:
    | "BEST_AVAILABLE"
    | "BEST_AT_POSITION"
    | "FILLS_OPEN_SLOT"
    | "FILLS_RESTRICTIVE_SLOT"
    | "MULTI_SLOT_FLEXIBILITY";
  position: string | null;
  slots: SlotInstance[];
};

type AssistantPlayer = {
  player_id: number;
  player_name: string;
  team: string | null;
  primary_position: string | null;
  eligible_positions: string[];
  overall_rank: number | null;
  overall_vor: string | null;
  best_value_position: string | null;
  fantasy_points_per_game: string;
  projected_fantasy_points: string;
  position: string | null;
  position_rank: number | null;
  position_vor: string | null;
  matching_open_slots: SlotInstance[];
  reasons: AssistantReason[];
};

type RosterSummary = {
  active_slots_total: number;
  active_slots_filled: number;
  active_slots_unfilled: number;
  bench_slots_total: number;
  bench_slots_filled: number;
  bench_slots_remaining: number;
  draftable_roster_capacity: number;
  players_drafted: number;
  roster_spots_remaining: number;
  assignments: {
    draft_pick_id: number;
    player_id: number;
    player_name: string;
    eligible_positions: string[];
    assigned_slot: string;
    slot_index: number;
    projected_fantasy_points: string | null;
  }[];
  bench_assignments: {
    draft_pick_id: number;
    player_id: number;
    player_name: string;
    eligible_positions: string[];
    bench_index: number;
    projected_fantasy_points: string | null;
  }[];
  unfilled_slots: SlotInstance[];
  unassigned_players: {
    draft_pick_id: number;
    player_id: number;
    player_name: string;
    eligible_positions: string[];
    reason: string;
    projected_fantasy_points: string | null;
  }[];
};

type DraftAssistant = {
  draft_id: number;
  status: "in_progress";
  current_round: number;
  current_overall_pick: number;
  on_clock_team: {
    fantasy_team_id: number;
    name: string;
    draft_position: number;
  } | null;
  is_user_on_clock: boolean;
  user_team: {
    fantasy_team_id: number;
    name: string;
    draft_position: number;
    players_drafted: number;
    roster_spots_remaining: number;
  };
  roster_summary: RosterSummary;
  best_available: AssistantPlayer[];
  best_by_position: {
    position: string;
    items: AssistantPlayer[];
  }[];
  roster_fit_options: AssistantPlayer[];
};

type TeamSetup = {
  name: string;
  draft_position: number;
};

export function DraftPage() {
  const [draft, setDraft] = useState<DraftSession | null>(null);
  const [board, setBoard] = useState<DraftBoard | null>(null);
  const [league, setLeague] = useState<LeagueResponse | null>(null);
  const [teams, setTeams] = useState<TeamSetup[]>([]);
  const [draftName, setDraftName] = useState("2026 League Draft");
  const [userDraftPosition, setUserDraftPosition] = useState(1);
  const [availablePlayers, setAvailablePlayers] = useState<AvailablePlayer[]>([]);
  const [assistant, setAssistant] = useState<DraftAssistant | null>(null);
  const [availableTotal, setAvailableTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [team, setTeam] = useState("");
  const [position, setPosition] = useState("");
  const [sort, setSort] = useState<DraftSort>("projected_fantasy_points");
  const [direction, setDirection] = useState<SortDirection>("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingAvailable, setIsLoadingAvailable] = useState(false);
  const [isLoadingAssistant, setIsLoadingAssistant] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  useEffect(() => {
    void loadInitialState();
  }, []);

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
          throw new Error("Available players request failed");
        }
        const data = (await response.json()) as AvailablePlayerResponse;
        if (isMounted) {
          setAvailablePlayers(data.items);
          setAvailableTotal(data.total);
          setErrorMessage(null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setAvailablePlayers([]);
          setAvailableTotal(0);
          setErrorMessage("Unable to load available players.");
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

    async function loadAssistant() {
      setIsLoadingAssistant(true);
      try {
        const response = await fetch("/api/draft/assistant", {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Draft assistant request failed");
        }
        const data = (await response.json()) as DraftAssistant;
        if (isMounted) {
          setAssistant(data);
          setErrorMessage(null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setAssistant(null);
          setErrorMessage("Unable to load draft assistant.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingAssistant(false);
        }
      }
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
    const response = await fetch("/api/draft/board");
    if (!response.ok) {
      return;
    }
    const data = (await response.json()) as DraftBoard;
    setBoard(data);
    setDraft(data.draft);
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
    setIsSaving(true);
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
      await loadBoard();
      setNoticeMessage("Pick recorded.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to draft player.");
    } finally {
      setIsSaving(false);
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
      <p className="state-message error">
        League configuration is required before creating a draft.
      </p>
    );
  }

  return (
    <div className="draft-page">
      {errorMessage ? <p className="state-message error">{errorMessage}</p> : null}
      {noticeMessage ? <p className="state-message success">{noticeMessage}</p> : null}

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
                    isSaving={isSaving}
                    onDraftPlayer={(playerId) => void draftPlayer(playerId)}
                  />
                  <AvailablePlayersTable
                    direction={direction}
                    isLoading={isLoadingAvailable}
                    isSaving={isSaving}
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
                <button
                  disabled={isSaving || board.picks.length === 0}
                  onClick={() => void undoLatestPick()}
                  type="button"
                >
                  Undo Latest Pick
                </button>
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

function DraftAssistantPanel({
  assistant,
  isLoading,
  isSaving,
  onDraftPlayer,
}: {
  assistant: DraftAssistant | null;
  isLoading: boolean;
  isSaving: boolean;
  onDraftPlayer: (playerId: number) => void;
}) {
  if (isLoading) {
    return <p className="state-message">Loading draft assistant...</p>;
  }
  if (!assistant) {
    return null;
  }
  return (
    <section className="assistant-panel" aria-labelledby="draft-assistant-heading">
      <div className="section-header">
        <h2 id="draft-assistant-heading">Draft Assistant</h2>
      </div>
      <div className="summary-grid">
        <div>
          <span>Current Pick</span>
          <strong>
            Round {assistant.current_round}, Pick {assistant.current_overall_pick}
          </strong>
        </div>
        <div>
          <span>On the Clock</span>
          <strong>{assistant.on_clock_team?.name ?? "None"}</strong>
        </div>
        <div>
          <span>Your Turn</span>
          <strong>{assistant.is_user_on_clock ? "Yes" : "No"}</strong>
        </div>
        <div>
          <span>Roster Spots</span>
          <strong>{assistant.user_team.roster_spots_remaining}</strong>
        </div>
      </div>

      <div className="assistant-roster">
        <div>
          <h3>Your Roster</h3>
          <p>
            Active {assistant.roster_summary.active_slots_filled} /{" "}
            {assistant.roster_summary.active_slots_total}, Bench{" "}
            {assistant.roster_summary.bench_slots_filled} /{" "}
            {assistant.roster_summary.bench_slots_total}
          </p>
          <p>
            Open active slots:{" "}
            {formatSlots(assistant.roster_summary.unfilled_slots) || "None"}
          </p>
          {assistant.roster_summary.assignments.length > 0 ? (
            <ul>
              {assistant.roster_summary.assignments.map((assignment) => (
                <li key={assignment.draft_pick_id}>
                  {formatSlot({
                    slot: assignment.assigned_slot,
                    slot_index: assignment.slot_index,
                  })}
                  : {assignment.player_name}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        {assistant.roster_summary.unassigned_players.length > 0 ? (
          <div>
            <h3>Unassigned</h3>
            <ul>
              {assistant.roster_summary.unassigned_players.map((player) => (
                <li key={player.draft_pick_id}>
                  {player.player_name}: {player.reason}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <AssistantOptionSection
        title="Best Available"
        players={assistant.best_available}
        isSaving={isSaving}
        onDraftPlayer={onDraftPlayer}
      />
      <AssistantOptionSection
        title="Roster Fits"
        players={assistant.roster_fit_options}
        isSaving={isSaving}
        onDraftPlayer={onDraftPlayer}
      />
      <div className="assistant-positions">
        {assistant.best_by_position.map((section) => (
          <AssistantOptionSection
            key={section.position}
            title={`${section.position} Options`}
            players={section.items}
            isSaving={isSaving}
            onDraftPlayer={onDraftPlayer}
          />
        ))}
      </div>
    </section>
  );
}

function AssistantOptionSection({
  title,
  players,
  isSaving,
  onDraftPlayer,
}: {
  title: string;
  players: AssistantPlayer[];
  isSaving: boolean;
  onDraftPlayer: (playerId: number) => void;
}) {
  return (
    <section className="assistant-section">
      <h3>{title}</h3>
      {players.length === 0 ? (
        <p className="state-message">No options in this section.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Player</th>
              <th>Team</th>
              <th>Eligibility</th>
              <th>Rank</th>
              <th>Overall VOR</th>
              <th>Projected Total</th>
              <th>Reasons</th>
              <th>Pick</th>
            </tr>
          </thead>
          <tbody>
            {players.map((player) => (
              <tr key={`${title}-${player.player_id}-${player.position ?? "overall"}`}>
                <td>{player.player_name}</td>
                <td>{player.team ?? "Unsigned"}</td>
                <td>{player.eligible_positions.join(", ") || "None"}</td>
                <td>{player.position_rank ?? player.overall_rank ?? "None"}</td>
                <td>{formatNumber(player.position_vor ?? player.overall_vor)}</td>
                <td>{formatNumber(player.projected_fantasy_points)}</td>
                <td>
                  <div className="reason-list">
                    {player.reasons.map((reason, index) => (
                      <span className="reason-pill" key={`${reason.code}-${index}`}>
                        {formatReason(reason)}
                      </span>
                    ))}
                  </div>
                </td>
                <td>
                  <button
                    aria-label={`Draft ${player.player_name}`}
                    disabled={isSaving}
                    onClick={() => onDraftPlayer(player.player_id)}
                    type="button"
                  >
                    Draft
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
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
  board,
  draft,
  setupTeamName,
}: {
  availableTotal: number;
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
          <strong>{playersRemaining}</strong>
        </div>
      </div>
    </section>
  );
}

function AvailablePlayersTable({
  direction,
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
            placeholder="DEN"
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
      {!isLoading && players.length === 0 ? (
        <p className="state-message">No available players match the current filters.</p>
      ) : null}
      {!isLoading && players.length > 0 ? (
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
                      Draft
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

function formatReason(reason: AssistantReason) {
  if (reason.code === "BEST_AVAILABLE") {
    return "Top overall value";
  }
  if (reason.code === "BEST_AT_POSITION") {
    return `Top available ${reason.position}`;
  }
  if (reason.code === "FILLS_RESTRICTIVE_SLOT") {
    return `Fills an open ${formatSlots(reason.slots)} slot`;
  }
  if (reason.code === "MULTI_SLOT_FLEXIBILITY") {
    return "Fits multiple open slots";
  }
  return "Matches an open roster slot";
}

function formatSlots(slots: SlotInstance[]) {
  return slots.map(formatSlot).join(", ");
}

function formatSlot(slot: SlotInstance) {
  const label =
    slot.slot === "G"
      ? "Guard"
      : slot.slot === "F"
        ? "Forward"
        : slot.slot === "UTIL"
          ? "Any active position"
          : slot.slot;
  return `${label} ${slot.slot_index}`;
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
