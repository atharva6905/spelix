import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";
import AccordionItem from "../AccordionItem";

describe("AccordionItem", () => {
  test("renders title and is collapsed by default", () => {
    render(
      <AccordionItem title="Why it works">
        <p>hidden body</p>
      </AccordionItem>,
    );
    const btn = screen.getByRole("button", { name: /why it works/i });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("hidden body")).not.toBeInTheDocument();
  });

  test("renders body when defaultOpen=true", () => {
    render(
      <AccordionItem title="T" defaultOpen>
        <p>visible body</p>
      </AccordionItem>,
    );
    const btn = screen.getByRole("button", { name: /^t$/i });
    expect(btn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("visible body")).toBeInTheDocument();
  });

  test("clicking toggles open/closed", async () => {
    const user = userEvent.setup();
    render(
      <AccordionItem title="T">
        <p>body text</p>
      </AccordionItem>,
    );
    const btn = screen.getByRole("button", { name: /^t$/i });
    await user.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("body text")).toBeInTheDocument();
    await user.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("body text")).not.toBeInTheDocument();
  });

  test("Enter key toggles open/closed", async () => {
    const user = userEvent.setup();
    render(
      <AccordionItem title="T">
        <p>body text</p>
      </AccordionItem>,
    );
    const btn = screen.getByRole("button", { name: /^t$/i });
    btn.focus();
    await user.keyboard("{Enter}");
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });

  test("Space key toggles open/closed", async () => {
    const user = userEvent.setup();
    render(
      <AccordionItem title="T">
        <p>body text</p>
      </AccordionItem>,
    );
    const btn = screen.getByRole("button", { name: /^t$/i });
    btn.focus();
    await user.keyboard(" ");
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });
});
