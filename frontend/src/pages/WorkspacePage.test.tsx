import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspacePage } from "./WorkspacePage";

describe("WorkspacePage", () => {
  it("routes each shortcut to the implemented page and scopes supported workflows", () => {
    render(<WorkspacePage knowledgeBaseId="kb/with spaces" />);

    expect(screen.getByRole("link", { name: /Overview/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(screen.getByRole("link", { name: /Chat/i })).toHaveAttribute(
      "href",
      "/chat?knowledgeBase=kb%2Fwith%20spaces",
    );
    expect(screen.getByRole("link", { name: /Evaluation/i })).toHaveAttribute(
      "href",
      "/evaluation",
    );
  });
});
