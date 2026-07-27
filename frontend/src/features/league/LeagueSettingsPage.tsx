import { useEffect, useMemo, useState } from "react";

type NumberInputValue = number | "";

type ScoringRule = {
  client_id: string;
  stat_key: string;
  display_name: string;
  points: string;
  sort_order: NumberInputValue;
};

type RosterSlot = {
  client_id: string;
  slot_key: string;
  display_name: string;
  count: NumberInputValue;
  sort_order: NumberInputValue;
};

type LeagueForm = {
  name: string;
  platform: "ESPN";
  season: NumberInputValue;
  team_count: NumberInputValue;
  scoring_format: "points";
  acquisition_limit_per_day: NumberInputValue;
  playoff_team_count: NumberInputValue;
  scoring_rules: ScoringRule[];
  roster_slots: RosterSlot[];
};

type LeagueScoringRuleResponse = Omit<
  ScoringRule,
  "client_id" | "points"
> & { points: number };
type LeagueRosterSlotResponse = Omit<RosterSlot, "client_id"> & {
  count: number;
  sort_order: number;
};

type LeagueResponse = Omit<
  LeagueForm,
  "acquisition_limit_per_day" | "scoring_rules" | "roster_slots"
> & {
  id: number;
  acquisition_limit_per_day: number | null;
  season: number;
  team_count: number;
  playoff_team_count: number;
  scoring_rules: LeagueScoringRuleResponse[];
  roster_slots: LeagueRosterSlotResponse[];
};

const fixedScoringRules = {
  PTS: {
    display_name: "Points",
    points: "1",
    sort_order: 10,
  },
  TEAM_WINS: {
    display_name: "Team Wins",
    points: "1",
    sort_order: 11,
  },
} as const;

function isFixedScoringKey(value: string) {
  return normalizeKey(value) in fixedScoringRules;
}

const defaultLeagueForm: LeagueForm = {
  name: "Fantasy GM Development League",
  platform: "ESPN",
  season: 2026,
  team_count: 12,
  scoring_format: "points",
  acquisition_limit_per_day: 1,
  playoff_team_count: 8,
  scoring_rules: [
    { client_id: "default-scoring-FGM", stat_key: "FGM", display_name: "Field Goals Made", points: "1", sort_order: 1 },
    { client_id: "default-scoring-FGA", stat_key: "FGA", display_name: "Field Goals Attempted", points: "-1", sort_order: 2 },
    { client_id: "default-scoring-FTM", stat_key: "FTM", display_name: "Free Throws Made", points: "1", sort_order: 3 },
    { client_id: "default-scoring-FTA", stat_key: "FTA", display_name: "Free Throws Attempted", points: "-1", sort_order: 4 },
    { client_id: "default-scoring-REB", stat_key: "REB", display_name: "Rebounds", points: "1", sort_order: 5 },
    { client_id: "default-scoring-AST", stat_key: "AST", display_name: "Assists", points: "1", sort_order: 6 },
    { client_id: "default-scoring-STL", stat_key: "STL", display_name: "Steals", points: "2", sort_order: 7 },
    { client_id: "default-scoring-BLK", stat_key: "BLK", display_name: "Blocks", points: "2", sort_order: 8 },
    { client_id: "default-scoring-TO", stat_key: "TO", display_name: "Turnovers", points: "-1", sort_order: 9 },
    { client_id: "default-scoring-PTS", stat_key: "PTS", display_name: "Points", points: "1", sort_order: 10 },
    { client_id: "default-scoring-TEAM_WINS", stat_key: "TEAM_WINS", display_name: "Team Wins", points: "1", sort_order: 11 },
  ],
  roster_slots: [
    { client_id: "default-slot-PG", slot_key: "PG", display_name: "Point Guard", count: 1, sort_order: 1 },
    { client_id: "default-slot-SG", slot_key: "SG", display_name: "Shooting Guard", count: 1, sort_order: 2 },
    { client_id: "default-slot-SF", slot_key: "SF", display_name: "Small Forward", count: 1, sort_order: 3 },
    { client_id: "default-slot-PF", slot_key: "PF", display_name: "Power Forward", count: 1, sort_order: 4 },
    { client_id: "default-slot-C", slot_key: "C", display_name: "Center", count: 1, sort_order: 5 },
    { client_id: "default-slot-G", slot_key: "G", display_name: "Guard", count: 1, sort_order: 6 },
    { client_id: "default-slot-F", slot_key: "F", display_name: "Forward", count: 1, sort_order: 7 },
    { client_id: "default-slot-UTIL", slot_key: "UTIL", display_name: "Utility", count: 3, sort_order: 8 },
    { client_id: "default-slot-BE", slot_key: "BE", display_name: "Bench", count: 4, sort_order: 9 },
    { client_id: "default-slot-IR", slot_key: "IR", display_name: "Injured Reserve", count: 2, sort_order: 10 },
  ],
};

function createClientId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function leagueResponseToForm(league: LeagueResponse): LeagueForm {
  return {
    name: league.name,
    platform: league.platform,
    season: league.season,
    team_count: league.team_count,
    scoring_format: league.scoring_format,
    acquisition_limit_per_day: league.acquisition_limit_per_day ?? "",
    playoff_team_count: league.playoff_team_count,
    scoring_rules: ensureFixedScoringRules(
      league.scoring_rules.map((rule) => ({
        ...rule,
        client_id: `saved-scoring-${rule.stat_key}-${rule.sort_order}`,
        points: String(rule.points),
      })),
    ),
    roster_slots: league.roster_slots.map((slot) => ({
      ...slot,
      client_id: `saved-slot-${slot.slot_key}-${slot.sort_order}`,
    })),
  };
}

function normalizeKey(value: string) {
  return value.trim().toUpperCase();
}

function ensureFixedScoringRules(rules: ScoringRule[]) {
  const byKey = new Map(rules.map((rule) => [normalizeKey(rule.stat_key), rule]));
  const nextRules = [...rules];
  for (const [statKey, fixedRule] of Object.entries(fixedScoringRules)) {
    const existing = byKey.get(statKey);
    if (existing) {
      const index = nextRules.indexOf(existing);
      nextRules[index] = {
        ...existing,
        stat_key: statKey,
        points: fixedRule.points,
        display_name: existing.display_name.trim()
          ? existing.display_name
          : fixedRule.display_name,
      };
      continue;
    }
    nextRules.push({
      client_id: `fixed-scoring-${statKey}`,
      stat_key: statKey,
      display_name: fixedRule.display_name,
      points: fixedRule.points,
      sort_order: fixedRule.sort_order,
    });
  }
  return nextRules.sort((left, right) => {
    const leftSort = isValidNumber(left.sort_order) ? left.sort_order : 999;
    const rightSort = isValidNumber(right.sort_order) ? right.sort_order : 999;
    return leftSort - rightSort;
  });
}

function parseNumberInput(value: string): NumberInputValue {
  return value === "" ? "" : Number(value);
}

function isValidNumber(value: NumberInputValue): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function LeagueSettingsPage() {
  const [form, setForm] = useState<LeagueForm>(defaultLeagueForm);
  const [savedForm, setSavedForm] = useState<LeagueForm | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isConfigured, setIsConfigured] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function loadLeague() {
      try {
        const response = await fetch("/api/league", { signal: controller.signal });

        if (response.status === 404) {
          if (isMounted) {
            setForm(defaultLeagueForm);
            setSavedForm(null);
            setIsConfigured(false);
            setErrorMessage(null);
          }
          return;
        }

        if (!response.ok) {
          throw new Error("League request failed");
        }

        const data = (await response.json()) as LeagueResponse;
        const loadedForm = leagueResponseToForm(data);

        if (isMounted) {
          setForm(loadedForm);
          setSavedForm(loadedForm);
          setIsConfigured(true);
          setErrorMessage(null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setErrorMessage("Unable to load league settings.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadLeague();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  const hasUnsavedChanges = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(savedForm ?? defaultLeagueForm),
    [form, savedForm],
  );

  function updateFormField<K extends keyof LeagueForm>(
    key: K,
    value: LeagueForm[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
    setSuccessMessage(null);
  }

  function updateScoringRule(
    index: number,
    key: keyof ScoringRule,
    value: string | NumberInputValue,
  ) {
    setForm((current) => ({
      ...current,
      scoring_rules: current.scoring_rules.map((rule, ruleIndex) =>
        ruleIndex === index ? { ...rule, [key]: value } : rule,
      ),
    }));
    setSuccessMessage(null);
  }

  function updateRosterSlot(
    index: number,
    key: keyof RosterSlot,
    value: string | NumberInputValue,
  ) {
    setForm((current) => ({
      ...current,
      roster_slots: current.roster_slots.map((slot, slotIndex) =>
        slotIndex === index ? { ...slot, [key]: value } : slot,
      ),
    }));
    setSuccessMessage(null);
  }

  function validateForm(): string[] {
    const errors: string[] = [];
    const scoringKeys = form.scoring_rules.map((rule) => normalizeKey(rule.stat_key));
    const rosterKeys = form.roster_slots.map((slot) => normalizeKey(slot.slot_key));

    if (!isValidNumber(form.season)) {
      errors.push("Season must be a valid number.");
    }
    if (!isValidNumber(form.team_count)) {
      errors.push("Team count must be a valid number.");
    }
    if (
      form.acquisition_limit_per_day !== "" &&
      !isValidNumber(form.acquisition_limit_per_day)
    ) {
      errors.push("Acquisition limit must be blank or a valid number.");
    }
    if (!isValidNumber(form.playoff_team_count)) {
      errors.push("Playoff team count must be a valid number.");
    }
    if (
      isValidNumber(form.playoff_team_count) &&
      isValidNumber(form.team_count) &&
      form.playoff_team_count > form.team_count
    ) {
      errors.push("Playoff teams cannot exceed team count.");
    }
    if (form.scoring_rules.length === 0) {
      errors.push("At least one scoring rule is required.");
    }
    if (form.scoring_rules.some((rule) => !isValidNumber(rule.sort_order))) {
      errors.push("Every scoring rule needs a valid sort order.");
    }
    if (new Set(scoringKeys).size !== scoringKeys.length) {
      errors.push("Scoring rule keys must be unique after uppercasing.");
    }
    if (form.roster_slots.length === 0) {
      errors.push("At least one roster slot is required.");
    }
    if (form.roster_slots.some((slot) => !isValidNumber(slot.count))) {
      errors.push("Every roster slot needs a valid count.");
    }
    if (form.roster_slots.some((slot) => !isValidNumber(slot.sort_order))) {
      errors.push("Every roster slot needs a valid sort order.");
    }
    if (new Set(rosterKeys).size !== rosterKeys.length) {
      errors.push("Roster slot keys must be unique after uppercasing.");
    }
    if (
      form.roster_slots.some((slot) => isValidNumber(slot.count) && slot.count < 0)
    ) {
      errors.push("Roster slot counts cannot be negative.");
    }
    if (
      !form.roster_slots.some((slot) => isValidNumber(slot.count) && slot.count > 0)
    ) {
      errors.push("At least one roster slot must have a count greater than zero.");
    }
    if (form.scoring_rules.some((rule) => rule.points.trim() === "")) {
      errors.push("Every scoring rule needs a decimal points value.");
    }
    if (form.scoring_rules.some((rule) => Number.isNaN(Number(rule.points)))) {
      errors.push("Scoring rule points must be valid decimal numbers.");
    }
    for (const [statKey, fixedRule] of Object.entries(fixedScoringRules)) {
      const rule = form.scoring_rules.find(
        (item) => normalizeKey(item.stat_key) === statKey,
      );
      if (!rule) {
        errors.push(`${statKey} is required for this fixed ESPN points league.`);
        continue;
      }
      if (rule.points !== fixedRule.points) {
        errors.push(`${statKey} must remain ${fixedRule.points} point.`);
      }
    }

    return errors;
  }

  async function saveLeague() {
    const errors = validateForm();
    setValidationErrors(errors);
    setSuccessMessage(null);

    if (errors.length > 0) {
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);

    if (
      !isValidNumber(form.season) ||
      !isValidNumber(form.team_count) ||
      !isValidNumber(form.playoff_team_count)
    ) {
      return;
    }

    const payload = {
      name: form.name,
      platform: form.platform,
      season: form.season,
      team_count: form.team_count,
      scoring_format: form.scoring_format,
      acquisition_limit_per_day:
        form.acquisition_limit_per_day === "" ? null : form.acquisition_limit_per_day,
      playoff_team_count: form.playoff_team_count,
      scoring_rules: ensureFixedScoringRules(form.scoring_rules).map((rule) => ({
        stat_key: normalizeKey(rule.stat_key),
        display_name: rule.display_name,
        points: Number(rule.points),
        sort_order: isValidNumber(rule.sort_order) ? rule.sort_order : 0,
      })),
      roster_slots: form.roster_slots.map((slot) => ({
        slot_key: normalizeKey(slot.slot_key),
        display_name: slot.display_name,
        count: isValidNumber(slot.count) ? slot.count : 0,
        sort_order: isValidNumber(slot.sort_order) ? slot.sort_order : 0,
      })),
    };

    try {
      const response = await fetch("/api/league", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        if (response.status === 422) {
          setValidationErrors(["The backend rejected one or more values."]);
          return;
        }
        throw new Error("League save failed");
      }

      const data = (await response.json()) as LeagueResponse;
      const saved = leagueResponseToForm(data);
      setForm(saved);
      setSavedForm(saved);
      setIsConfigured(true);
      setValidationErrors([]);
      setSuccessMessage("League settings saved.");
    } catch {
      setErrorMessage("Unable to save league settings.");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return <p className="state-message">Loading league settings...</p>;
  }

  return (
    <div className="league-settings">
      {!isConfigured ? (
        <p className="state-message notice">
          League not configured. Save this form to create the local configuration.
        </p>
      ) : null}
      {hasUnsavedChanges ? (
        <p className="state-message notice">Unsaved changes</p>
      ) : null}
      {errorMessage ? <p className="state-message error">{errorMessage}</p> : null}
      {successMessage ? (
        <p className="state-message success">{successMessage}</p>
      ) : null}
      {validationErrors.length > 0 ? (
        <ul className="validation-list">
          {validationErrors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      ) : null}

      <div className="form-grid">
        <label>
          League Name
          <input
            value={form.name}
            onChange={(event) => updateFormField("name", event.target.value)}
          />
        </label>
        <label>
          Platform
          <input value={form.platform} readOnly />
        </label>
        <label>
          Season
          <input
            type="number"
            value={form.season}
            onChange={(event) =>
              updateFormField("season", parseNumberInput(event.target.value))
            }
          />
        </label>
        <label>
          Teams
          <input
            type="number"
            value={form.team_count}
            onChange={(event) =>
              updateFormField("team_count", parseNumberInput(event.target.value))
            }
          />
        </label>
        <label>
          Scoring Format
          <input value={form.scoring_format} readOnly />
        </label>
        <label>
          Acquisition Limit Per Day
          <input
            type="number"
            value={form.acquisition_limit_per_day}
            onChange={(event) =>
              updateFormField(
                "acquisition_limit_per_day",
                parseNumberInput(event.target.value),
              )
            }
          />
        </label>
        <label>
          Playoff Teams
          <input
            type="number"
            value={form.playoff_team_count}
            onChange={(event) =>
              updateFormField(
                "playoff_team_count",
                parseNumberInput(event.target.value),
              )
            }
          />
        </label>
      </div>

      <EditableScoringRules
        rules={form.scoring_rules}
        onAdd={() =>
          updateFormField("scoring_rules", [
            ...form.scoring_rules,
            {
              client_id: createClientId("scoring"),
              stat_key: "",
              display_name: "",
              points: "0",
              sort_order: form.scoring_rules.length + 1,
            },
          ])
        }
        onRemove={(index) =>
          updateFormField(
            "scoring_rules",
            ensureFixedScoringRules(
              form.scoring_rules.filter(
                (rule, ruleIndex) =>
                  ruleIndex !== index || isFixedScoringKey(rule.stat_key),
              ),
            ),
          )
        }
        onUpdate={updateScoringRule}
      />

      <EditableRosterSlots
        slots={form.roster_slots}
        onAdd={() =>
          updateFormField("roster_slots", [
            ...form.roster_slots,
            {
              client_id: createClientId("slot"),
              slot_key: "",
              display_name: "",
              count: 0,
              sort_order: form.roster_slots.length + 1,
            },
          ])
        }
        onRemove={(index) =>
          updateFormField(
            "roster_slots",
            form.roster_slots.filter((_, slotIndex) => slotIndex !== index),
          )
        }
        onUpdate={updateRosterSlot}
      />

      <div className="actions">
        <button disabled={isSaving} onClick={() => void saveLeague()} type="button">
          {isSaving ? "Saving..." : "Save League Settings"}
        </button>
      </div>
    </div>
  );
}

function EditableScoringRules({
  rules,
  onAdd,
  onRemove,
  onUpdate,
}: {
  rules: ScoringRule[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (
    index: number,
    key: keyof ScoringRule,
    value: string | NumberInputValue,
  ) => void;
}) {
  return (
    <section className="editor-section">
      <div className="section-header">
        <h2>Scoring Rules</h2>
        <button onClick={onAdd} type="button">Add Rule</button>
      </div>
      <p className="state-message">
        PTS and TEAM_WINS are required fixed rules for this ESPN points league.
        TEAM_WINS is part of league scoring but is not projected yet, so it
        currently contributes 0 in diagnostics and valuations.
      </p>
      <table>
        <thead>
          <tr>
            <th>Stat Key</th>
            <th>Display Name</th>
            <th>Points</th>
            <th>Sort</th>
            <th>Remove</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule, index) => (
            <tr key={rule.client_id}>
              {(() => {
                const isFixed = isFixedScoringKey(rule.stat_key);
                return (
                  <>
              <td>
                <input
                  readOnly={isFixed}
                  value={rule.stat_key}
                  onChange={(event) =>
                    onUpdate(index, "stat_key", event.target.value)
                  }
                  aria-label={`Scoring rule ${index + 1} stat key`}
                />
                {isFixed ? <span className="muted-detail">Required</span> : null}
              </td>
              <td>
                <input
                  value={rule.display_name}
                  onChange={(event) =>
                    onUpdate(index, "display_name", event.target.value)
                  }
                  aria-label={`Scoring rule ${index + 1} display name`}
                />
              </td>
              <td>
                <input
                  readOnly={isFixed}
                  value={rule.points}
                  onChange={(event) =>
                    onUpdate(index, "points", event.target.value)
                  }
                  aria-label={`Scoring rule ${index + 1} points`}
                />
                {normalizeKey(rule.stat_key) === "TEAM_WINS" ? (
                  <span className="muted-detail">Configured, not projected yet.</span>
                ) : null}
              </td>
              <td>
                <input
                  type="number"
                  value={rule.sort_order}
                  onChange={(event) =>
                    onUpdate(index, "sort_order", parseNumberInput(event.target.value))
                  }
                  aria-label={`Scoring rule ${index + 1} sort order`}
                />
              </td>
              <td>
                <button
                  disabled={isFixed}
                  onClick={() => onRemove(index)}
                  type="button"
                >
                  {isFixed ? "Required" : "Remove"}
                </button>
              </td>
                  </>
                );
              })()}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function EditableRosterSlots({
  slots,
  onAdd,
  onRemove,
  onUpdate,
}: {
  slots: RosterSlot[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (
    index: number,
    key: keyof RosterSlot,
    value: string | NumberInputValue,
  ) => void;
}) {
  return (
    <section className="editor-section">
      <div className="section-header">
        <h2>Roster Slots</h2>
        <button onClick={onAdd} type="button">Add Slot</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Slot Key</th>
            <th>Display Name</th>
            <th>Count</th>
            <th>Sort</th>
            <th>Remove</th>
          </tr>
        </thead>
        <tbody>
          {slots.map((slot, index) => (
            <tr key={slot.client_id}>
              <td>
                <input
                  value={slot.slot_key}
                  onChange={(event) =>
                    onUpdate(index, "slot_key", event.target.value)
                  }
                  aria-label={`Roster slot ${index + 1} key`}
                />
              </td>
              <td>
                <input
                  value={slot.display_name}
                  onChange={(event) =>
                    onUpdate(index, "display_name", event.target.value)
                  }
                  aria-label={`Roster slot ${index + 1} display name`}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={slot.count}
                  onChange={(event) =>
                    onUpdate(index, "count", parseNumberInput(event.target.value))
                  }
                  aria-label={`Roster slot ${index + 1} count`}
                />
              </td>
              <td>
                <input
                  type="number"
                  value={slot.sort_order}
                  onChange={(event) =>
                    onUpdate(index, "sort_order", parseNumberInput(event.target.value))
                  }
                  aria-label={`Roster slot ${index + 1} sort order`}
                />
              </td>
              <td>
                <button onClick={() => onRemove(index)} type="button">Remove</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
