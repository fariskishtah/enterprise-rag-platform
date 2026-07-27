import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

const loginUser = vi.fn();
const registerUser = vi.fn();
const getAccessConfiguration = vi.fn();
const getAuthSession = vi.fn();
const loginDemo = vi.fn();

vi.mock("../api/client", () => ({
  loginUser: (...args: unknown[]) => loginUser(...args),
  registerUser: (...args: unknown[]) => registerUser(...args),
  getAccessConfiguration: (...args: unknown[]) => getAccessConfiguration(...args),
  getAuthSession: (...args: unknown[]) => getAuthSession(...args),
  loginDemo: (...args: unknown[]) => loginDemo(...args),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    loginUser.mockReset();
    registerUser.mockReset();
    getAccessConfiguration.mockResolvedValue({
      mode: "accounts",
      session_expiry_minutes: 120,
    });
    getAuthSession.mockResolvedValue({
      mode: "accounts",
      authenticated: false,
      expires_at: null,
      role: null,
    });
    loginDemo.mockReset();
    window.localStorage.clear();
  });

  it("shows authentication failures without granting a fake local session", async () => {
    loginUser.mockRejectedValue(new Error("Incorrect email or password."));
    window.localStorage.setItem("token", "dev-local-token");
    render(<LoginPage />);

    fireEvent.change(await screen.findByLabelText("Email Address"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign in/i }));

    expect(await screen.findByText("Incorrect email or password.")).toBeInTheDocument();
    expect(window.localStorage.getItem("token")).toBeNull();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Sign in/i })).toBeEnabled(),
    );
  });
});
