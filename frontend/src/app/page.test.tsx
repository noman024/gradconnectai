import { render, screen } from "@testing-library/react";
import HomePage from "./page";

describe("HomePage", () => {
  it("renders the main hero title and primary actions", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", {
        name: /find the right supervisor, faster\./i,
        level: 1,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: /start with your profile/i }),
    ).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /view matches/i })).toBeInTheDocument();
  });
});

