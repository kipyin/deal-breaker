import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import type { InspectorState } from "../../api/types";
import { PlayTable } from "./PlayTable";

const playableState: InspectorState = {
  game_id: "game_123",
  version: 12,
  status: "active",
  turn: 7,
  phase: "action",
  current_player_id: "P1",
  active_player_id: "P1",
  winner_id: null,
  deck_count: 99,
  discard_count: 1,
  discard_top: { id: "top1", name: "Top Discard", kind: "money", value: 2 },
  viewer: {
    player_id: "P1",
    actions_taken: 1,
    actions_left: 2,
    discard_required: 0,
    hand: [
      { id: "deal_breaker", name: "Deal Breaker", kind: "action", value: 5 },
      { id: "rent", name: "Rent", kind: "action", value: 3, color: "blue" },
      { id: "boardwalk_hand", name: "Boardwalk", kind: "property", value: 4, color: "blue" },
    ],
    bank: [
      { id: "money_5", name: "$5M", kind: "money", value: 5 },
      { id: "money_1", name: "$1M", kind: "money", value: 1 },
    ],
    properties: {
      blue: [{ id: "boardwalk", name: "Boardwalk", kind: "property", value: 4, color: "blue" }],
    },
  },
  opponents: [
    {
      id: "P2",
      name: "AI Broker",
      hand_size: 4,
      bank_value: 3,
      completed_sets: 0,
      properties: {
        red: [{ id: "kentucky", name: "Kentucky Ave", kind: "property", value: 3, color: "red" }],
      },
    },
  ],
  pending: {
    kind: "rent",
    actor_id: "P2",
    target_id: "P1",
    respond_player_id: "P1",
    amount: 3,
    source_card_name: "Rent",
    reason: "P2 charged rent",
    negated: false,
  },
  legal_actions: [
    {
      id: "bank",
      label: "Bank Deal Breaker",
      payload: { type: "BankCard", card_id: "deal_breaker" },
    },
    {
      id: "action",
      label: "Use Deal Breaker",
      payload: { type: "PlayActionCard", card_id: "deal_breaker" },
    },
    {
      id: "property",
      label: "Play Boardwalk",
      payload: { type: "PlayProperty", card_id: "boardwalk_hand", color: "blue" },
    },
    {
      id: "draw",
      label: "Draw 2 cards",
      payload: { type: "DrawCards" },
    },
    { id: "end", label: "End turn", payload: { type: "EndTurn" } },
  ],
  last_action: {
    player_id: "P2",
    payload: { type: "rent", amount: 3 },
  },
  timeline: [],
};

const densePlayUiStressState: InspectorState = {
  ...playableState,
  version: 44,
  turn: 18,
  deck_count: 7,
  discard_count: 31,
  discard_top: {
    id: "discard_long",
    name: "International Ultra Mega Rent Multicolor Surprise",
    kind: "rent",
    value: 5,
    color: "light_blue",
  },
  viewer: {
    ...playableState.viewer!,
    actions_left: 1,
    hand: [
      {
        id: "stress_long_action",
        name: "International Ultra Mega Deal Breaker Deluxe Edition",
        kind: "action",
        value: 5,
      },
      {
        id: "stress_multicolor_rent",
        name: "Rent Across Every Single Color Group",
        kind: "rent",
        value: 3,
        color: "blue",
      },
      {
        id: "stress_boardwalk",
        name: "Boardwalk With A Very Long Display Name",
        kind: "property",
        value: 4,
        color: "blue",
      },
      { id: "stress_park_place", name: "Park Place", kind: "property", value: 4, color: "blue" },
      {
        id: "stress_wild",
        name: "Wildcard Any Color Property Mega Long Name",
        kind: "wild_property",
        value: 4,
        colors: ["red", "yellow", "green"],
      },
      { id: "stress_house", name: "House", kind: "house", value: 3 },
      { id: "stress_hotel", name: "Hotel", kind: "hotel", value: 4 },
      { id: "stress_money", name: "$10M", kind: "money", value: 10 },
    ],
    bank: [
      { id: "stress_money_10", name: "$10M", kind: "money", value: 10 },
      { id: "stress_money_5", name: "$5M", kind: "money", value: 5 },
      { id: "stress_money_4", name: "$4M", kind: "money", value: 4 },
      { id: "stress_money_3", name: "$3M", kind: "money", value: 3 },
      { id: "stress_money_2", name: "$2M", kind: "money", value: 2 },
      { id: "stress_money_1", name: "$1M", kind: "money", value: 1 },
    ],
    properties: {
      blue: [
        {
          id: "stress_boardwalk_table",
          name: "Boardwalk With A Very Long Display Name",
          kind: "property",
          value: 4,
          color: "blue",
        },
        {
          id: "stress_park_place_table",
          name: "Park Place With Boardwalk-Sized Label",
          kind: "property",
          value: 4,
          color: "blue",
        },
        { id: "stress_blue_house", name: "House", kind: "house", value: 3, color: "blue" },
      ],
      light_blue: [
        {
          id: "stress_oriental",
          name: "Oriental Avenue With Overflow Pressure",
          kind: "property",
          value: 1,
          color: "light_blue",
        },
        {
          id: "stress_vermont",
          name: "Vermont Avenue With Overflow Pressure",
          kind: "property",
          value: 1,
          color: "light_blue",
        },
      ],
      railroad: [
        {
          id: "stress_rail",
          name: "Reading Railroad And Friends",
          kind: "property",
          value: 2,
          color: "railroad",
        },
      ],
    },
  },
  opponents: [
    {
      id: "P2",
      name: "Long Named Opportunistic Investor Bot",
      hand_size: 9,
      bank_value: 14,
      completed_sets: 1,
      properties: {
        red: [
          { id: "stress_red_1", name: "Kentucky Avenue", kind: "property", value: 3, color: "red" },
          { id: "stress_red_2", name: "Indiana Avenue", kind: "property", value: 3, color: "red" },
          { id: "stress_red_3", name: "Illinois Avenue", kind: "property", value: 3, color: "red" },
        ],
        green: [
          { id: "stress_green_1", name: "Pacific Avenue", kind: "property", value: 4, color: "green" },
        ],
      },
    },
    {
      id: "P3",
      name: "Another Very Long Rival Name",
      hand_size: 7,
      bank_value: 8,
      completed_sets: 0,
      properties: {
        yellow: [
          { id: "stress_yellow_1", name: "Atlantic Avenue", kind: "property", value: 3, color: "yellow" },
          { id: "stress_yellow_2", name: "Ventnor Avenue", kind: "property", value: 3, color: "yellow" },
        ],
      },
    },
  ],
  pending: {
    kind: "rent_response",
    actor_id: "P2",
    target_id: "P1",
    respond_player_id: "P1",
    amount: 9,
    source_card_name: "Rent Across Every Single Color Group",
    reason: "Long Named Opportunistic Investor Bot charged a huge multicolor rent",
    negated: false,
  },
  legal_actions: [
    {
      id: "stress_bank",
      label: "Bank International Ultra Mega Deal Breaker Deluxe Edition",
      payload: { type: "BankCard", card_id: "stress_long_action" },
    },
    {
      id: "stress_action",
      label: "Use International Ultra Mega Deal Breaker Deluxe Edition",
      payload: { type: "PlayActionCard", card_id: "stress_long_action" },
    },
    {
      id: "stress_property",
      label: "Play Boardwalk With A Very Long Display Name",
      payload: { type: "PlayProperty", card_id: "stress_boardwalk", color: "blue" },
    },
    { id: "stress_draw", label: "Draw 2 cards", payload: { type: "DrawCards" } },
    { id: "stress_end", label: "End turn", payload: { type: "EndTurn" } },
  ],
  last_action: {
    player_id: "P3",
    payload: { type: "deal_breaker", card_id: "stress_action" },
  },
};

describe("PlayTable", () => {
  test("renders prototype table landmarks, pile mapping, and primary actions", () => {
    const onChoose = vi.fn();
    render(
      <PlayTable
        state={playableState}
        onChoose={onChoose}
        onRunAi={() => undefined}
      />
    );

    const table = screen.getByRole("region", { name: "Prototype play table" });
    expect(table.querySelector(".play-table__inner--prototype")).toBeInTheDocument();
    expect(within(table).getByLabelText("Opponent seats")).toBeInTheDocument();
    expect(within(table).getByLabelText("Your bank")).toHaveTextContent("YOUR BANK");
    expect(within(table).getByLabelText("Your properties")).toHaveTextContent("YOUR PROPERTIES");
    expect(within(table).getByLabelText("Your hand")).toHaveTextContent("YOUR HAND (3)");
    expect(within(table).getByText("PIXEL PROPERTY DEAL")).toBeInTheDocument();
    expect(within(table).getByText("YOUR TURN")).toBeInTheDocument();
    expect(within(table).getByText("TURN 7")).toBeInTheDocument();
    expect(within(table).getByText("2 ACTIONS LEFT")).toBeInTheDocument();
    expect(within(table).queryByText(/Version/)).not.toBeInTheDocument();
    expect(within(table).queryByRole("button", { name: /Refresh/i })).not.toBeInTheDocument();

    expect(within(table).getByText("99")).toBeInTheDocument();
    expect(within(table).getByText("Top Discard")).toBeInTheDocument();
    const piles = within(table).getByLabelText("Draw and discard piles");
    expect(within(piles).getByText("DRAW PILE")).toBeInTheDocument();
    expect(within(piles).getByText("DISCARD")).toBeInTheDocument();

    expect(within(table).getByText("Bank $6M")).toBeInTheDocument();
    expect(within(table).getByText("Deal Breaker")).toBeInTheDocument();
    expect(within(table).getAllByText("Boardwalk").length).toBeGreaterThan(0);
    expect(within(table).getByText("AI Broker")).toBeInTheDocument();
    expect(within(table).getByText("Hand 4")).toBeInTheDocument();
    expect(within(table).getByText("P2 charged rent")).toBeInTheDocument();

    fireEvent.click(within(table).getByRole("button", { name: "Draw +2 cards" }));
    expect(onChoose).toHaveBeenCalledWith({ type: "DrawCards" });

    const primarySlot = within(table).getByLabelText("Action zone").querySelector(".action-zone__primary");
    expect(primarySlot).not.toBeNull();
    expect(primarySlot?.contains(within(table).getByRole("button", { name: "END TURN" }))).toBe(true);

    fireEvent.click(within(table).getByRole("button", { name: "END TURN" }));

    expect(onChoose).toHaveBeenCalledWith({ type: "EndTurn" });
  });

  test("routes hand card popover choices through matching legal actions", () => {
    const onChoose = vi.fn();
    render(
      <PlayTable
        state={playableState}
        onChoose={onChoose}
        onRunAi={() => undefined}
      />
    );

    const table = screen.getByRole("region", { name: "Prototype play table" });

    fireEvent.click(within(table).getByRole("button", { name: /Deal Breaker/i }));
    fireEvent.click(within(table).getByRole("button", { name: /Play to Bank/i }));
    expect(onChoose).toHaveBeenLastCalledWith({ type: "BankCard", card_id: "deal_breaker" });

    fireEvent.click(within(table).getByRole("button", { name: /Deal Breaker/i }));
    fireEvent.click(within(table).getByRole("button", { name: /Use Action/i }));
    expect(onChoose).toHaveBeenLastCalledWith({ type: "PlayActionCard", card_id: "deal_breaker" });

    fireEvent.click(within(table).getByRole("button", { name: /Boardwalk/i }));
    fireEvent.click(within(table).getByRole("button", { name: /Play as Property/i }));
    expect(onChoose).toHaveBeenLastCalledWith({
      type: "PlayProperty",
      card_id: "boardwalk_hand",
      color: "blue",
    });
  });

  test("omitted pile metadata shows honest placeholders, not fake counts", () => {
    const minimal: InspectorState = {
      ...playableState,
      deck_count: undefined,
      discard_count: undefined,
      discard_top: undefined,
    };
    render(<PlayTable state={minimal} onChoose={() => undefined} onRunAi={() => undefined} />);
    const table = screen.getByRole("region", { name: "Prototype play table" });
    const piles = within(table).getByLabelText("Draw and discard piles");
    expect(within(piles).getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  test("dense stress state keeps long card text and selected-card actions discoverable", () => {
    render(
      <PlayTable
        state={densePlayUiStressState}
        onChoose={() => undefined}
        onRunAi={() => undefined}
        flashMessage="Selected card cannot cover table controls"
      />
    );

    const table = screen.getByRole("region", { name: "Prototype play table" });
    const handRegion = within(table).getByLabelText("Your hand");
    expect(handRegion).toHaveAttribute("data-hand-count", "8");
    expect(handRegion).toHaveAttribute("data-hand-dense", "true");
    expect(within(table).getByText("YOUR HAND (8)")).toBeInTheDocument();
    expect(within(table).getByText("Long Named Opportunistic Investor Bot")).toBeInTheDocument();
    expect(within(table).getByText("Another Very Long Rival Name")).toBeInTheDocument();
    expect(within(table).getByText("Bank $25M")).toBeInTheDocument();
    expect(within(table).getByRole("alert")).toHaveTextContent("Selected card cannot cover table controls");

    const longCard = within(table).getByRole("button", {
      name: /International Ultra Mega Deal Breaker Deluxe Edition/i,
    });
    expect(longCard).toHaveAttribute("title", "International Ultra Mega Deal Breaker Deluxe Edition");

    fireEvent.click(longCard);
    const popover = within(table).getByRole("dialog", {
      name: /Actions for International Ultra Mega Deal Breaker Deluxe Edition/i,
    });
    expect(within(popover).getByText("Use International Ultra Mega Deal Breaker Deluxe Edition")).toBeInTheDocument();
    expect(popover).toHaveAttribute("data-placement", "hand");

    const propertyCards = within(table).getByLabelText("Your properties").querySelectorAll(".play-card--compact");
    expect(propertyCards.length).toBeGreaterThanOrEqual(6);
    for (const card of propertyCards) {
      expect(card).toHaveAttribute("title");
      expect(card.querySelector(".play-card__name")).not.toBeNull();
    }
  });
});
