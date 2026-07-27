import { useEffect, useState } from "react";

type BootstrapStatus = {
  projection_sets_count: number;
  csv_available: boolean;
  csv_path: string;
  metadata_available: boolean;
  metadata_path: string;
  bootstrap_projection_set_exists: boolean;
  active_bootstrap_projection_set_exists: boolean;
  imported_player_count: number;
  players_with_eligibility_count: number;
  players_missing_eligibility_count: number;
  draft_ready: boolean;
  import_available: boolean;
};

type BootstrapImportResponse = {
  projection_set_id: number;
  rows_imported: number;
  players_created: number;
  projection_rows_created: number;
};

export function BootstrapImportPanel({
  refreshKey,
  onImported,
}: {
  refreshKey: number;
  onImported: () => void;
}) {
  const [status, setStatus] = useState<BootstrapStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function loadStatus() {
      setIsLoading(true);
      try {
        const response = await fetch("/api/projection-bootstrap/status", {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Bootstrap status request failed");
        }
        const data = (await response.json()) as BootstrapStatus;
        if (isMounted) {
          setStatus(data);
          setErrorMessage(null);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (isMounted) {
          setStatus(null);
          setErrorMessage("Unable to check bootstrap data status.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadStatus();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [refreshKey]);

  async function importBootstrapData() {
    setIsImporting(true);
    setErrorMessage(null);
    setMessage(null);
    try {
      const response = await fetch("/api/projection-bootstrap/import", {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Bootstrap import failed");
      }
      const data = (await response.json()) as BootstrapImportResponse;
      setMessage(
        `Imported ${data.projection_rows_created} projection rows and ${data.players_created} players.`,
      );
      onImported();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Bootstrap import failed.",
      );
    } finally {
      setIsImporting(false);
    }
  }

  if (isLoading || status?.projection_sets_count) {
    return null;
  }

  return (
    <section className="onboarding-panel" aria-labelledby="bootstrap-heading">
      <div>
        <h2 id="bootstrap-heading">No projection data has been imported yet.</h2>
        <p>
          Import the local Basketball Reference bootstrap file to populate players
          and raw projections for development.
        </p>
        {!status?.csv_available ? (
          <p className="state-message notice">
            Bootstrap CSV not found at {status?.csv_path ?? "the configured path"}.
          </p>
        ) : null}
        {status?.csv_available && !status.metadata_available ? (
          <p className="state-message notice">
            Bootstrap metadata not found at {status.metadata_path}.
          </p>
        ) : null}
        {status?.csv_available
        && status.metadata_available
        && !status.import_available ? (
          <p className="state-message notice">
            Bootstrap import is not available because projection data already exists.
          </p>
        ) : null}
        {message ? <p className="state-message success">{message}</p> : null}
        {errorMessage ? <p className="state-message error">{errorMessage}</p> : null}
      </div>
      <button
        disabled={!status?.import_available || isImporting}
        onClick={() => void importBootstrapData()}
        type="button"
      >
        {isImporting ? "Importing..." : "Import Bootstrap Data"}
      </button>
    </section>
  );
}
