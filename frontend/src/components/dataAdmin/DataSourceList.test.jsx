import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "../../services/dataAdminApi.js";
import DataSourceList from "./DataSourceList.jsx";

vi.mock("../../services/dataAdminApi.js", () => ({
  getDataSources: vi.fn(),
  getDataSourceData: vi.fn(),
  deleteDataSource: vi.fn(),
  updateDataSourceRows: vi.fn(),
}));

const SOURCE = {
  id: 1,
  source_name: "Production Log",
  table_name: "production_log",
  original_file: "pl.xlsx",
  description: "",
  row_count: 1,
  is_active: true,
  created_at: null,
};

const PREVIEW = {
  table_name: "production_log",
  columns: [{ name: "production_date" }, { name: "stage" }, { name: "pieces_completed" }],
  data: [{ production_date: "2026-01-01", stage: "KNITTING", pieces_completed: 1027 }],
  total: 1,
  limit: 50,
  offset: 0,
};

async function openDrawer(user) {
  await user.click(await screen.findByRole("button", { name: /view/i }));
  // Wait for the preview Edit button to render.
  await screen.findByRole("button", { name: /edit/i });
}

async function openEditor(user) {
  await user.click(await screen.findByRole("button", { name: /edit/i }));
  await screen.findByText("Stage row changes");
}

async function setPieces(user, from, to) {
  const input = await screen.findByDisplayValue(from);
  await user.clear(input);
  await user.type(input, to);
}

async function stage(user) {
  await user.click(screen.getByRole("button", { name: /stage change/i }));
}

const pendingCount = () => {
  const el = screen.getByText(/pending row change/i);
  const match = el.textContent.match(/(\d+)\s+pending row change/i);
  return match ? Number(match[1]) : -1;
};

describe("DataSourceList row editing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getDataSources.mockResolvedValue({ data: [SOURCE] });
    api.getDataSourceData.mockResolvedValue({ data: PREVIEW });
    api.updateDataSourceRows.mockResolvedValue({ data: { updated_count: 1 } });
  });

  it("shows real primary-key and field values, with keys read-only", async () => {
    const user = userEvent.setup();
    render(<DataSourceList />);
    await openDrawer(user);
    await openEditor(user);

    const dateInput = await screen.findByDisplayValue("2026-01-01");
    const stageInput = await screen.findByDisplayValue("KNITTING");
    await screen.findByDisplayValue("1027");
    expect(dateInput).toBeDisabled();
    expect(stageInput).toBeDisabled();
  });

  it("stages 1027 -> 1028 as exactly one pending change", async () => {
    const user = userEvent.setup();
    render(<DataSourceList />);
    await openDrawer(user);
    await openEditor(user);

    await setPieces(user, "1027", "1028");
    await stage(user);

    await waitFor(() => expect(pendingCount()).toBe(1));
  });

  it("does not stage when nothing changed", async () => {
    const user = userEvent.setup();
    render(<DataSourceList />);
    await openDrawer(user);
    await openEditor(user);
    await stage(user);

    expect(await screen.findByText(/edit at least one value/i)).toBeInTheDocument();
    expect(pendingCount()).toBe(0);
  });

  it("re-edit shows the staged value; reverting to original removes the change", async () => {
    const user = userEvent.setup();
    render(<DataSourceList />);
    await openDrawer(user);

    await openEditor(user);
    await setPieces(user, "1027", "1028");
    await stage(user);
    await waitFor(() => expect(pendingCount()).toBe(1));

    // Re-open the same row WITHOUT clicking View again.
    await openEditor(user);
    await screen.findByDisplayValue("1028");
    await setPieces(user, "1028", "1027");
    await stage(user);

    await waitFor(() => expect(pendingCount()).toBe(0));
  });

  it("Clear discards staged changes without calling the API", async () => {
    const user = userEvent.setup();
    render(<DataSourceList />);
    await openDrawer(user);

    await openEditor(user);
    await setPieces(user, "1027", "1028");
    await stage(user);
    await waitFor(() => expect(pendingCount()).toBe(1));

    await user.click(screen.getByRole("button", { name: /^clear$/i }));
    await waitFor(() => expect(pendingCount()).toBe(0));
    expect(api.updateDataSourceRows).not.toHaveBeenCalled();
  });

  it("Save batch asks for confirmation before calling the API", async () => {
    const user = userEvent.setup();
    render(<DataSourceList />);
    await openDrawer(user);

    await openEditor(user);
    await setPieces(user, "1027", "1028");
    await stage(user);
    await waitFor(() => expect(pendingCount()).toBe(1));

    await user.click(screen.getByRole("button", { name: /save batch/i }));
    const titles = await screen.findAllByText("Save staged changes?");
    expect(titles.length).toBeGreaterThan(0);
    expect(api.updateDataSourceRows).not.toHaveBeenCalled();

    // The Edit modal is hidden but still mounted, so scope to the newest Cancel
    // (the confirmation dialog appended last).
    const cancelButtons = screen.getAllByRole("button", { name: /^cancel$/i });
    await user.click(cancelButtons[cancelButtons.length - 1]);
    expect(api.updateDataSourceRows).not.toHaveBeenCalled();
  });

  it("sends exactly the changed numeric field and row key on save", async () => {
    const user = userEvent.setup();
    render(<DataSourceList />);
    await openDrawer(user);
    await openEditor(user);

    await setPieces(user, "1027", "1028");
    await stage(user);
    await waitFor(() => expect(pendingCount()).toBe(1));

    // Open the confirmation, then confirm with the dialog's "Save batch".
    const saveButtons = screen.getAllByRole("button", { name: /save batch/i });
    await user.click(saveButtons[saveButtons.length - 1]);
    await screen.findAllByText("Save staged changes?");
    const confirmButtons = screen.getAllByRole("button", { name: /save batch/i });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(api.updateDataSourceRows).toHaveBeenCalledTimes(1));
    const [datasourceId, updates] = api.updateDataSourceRows.mock.calls[0];
    expect(datasourceId).toBe(1);
    expect(updates).toEqual([
      {
        key: { production_date: "2026-01-01", stage: "KNITTING" },
        changes: { pieces_completed: 1028 },
      },
    ]);
    expect(typeof updates[0].changes.pieces_completed).toBe("number");
  });
});
