export type DraftStatus = "setup" | "in_progress" | "completed";
export type SortDirection = "asc" | "desc";
export type DraftSort =
  | "player"
  | "team"
  | "position"
  | "fantasy_points_per_game"
  | "projected_fantasy_points"
  | "overall_vor"
  | "overall_rank";

export type LeagueResponse = {
  name: string;
  season: number;
  team_count: number;
};

export type DraftSession = {
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

export type FantasyTeam = {
  id: number;
  draft_session_id: number;
  name: string;
  draft_position: number;
  is_user_team: boolean;
};

export type DraftPick = {
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

export type DraftBoard = {
  draft: DraftSession;
  on_clock_team: FantasyTeam | null;
  teams: FantasyTeam[];
  picks: DraftPick[];
  recent_picks: DraftPick[];
};

export type AvailablePlayer = {
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

export type AvailablePlayerResponse = {
  items: AvailablePlayer[];
  total: number;
  limit: number;
  offset: number;
};

export type SlotInstance = {
  slot: string;
  slot_index: number;
};

export type AssistantReason = {
  code:
    | "BEST_AVAILABLE"
    | "BEST_AT_POSITION"
    | "BEYOND_NEXT_PICK_WINDOW"
    | "FILLS_OPEN_SLOT"
    | "FILLS_RESTRICTIVE_SLOT"
    | "INSIDE_NEXT_PICK_WINDOW"
    | "LARGE_VALUE_DROP"
    | "LIMITED_POSITION_DEPTH"
    | "MULTI_SLOT_FLEXIBILITY"
    | "NEAR_NEXT_PICK_WINDOW"
    | "NO_FUTURE_USER_PICK"
    | "POSITION_DEPTH_AVAILABLE"
    | "POSITION_VALUE_DROP"
    | "USER_ON_CLOCK";
  position: string | null;
  slots: SlotInstance[];
};

export type AssistantPlayer = {
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

export type RosterSummary = {
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

export type DraftIntelligence = {
  next_user_pick: {
    next_overall_pick: number;
    next_round: number;
    next_pick_in_round: number;
    draft_position: number;
    picks_until: number;
    is_user_on_clock: boolean;
    is_consecutive_turn: boolean;
    turn_pick_number: number;
    consecutive_pick_numbers: number[];
    consecutive_pick_overalls: number[];
  } | null;
  availability_outlook: {
    player_id: number;
    player_name: string;
    team: string | null;
    eligible_positions: string[];
    overall_rank: number | null;
    available_rank: number;
    overall_vor: string | null;
    projected_fantasy_points: string;
    outlook: "UNLIKELY_TO_RETURN" | "AT_RISK" | "COULD_RETURN";
    reasons: AssistantReason[];
  }[];
  positional_scarcity: {
    position: string;
    top_player_id: number | null;
    top_player_name: string | null;
    top_position_vor: string | null;
    cutoff_player_id: number | null;
    cutoff_player_name: string | null;
    cutoff_position_vor: string | null;
    projected_vor_drop: string | null;
    players_before_next_pick: number;
    meaningful_options_remaining: number;
    severity: "HIGH" | "MEDIUM" | "LOW";
    reasons: AssistantReason[];
  }[];
  value_drop: {
    scan_limit: number;
    meaningful_value_drop: string;
    drop_after_available_rank: number;
    before_player_id: number;
    before_player_name: string;
    before_overall_vor: string | null;
    after_player_id: number;
    after_player_name: string;
    after_overall_vor: string | null;
    gap: string;
    reasons: AssistantReason[];
  } | null;
};

export type DraftAssistant = {
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
  intelligence: DraftIntelligence;
};

export type TeamSetup = {
  name: string;
  draft_position: number;
};
