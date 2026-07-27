import { Fragment, useEffect, useState } from "react";

import { ExplainedTerm } from "../../shared/ExplainedTerm";
import { helpText } from "../../shared/helpText";
import { useDebouncedValue } from "../../shared/useDebouncedValue";

type SortDirection = "asc" | "desc";
type ValuationSort =
  | "player"
  | "team"
  | "position"
  | "fantasy_points_per_game"
  | "projected_fantasy_points"
  | "overall_vor"
  | "overall_rank";

type PositionValue = {
  position: string;
  replacement_player_id: number;
  replacement_player_name: string;
  replacement_fantasy_points: string;
  vor: string;
  position_rank: number;
};

type PlayerValuation = {
  player_id: number;
  player_name: string;
  team: string | null;
  primary_position: string | null;
  eligible_positions: string[];
  compatible_roster_slots: string[];
  projected_games: string;
  fantasy_points_per_game: string;
  projected_fantasy_points: string;
  position_values: PositionValue[];
  overall_vor: string | null;
  best_value_position: string | null;
  overall_rank: number | null;
};

type ValuationResponse = {
  items: PlayerValuation[];
  total: number;
  limit: number;
  offset: number;
  projection_set_id: number;
  projection_set_name: string;
  projection_set_as_of_date: string;
};

type ReplacementLevel = {
  position: string;
  demand: number;
  replacement_player_name: string;
  replacement_fantasy_points: string;
};

type ReplacementResponse = {
  team_count: number;
  total_active_demand: number;
  drafted_player_target: number;
  positions: ReplacementLevel[];
};

type ValuationDiagnostics = {
  player: {
    id: number;
    name: string;
    team: string | null;
    primary_position: string | null;
    eligible_positions: string[];
  };
  projection: {
    projection_set_id: number;
    games: string;
    minutes_per_game: string;
    raw_projected_stats: Record<string, string | null>;
  };
  scoring: {
    rules: {
      stat_key: string;
      display_name: string;
      points: string;
      sort_order: number;
    }[];
    contributions: {
      stat_name: string;
      scoring_key: string;
      configured_stat_key: string | null;
      is_configured: boolean;
      projection_value: string | null;
      league_weight: string;
      contribution: string;
    }[];
    unsupported_rules: {
      stat_key: string;
      points: string;
      contribution: string;
      message: string;
    }[];
    fantasy_points_per_game: string;
    projected_fantasy_points: string;
  };
  replacement: {
    calculation_method: string;
    replacement_levels: {
      position: string;
      replacement_player_id: number;
      replacement_player_name: string;
      replacement_fantasy_points: string;
      vor: string;
      position_rank: number;
    }[];
    selected_replacement_position: string | null;
    selected_replacement_player_id: number | null;
    selected_replacement_player_name: string | null;
    selected_replacement_fantasy_points: string | null;
    overall_vor: string | null;
  };
  metadata: {
    league_id: number;
    projection_set_id: number;
    valuation_algorithm_version: string;
    scoring_format: string;
    assumptions: string[];
  };
};

export function ValuationsPage() {
  const [players, setPlayers] = useState<PlayerValuation[]>([]);
  const [replacement, setReplacement] = useState<ReplacementResponse | null>(null);
  const [context, setContext] = useState<ValuationResponse | null>(null);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [team, setTeam] = useState("");
  const [position, setPosition] = useState("");
  const [sort, setSort] = useState<ValuationSort>("overall_rank");
  const [direction, setDirection] = useState<SortDirection>("asc");
  const [offset, setOffset] = useState(0);
  const [expandedPlayerId, setExpandedPlayerId] = useState<number | null>(null);
  const [diagnostics, setDiagnostics] = useState<ValuationDiagnostics | null>(null);
  const [diagnosticError, setDiagnosticError] = useState<string | null>(null);
  const [isLoadingDiagnostics, setIsLoadingDiagnostics] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const limit = 50;
  const debouncedSearch = useDebouncedValue(search, 300);
  const debouncedTeam = useDebouncedValue(team, 300);

  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch, debouncedTeam, position, sort, direction]);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function loadValuations() {
      setIsLoading(true);
      const params = new URLSearchParams({
        sort,
        direction,
        limit: String(limit),
        offset: String(offset),
      });
      if (debouncedSearch.trim()) {
        params.set("search", debouncedSearch.trim());
      }
      if (debouncedTeam.trim()) {
        params.set("team", debouncedTeam.trim());
      }
      if (position) {
        params.set("position", position);
      }

      try {
        const [valuationResponse, replacementResponse] = await Promise.all([
          fetch(`/api/valuations?${params.toString()}`, { signal: controller.signal }),
          fetch("/api/valuations/replacement-levels", { signal: controller.signal }),
        ]);
        if (!valuationResponse.ok || !replacementResponse.ok) {
          const detail = await valuationResponse.json().catch(() => null);
          throw new Error(detail?.detail ?? "valuation request failed");
        }
        const valuationData = (await valuationResponse.json()) as ValuationResponse;
        const replacementData =
          (await replacementResponse.json()) as ReplacementResponse;
        if (isMounted) {
          setPlayers(valuationData.items);
          setTotal(valuationData.total);
          setContext(valuationData);
          setReplacement(replacementData);
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
            error instanceof Error && error.message
              ? error.message
              : "Unable to load valuations.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadValuations();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [debouncedSearch, debouncedTeam, position, sort, direction, offset]);

  function changeSort(nextSort: ValuationSort) {
    if (sort === nextSort) {
      setDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSort(nextSort);
    setDirection(
      nextSort === "player" || nextSort === "team" || nextSort === "position"
        ? "asc"
        : nextSort === "overall_rank"
          ? "asc"
          : "desc",
    );
  }

  async function loadDiagnostics(playerId: number) {
    setIsLoadingDiagnostics(true);
    setDiagnosticError(null);
    setDiagnostics(null);
    try {
      const params = new URLSearchParams();
      if (context?.projection_set_id) {
        params.set("projection_set_id", String(context.projection_set_id));
      }
      const response = await fetch(
        `/api/valuations/players/${playerId}/diagnostics${
          params.toString() ? `?${params.toString()}` : ""
        }`,
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Unable to load diagnostics.");
      }
      setDiagnostics((await response.json()) as ValuationDiagnostics);
    } catch (error) {
      setDiagnosticError(
        error instanceof Error ? error.message : "Unable to load diagnostics.",
      );
    } finally {
      setIsLoadingDiagnostics(false);
    }
  }

  return (
    <div className="valuations-page">
      {errorMessage ? <p className="state-message error">{errorMessage}</p> : null}

      {context ? (
        <section className="summary-panel" aria-labelledby="valuation-context-heading">
          <h2 id="valuation-context-heading">Valuation Context</h2>
          <div className="summary-grid">
            <div>
              <span>Projection Set</span>
              <strong>{context.projection_set_name}</strong>
            </div>
            <div>
              <span>As Of</span>
              <strong>{context.projection_set_as_of_date}</strong>
            </div>
            <div>
              <span>Active Demand</span>
              <strong>{replacement?.total_active_demand ?? "Unknown"}</strong>
            </div>
            <div>
              <span>Drafted Target</span>
              <strong>{replacement?.drafted_player_target ?? "Unknown"}</strong>
            </div>
          </div>
        </section>
      ) : null}

      {replacement ? (
        <section className="editor-section">
          <div className="section-header">
            <h2>Replacement Levels</h2>
          </div>
          <table>
            <thead>
              <tr>
                <th>Position</th>
                <th>Replacement Player</th>
                <th>
                  <HeaderWithHelp
                    label="Projected Total"
                    help={helpText.projectedTotal}
                  />
                </th>
              </tr>
            </thead>
            <tbody>
              {replacement.positions.map((item) => (
                <tr key={item.position}>
                  <td>{item.position}</td>
                  <td>{item.replacement_player_name}</td>
                  <td>{formatNumber(item.replacement_fantasy_points)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      <div className="filters" aria-label="Valuation filters">
        <label>
          Search
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Player name"
          />
        </label>
        <label>
          NBA Team
          <input
            value={team}
            onChange={(event) => setTeam(event.target.value)}
            placeholder="DEN"
          />
        </label>
        <label>
          Eligibility
          <select value={position} onChange={(event) => setPosition(event.target.value)}>
            <option value="">All positions</option>
            {["PG", "SG", "SF", "PF", "C"].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading ? <p className="state-message">Loading valuations...</p> : null}
      {!isLoading && !errorMessage && players.length === 0 ? (
        <p className="state-message">No valuations match the current filters.</p>
      ) : null}
      {!isLoading && !errorMessage && players.length > 0 ? (
        <section className="editor-section">
          <p className="result-count">{total} player valuations</p>
          <table>
            <thead>
              <tr>
                <SortableHeader label="Rank" sortKey="overall_rank" currentSort={sort} direction={direction} onSort={changeSort} />
                <SortableHeader label="Player" sortKey="player" currentSort={sort} direction={direction} onSort={changeSort} />
                <SortableHeader label="NBA Team" sortKey="team" currentSort={sort} direction={direction} onSort={changeSort} />
                <th>
                  <HeaderWithHelp label="Eligibility" help={helpText.eligibility} />
                </th>
                <SortableHeader label="Fantasy PPG" help={helpText.fantasyPpg} sortKey="fantasy_points_per_game" currentSort={sort} direction={direction} onSort={changeSort} />
                <SortableHeader label="Projected Total" help={helpText.projectedTotal} sortKey="projected_fantasy_points" currentSort={sort} direction={direction} onSort={changeSort} />
                <SortableHeader label="Overall VOR" help={helpText.vor} sortKey="overall_vor" currentSort={sort} direction={direction} onSort={changeSort} />
                <th>Value Position</th>
                <th>Explain</th>
              </tr>
            </thead>
            <tbody>
              {players.map((player) => (
                <Fragment key={player.player_id}>
                  <tr>
                    <td>{player.overall_rank ?? "None"}</td>
                    <td>
                      <button
                        className="link-button"
                        onClick={() =>
                          setExpandedPlayerId((current) =>
                            current === player.player_id ? null : player.player_id,
                          )
                        }
                        type="button"
                      >
                        {player.player_name}
                      </button>
                    </td>
                    <td>{player.team ?? "Unsigned"}</td>
                    <td>{player.eligible_positions.join(", ") || "None"}</td>
                    <td>{formatSignedNumber(player.fantasy_points_per_game)}</td>
                    <td>{formatNumber(player.projected_fantasy_points)}</td>
                    <td>{formatVor(player.overall_vor)}</td>
                    <td>{player.best_value_position ?? "None"}</td>
                    <td>
                      <button
                        onClick={() => void loadDiagnostics(player.player_id)}
                        type="button"
                      >
                        Explain
                      </button>
                    </td>
                  </tr>
                  {expandedPlayerId === player.player_id ? (
                    <tr key={`${player.player_id}-details`}>
                      <td colSpan={9}>
                        <PositionDetails values={player.position_values} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
          <div className="pagination-actions">
            <button
              disabled={offset === 0}
              onClick={() => setOffset((current) => Math.max(current - limit, 0))}
              type="button"
            >
              Previous
            </button>
            <span>
              {offset + 1} - {Math.min(offset + players.length, total)} of {total}
            </span>
            <button
              disabled={offset + limit >= total}
              onClick={() => setOffset((current) => current + limit)}
              type="button"
            >
              Next
            </button>
          </div>
        </section>
      ) : null}
      {isLoadingDiagnostics || diagnosticError || diagnostics ? (
        <DiagnosticsDialog
          diagnostics={diagnostics}
          errorMessage={diagnosticError}
          isLoading={isLoadingDiagnostics}
          onClose={() => {
            setDiagnostics(null);
            setDiagnosticError(null);
            setIsLoadingDiagnostics(false);
          }}
        />
      ) : null}
    </div>
  );
}

function DiagnosticsDialog({
  diagnostics,
  errorMessage,
  isLoading,
  onClose,
}: {
  diagnostics: ValuationDiagnostics | null;
  errorMessage: string | null;
  isLoading: boolean;
  onClose: () => void;
}) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <dialog
      aria-labelledby="player-valuation-diagnostics-heading"
      className="diagnostics-dialog"
      open
    >
      <div className="section-header">
        <h2 id="player-valuation-diagnostics-heading">
          Player Valuation Diagnostics
        </h2>
        <button onClick={onClose} type="button">
          Close
        </button>
      </div>
      {isLoading ? <p className="state-message">Loading diagnostics...</p> : null}
      {errorMessage ? <p className="state-message error">{errorMessage}</p> : null}
      {diagnostics ? (
        <div className="diagnostics-grid">
          <p className="assumption-note">
            These values reflect the current bootstrap projection assumptions.
          </p>
          <section className="diagnostics-card">
            <h3>{diagnostics.player.name}</h3>
            <p>
              {diagnostics.player.team ?? "Unsigned"} |{" "}
              {diagnostics.player.primary_position ?? "Unknown"} | Eligibility:{" "}
              {diagnostics.player.eligible_positions.join(", ") || "None"}
            </p>
            <p>
              Projected games: {formatNumber(diagnostics.projection.games)}. Projected
              minutes: {formatNumber(diagnostics.projection.minutes_per_game)}.
            </p>
          </section>
          <section className="diagnostics-card">
            <h3>Raw Projection</h3>
            <table>
              <thead>
                <tr>
                  <th>Stat</th>
                  <th>Projection</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(diagnostics.projection.raw_projected_stats).map(
                  ([stat, value]) => (
                    <tr key={stat}>
                      <td>{formatStatName(stat)}</td>
                      <td>{formatNumber(value)}</td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </section>
          <section className="diagnostics-card">
            <h3>League Scoring Breakdown</h3>
            <table>
              <thead>
                <tr>
                  <th>Stat</th>
                  <th>Projection</th>
                  <th>League Weight</th>
                  <th>Contribution</th>
                </tr>
              </thead>
              <tbody>
                {diagnostics.scoring.contributions.map((item) => (
                  <tr key={item.stat_name}>
                    <td>{item.scoring_key}</td>
                    <td>{formatNumber(item.projection_value)}</td>
                    <td>{formatSignedNumber(item.league_weight)}</td>
                    <td>{formatSignedNumber(item.contribution)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {diagnostics.scoring.unsupported_rules.length > 0 ? (
              <div className="assumption-note">
                {diagnostics.scoring.unsupported_rules.map((item) => (
                  <p key={item.stat_key}>
                    {item.message} League weight: {formatSignedNumber(item.points)}.
                    Contribution: {formatSignedNumber(item.contribution)}.
                  </p>
                ))}
              </div>
            ) : null}
            <p>
              Fantasy PPG:{" "}
              {formatSignedNumber(diagnostics.scoring.fantasy_points_per_game)}.
              Projected Total:{" "}
              {formatSignedNumber(diagnostics.scoring.projected_fantasy_points)}.
            </p>
          </section>
          <section className="diagnostics-card">
            <h3>Replacement Baseline</h3>
            <p>{diagnostics.replacement.calculation_method}</p>
            <table>
              <thead>
                <tr>
                  <th>Position</th>
                  <th>Replacement Player</th>
                  <th>Replacement Total</th>
                  <th>VOR</th>
                </tr>
              </thead>
              <tbody>
                {diagnostics.replacement.replacement_levels.map((item) => (
                  <tr key={item.position}>
                    <td>{item.position}</td>
                    <td>{item.replacement_player_name}</td>
                    <td>{formatNumber(item.replacement_fantasy_points)}</td>
                    <td>{formatVor(item.vor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p>
              Selected baseline:{" "}
              {diagnostics.replacement.selected_replacement_position ?? "None"} | Overall
              VOR: {formatVor(diagnostics.replacement.overall_vor)}
            </p>
          </section>
        </div>
      ) : null}
    </dialog>
  );
}

function PositionDetails({ values }: { values: PositionValue[] }) {
  if (values.length === 0) {
    return <p className="state-message">No eligibility-based VOR is available.</p>;
  }
  return (
    <table className="nested-table">
      <thead>
        <tr>
          <th>Position</th>
          <th>Position Rank</th>
          <th>Replacement Player</th>
          <th>
            <HeaderWithHelp
              label="Replacement Total"
              help={helpText.replacementLevel}
            />
          </th>
          <th>
            <HeaderWithHelp label="VOR" help={helpText.vor} />
          </th>
        </tr>
      </thead>
      <tbody>
        {values.map((value) => (
          <tr key={value.position}>
            <td>{value.position}</td>
            <td>{value.position_rank}</td>
            <td>{value.replacement_player_name}</td>
            <td>{formatNumber(value.replacement_fantasy_points)}</td>
            <td>{formatVor(value.vor)}</td>
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
  sortKey: ValuationSort;
  currentSort: ValuationSort;
  direction: SortDirection;
  onSort: (sortKey: ValuationSort) => void;
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
        <button className="table-sort" onClick={() => onSort(sortKey)} type="button">
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

function formatNumber(value: string | null) {
  if (value === null) {
    return "None";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(Number(value));
}

function formatSignedNumber(value: string | null) {
  if (value === null) {
    return "None";
  }
  const numericValue = Number(value);
  const formatted = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
    signDisplay: "exceptZero",
  }).format(numericValue);
  return (
    <span className={numericValue < 0 ? "value-negative" : undefined}>
      {formatted}
    </span>
  );
}

function formatVor(value: string | null) {
  if (value === null) {
    return "None";
  }
  const numericValue = Number(value);
  return (
    <span className={numericValue < 0 ? "value-negative" : undefined}>
      {formatNumber(value)}
      {numericValue < 0 ? " below replacement" : ""}
    </span>
  );
}

function formatStatName(value: string) {
  if (value === "rebounds") {
    return "REB";
  }
  if (value === "assists") {
    return "AST";
  }
  if (value === "steals") {
    return "STL";
  }
  if (value === "blocks") {
    return "BLK";
  }
  if (value === "turnovers") {
    return "TO";
  }
  return value.toUpperCase();
}
