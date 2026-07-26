import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "./SettingsPage";

const getRagConfiguration = vi.fn();

vi.mock("../api/client", () => ({
  getRagConfiguration: (...args: unknown[]) => getRagConfiguration(...args),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    getRagConfiguration.mockReset();
  });

  it("replaces the loading state with an actionable error when the API fails", async () => {
    getRagConfiguration.mockRejectedValue(new Error("Backend is unavailable."));

    render(<SettingsPage />);

    expect(await screen.findByText("Configuration unavailable")).toBeInTheDocument();
    expect(screen.getByText("Backend is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText("Loading configuration…")).not.toBeInTheDocument();
  });
});
