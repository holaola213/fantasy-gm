import type {
  AssistantPlayer,
  AssistantReason,
  DraftAssistant,
  SlotInstance,
} from "./types";
import { DraftRecommendationsSection } from "./DraftRecommendationsSection";

export function DraftAssistantPanel({
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

      <DraftIntelligenceSummary assistant={assistant} />
      <DraftRecommendationsSection
        recommendations={assistant.recommendations}
        isSaving={isSaving}
        onDraftPlayer={onDraftPlayer}
      />

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
        {assistant.roster_summary.bench_assignments.length > 0 ? (
          <div>
            <h3>Bench</h3>
            <ul>
              {assistant.roster_summary.bench_assignments.map((assignment) => (
                <li key={assignment.draft_pick_id}>
                  Bench {assignment.bench_index}: {assignment.player_name}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
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

function DraftIntelligenceSummary({ assistant }: { assistant: DraftAssistant }) {
  const { intelligence } = assistant;
  const nextPick = intelligence.next_user_pick;
  return (
    <div className="assistant-intelligence">
      <section className="assistant-section">
        <h3>Next Pick Context</h3>
        {nextPick ? (
          <div className="summary-grid">
            <div>
              <span>Your Next Pick</span>
              <strong>#{nextPick.next_overall_pick}</strong>
            </div>
            <div>
              <span>Picks Until</span>
              <strong>{nextPick.picks_until}</strong>
            </div>
            <div>
              <span>Turn Picks</span>
              <strong>
                {nextPick.is_consecutive_turn
                  ? `${nextPick.consecutive_pick_overalls.join(", ")} (${nextPick.turn_pick_number} of ${nextPick.consecutive_pick_numbers.length})`
                  : "No"}
              </strong>
            </div>
          </div>
        ) : (
          <p className="state-message">No future user pick is scheduled.</p>
        )}
      </section>

      <section className="assistant-section">
        <h3>Availability Outlook</h3>
        {intelligence.availability_outlook.length === 0 ? (
          <p className="state-message">No available players to analyze.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Player</th>
                <th>Outlook</th>
                <th>Projected Total</th>
              </tr>
            </thead>
            <tbody>
              {intelligence.availability_outlook.map((item) => (
                <tr key={item.player_id}>
                  <td>{item.available_rank}</td>
                  <td>{item.player_name}</td>
                  <td>{formatOutlook(item.outlook)}</td>
                  <td>{formatNumber(item.projected_fantasy_points)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="assistant-section">
        <h3>Positional Scarcity</h3>
        <table>
          <thead>
            <tr>
              <th>Position</th>
              <th>Severity</th>
              <th>Top Option</th>
              <th>VOR Drop</th>
              <th>Depth</th>
            </tr>
          </thead>
          <tbody>
            {intelligence.positional_scarcity.map((item) => (
              <tr key={item.position}>
                <td>{item.position}</td>
                <td>{formatSeverity(item.severity)}</td>
                <td>{item.top_player_name ?? "None"}</td>
                <td>{formatNumber(item.projected_vor_drop)}</td>
                <td>{item.meaningful_options_remaining}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="assistant-section">
        <h3>Value Drop</h3>
        {intelligence.value_drop ? (
          <p className="state-message">
            A {formatNumber(intelligence.value_drop.gap)} VOR drop appears after{" "}
            {intelligence.value_drop.before_player_name}.
          </p>
        ) : (
          <p className="state-message">
            No meaningful value drop in the scanned player window.
          </p>
        )}
      </section>
    </div>
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
  if (reason.code === "LARGE_VALUE_DROP") {
    return "Before value drop";
  }
  if (reason.code === "INSIDE_NEXT_PICK_WINDOW") {
    return "May not return";
  }
  if (reason.code === "NEAR_NEXT_PICK_WINDOW") {
    return "At risk";
  }
  if (reason.code === "USER_ON_CLOCK") {
    return "Available now";
  }
  return "Additional draft context";
}

function formatOutlook(value: string) {
  if (value === "UNLIKELY_TO_RETURN") {
    return "Unlikely to return";
  }
  if (value === "AT_RISK") {
    return "At risk";
  }
  return "Could return";
}

function formatSeverity(value: string) {
  return value.charAt(0) + value.slice(1).toLowerCase();
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
