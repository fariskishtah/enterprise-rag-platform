import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";

vi.mock("../api/client", () => ({
  getRagConfiguration: vi.fn().mockResolvedValue(null),
  logoutSession: vi.fn().mockResolvedValue(undefined),
}));

describe("AppShell", () => {
  it("presents the fixed workspace label as status rather than a dead button", () => {
    render(<AppShell><p>Page content</p></AppShell>);

    expect(screen.getByLabelText("Current workspace: Local intelligence")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Current workspace: Local intelligence" }),
    ).not.toBeInTheDocument();
  });
});
