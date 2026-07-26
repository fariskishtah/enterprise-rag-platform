import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders document and media lifecycle states", () => {
    const { rerender } = render(<StatusBadge status="ready_for_chat" />);
    expect(screen.getByText("Ready for chat")).toBeInTheDocument();

    rerender(<StatusBadge status="transcribing" />);
    expect(screen.getByText("Transcribing")).toBeInTheDocument();
  });
});
