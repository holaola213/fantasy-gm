import type { AssistantReason, DraftRecommendation, SlotInstance } from "./types";

export function DraftRecommendationsSection({
  recommendations,
  isSaving,
  onDraftPlayer,
}: {
  recommendations: DraftRecommendation[];
  isSaving: boolean;
  onDraftPlayer: (playerId: number) => void;
}) {
  return (
    <section className="assistant-section recommendations-section">
      <h3>Recommended Picks</h3>
      {recommendations.length === 0 ? (
        <p className="state-message">
          No recommendation-ready players are available right now.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Player</th>
              <th>Fit</th>
              <th>Value</th>
              <th>Why</th>
              <th>Signals</th>
              <th>Watch</th>
              <th>Pick</th>
            </tr>
          </thead>
          <tbody>
            {recommendations.map((item) => (
              <tr key={`recommendation-${item.player_id}`}>
                <td>{item.recommendation_rank}</td>
                <td>
                  <strong>{item.player_name}</strong>
                  <span className="muted-detail">
                    {item.team ?? "Unsigned"} |{" "}
                    {item.eligible_positions.join(", ") || "No eligibility"}
                  </span>
                </td>
                <td>{formatRosterFit(item)}</td>
                <td>
                  <div>{formatNumber(item.overall_vor)} VOR</div>
                  {item.score_breakdown ? (
                    <details className="score-details">
                      <summary>Score details</summary>
                      <dl>
                        <dt>Total</dt>
                        <dd>{formatNumber(item.score_breakdown.total_score)}</dd>
                        <dt>Value</dt>
                        <dd>
                          {formatNumber(item.score_breakdown.value_proximity_score)}
                        </dd>
                        <dt>Roster</dt>
                        <dd>{formatNumber(item.score_breakdown.roster_fit_score)}</dd>
                        <dt>Scarcity</dt>
                        <dd>{formatNumber(item.score_breakdown.scarcity_score)}</dd>
                        <dt>Availability</dt>
                        <dd>{formatNumber(item.score_breakdown.availability_score)}</dd>
                        <dt>Drop</dt>
                        <dd>{formatNumber(item.score_breakdown.value_drop_score)}</dd>
                        <dt>Flex</dt>
                        <dd>{formatNumber(item.score_breakdown.flexibility_score)}</dd>
                      </dl>
                    </details>
                  ) : (
                    <span className="muted-detail">Value-based alternative</span>
                  )}
                </td>
                <td>{item.explanation}</td>
                <td>
                  <ReasonPills reasons={item.reasons} />
                </td>
                <td>
                  {item.warnings.length > 0 ? (
                    <ReasonPills reasons={item.warnings} warning />
                  ) : (
                    <span className="muted-detail">None</span>
                  )}
                </td>
                <td>
                  <button
                    aria-label={`Draft ${item.player_name}`}
                    disabled={isSaving}
                    onClick={() => onDraftPlayer(item.player_id)}
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

function ReasonPills({
  reasons,
  warning = false,
}: {
  reasons: AssistantReason[];
  warning?: boolean;
}) {
  return (
    <div className="reason-list">
      {reasons.map((reason, index) => (
        <span
          className={warning ? "reason-pill warning-pill" : "reason-pill"}
          key={`${reason.code}-${index}`}
        >
          {formatReason(reason)}
        </span>
      ))}
    </div>
  );
}

function formatRosterFit(item: DraftRecommendation) {
  const assignment = item.projected_roster_assignment;
  if (assignment.assignment_type === "active" && assignment.assigned_slot) {
    return `Active ${formatSlot({
      slot: assignment.assigned_slot,
      slot_index: assignment.slot_index ?? 1,
    })}`;
  }
  if (assignment.assignment_type === "bench") {
    return "Bench fit";
  }
  return "No current fit";
}

function formatReason(reason: AssistantReason) {
  if (reason.code === "BEST_AVAILABLE_VALUE") {
    return "Top board value";
  }
  if (reason.code === "STRONG_VALUE") {
    return "Strong value";
  }
  if (reason.code === "FILLS_RESTRICTIVE_STARTER_SLOT") {
    return `Starter ${reason.position ?? "fit"}`;
  }
  if (reason.code === "FILLS_FLEX_SLOT") {
    return `Flex ${formatSlots(reason.slots) || "fit"}`;
  }
  if (reason.code === "IMPROVES_ACTIVE_LINEUP") {
    return "Improves active lineup";
  }
  if (reason.code === "MULTI_POSITION_FLEXIBILITY") {
    return "Useful flexibility";
  }
  if (reason.code === "LIMITED_POSITION_DEPTH") {
    return `Limited ${reason.position ?? "position"} depth`;
  }
  if (reason.code === "POSITION_VALUE_DROP") {
    return `${reason.position ?? "Position"} value drop`;
  }
  if (reason.code === "UNLIKELY_TO_RETURN") {
    return "May not return";
  }
  if (reason.code === "AT_RISK_BEFORE_NEXT_PICK") {
    return "At risk";
  }
  if (reason.code === "BEFORE_MEANINGFUL_VALUE_DROP") {
    return "Before value drop";
  }
  if (reason.code === "BENCH_ONLY_FIT") {
    return "Bench-only fit";
  }
  if (reason.code === "POSITION_ALREADY_DEEP") {
    return `${reason.position ?? "Position"} depth available`;
  }
  if (reason.code === "COULD_RETURN_LATER") {
    return "Could return";
  }
  if (reason.code === "SIGNIFICANT_VALUE_REACH") {
    return "Meaningful value reach";
  }
  return "Additional draft context";
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
