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
      bank: [{ id: "opp_money_3", name: "$3M", kind: "money", value: 3 }],
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
      bank: [
        { id: "opp_money_10", name: "$10M", kind: "money", value: 10 },
        { id: "opp_money_4", name: "$4M", kind: "money", value: 4 },
      ],
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
      bank: [{ id: "opp_money_8", name: "$8M", kind: "money", value: 8 }],
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

const fivePlayerState: InspectorState = {
  ...playableState,
  version: 99,
  opponents: [
    {
      id: "P2",
      name: "Rival Two",
      hand_size: 3,
      bank: [{ id: "rival_two_money", name: "$1M", kind: "money", value: 1 }],
      bank_value: 1,
      completed_sets: 0,
      properties: {
        red: [{ id: "r1", name: "R1", kind: "property", value: 1, color: "red" }],
      },
    },
    {
      id: "P3",
      name: "Rival Three",
      hand_size: 4,
      bank: [{ id: "rival_three_money", name: "$2M", kind: "money", value: 2 }],
      bank_value: 2,
      completed_sets: 0,
      properties: {},
    },
    {
      id: "P4",
      name: "Rival Four",
      hand_size: 2,
      bank: [],
      bank_value: 0,
      completed_sets: 0,
      properties: {},
    },
    {
      id: "P5",
      name: "Rival Five",
      hand_size: 5,
      bank: [{ id: "rival_five_money", name: "$3M", kind: "money", value: 3 }],
      bank_value: 3,
      completed_sets: 1,
      properties: {},
    },
  ],
};

/** P1 is still the turn clock "current" player, but P2 is the active responder. Human P1 must wait. */
const viewerP1CurrentButP2Responds: InspectorState = {
  game_id: "game_respond_p2",
  version: 5,
  status: "active",
  turn: 4,
  phase: "respond",
  current_player_id: "P1",
  active_player_id: "P2",
  winner_id: null,
  deck_count: 20,
  discard_count: 2,
  discard_top: { id: "d1", name: "Discard", kind: "money", value: 1 },
  viewer: {
    player_id: "P1",
    actions_taken: 0,
    actions_left: 2,
    discard_required: 0,
    hand: [],
    bank: [],
    properties: {},
  },
  opponents: [
    {
      id: "P2",
      name: "AI Broker",
      hand_size: 2,
      bank: [],
      bank_value: 0,
      completed_sets: 0,
      properties: {},
    },
  ],
  pending: {
    kind: "payment",
    actor_id: "P1",
    target_id: "P2",
    respond_player_id: "P2",
    amount: 3,
    source_card_name: "Rent",
    reason: "P2 may respond with Just Say No",
    negated: false,
  },
  legal_actions: [],
  last_action: {
    player_id: "P1",
    payload: { type: "PlayRent" },
  },
  timeline: [],
};

describe("PlayTable", () => {
  test("shows AI turn and disables actions when viewer is not the active player", () => {
    const onChoose = vi.fn();
    const onRunAi = vi.fn();
    render(
      <PlayTable
        state={viewerP1CurrentButP2Responds}
        onChoose={onChoose}
        onRunAi={onRunAi}
      />
    );

    const table = screen.getByRole("region", { name: "Prototype play table" });
    expect(within(table).getByText("AI TURN")).toBeInTheDocument();
    const controls = within(table).getByLabelText("Board controls");
    expect(within(controls).getByText("AI is resolving the table.")).toBeInTheDocument();

    fireEvent.click(within(controls).getByRole("button", { name: /RUN AI UNTIL YOUR TURN/i }));
    expect(onRunAi).toHaveBeenCalled();
    expect(onChoose).not.toHaveBeenCalled();
  });

  test("renders board-first landmarks, pile mapping, and primary actions", () => {
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
    expect(within(table).getByLabelText("Opponent seats")).toHaveAttribute("data-opponent-count", "1");
    const board = within(table).getByRole("region", { name: "Card table" });
    const center = within(table).getByRole("region", { name: "Board center" });
    const handDock = within(table).getByRole("region", { name: "Hand dock" });
    expect(within(board).getByLabelText("Your bank")).toHaveTextContent("YOUR BANK");
    expect(within(board).getByLabelText("Your properties")).toHaveTextContent("YOUR PROPERTIES");
    expect(within(handDock).getByText("YOUR HAND (3)")).toBeInTheDocument();
    expect(within(handDock).getByLabelText("Your hand")).toHaveAttribute("data-hand-count", "3");
    expect(within(table).queryByText("PIXEL PROPERTY DEAL")).not.toBeInTheDocument();
    expect(within(table).getByText("YOUR TURN")).toBeInTheDocument();
    expect(within(table).getByText("TURN 7")).toBeInTheDocument();
    expect(within(table).getByText("2 ACTIONS LEFT")).toBeInTheDocument();
    expect(within(table).queryByText(/Version/)).not.toBeInTheDocument();
    expect(within(table).queryByRole("button", { name: /Refresh/i })).not.toBeInTheDocument();

    expect(within(table).getByText("99")).toBeInTheDocument();
    const piles = within(center).getByLabelText("Draw and discard piles");
    expect(piles).toHaveAttribute("data-layout", "side-by-side");
    expect(within(piles).getByText("DRAW PILE")).toBeInTheDocument();
    expect(within(piles).getByText("DISCARD")).toBeInTheDocument();
    expect(within(center).getByText("ACTIONS 1/3")).toBeInTheDocument();

    expect(within(table).getByText("Bank $6M")).toBeInTheDocument();
    expect(within(table).getByText("Deal Breaker")).toBeInTheDocument();
    expect(within(table).getAllByText(/BLUE/i).length).toBeGreaterThan(0);
    expect(within(table).getByText("AI Broker")).toBeInTheDocument();
    expect(within(table).getByText("Hand 4")).toBeInTheDocument();
    expect(within(table).getByText(/P2 charged rent/i)).toBeInTheDocument();

    fireEvent.click(within(table).getByRole("button", { name: "Draw +2 cards" }));
    expect(onChoose).toHaveBeenCalledWith({ type: "DrawCards" });

    const primarySlot = within(center).getByLabelText("Board controls").querySelector(".board-controls__primary");
    expect(primarySlot).not.toBeNull();
    expect(primarySlot).toHaveAttribute("data-placement", "table-bottom-right");
    expect(primarySlot?.contains(within(table).getByRole("button", { name: "END TURN" }))).toBe(true);

    fireEvent.click(within(table).getByRole("button", { name: "END TURN" }));

    expect(onChoose).toHaveBeenCalledWith({ type: "EndTurn" });
  });

  test("shows selected-card actions in an anchored menu above the hand card", () => {
    render(
      <PlayTable
        state={playableState}
        onChoose={() => undefined}
        onRunAi={() => undefined}
      />
    );

    const table = screen.getByRole("region", { name: "Prototype play table" });
    const handDock = within(table).getByRole("region", { name: "Hand dock" });

    fireEvent.click(within(handDock).getByRole("button", { name: /Deal Breaker/i }));
    const panel = within(handDock).getByRole("menu", {
      name: /Actions for Deal Breaker/i,
    });

    expect(handDock.contains(panel)).toBe(true);
    expect(panel.closest(".play-hand__item--selected")).not.toBeNull();
    expect(within(panel).getByRole("menuitem", { name: /View card details/i })).toBeInTheDocument();
    expect(within(table).getByText(/P2 charged rent/i)).toBeInTheDocument();
    expect(within(table).getByText(/P2 played rent/i)).toBeInTheDocument();
    expect(within(table).getByRole("button", { name: "END TURN" })).toBeInTheDocument();
  });

  test("routes hand card action panel choices through matching legal actions", () => {
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
    fireEvent.click(within(table).getByRole("menuitem", { name: /Play to Bank/i }));
    expect(onChoose).toHaveBeenLastCalledWith({ type: "BankCard", card_id: "deal_breaker" });

    fireEvent.click(within(table).getByRole("button", { name: /Deal Breaker/i }));
    fireEvent.click(within(table).getByRole("menuitem", { name: /Use Action/i }));
    expect(onChoose).toHaveBeenLastCalledWith({ type: "PlayActionCard", card_id: "deal_breaker" });

    fireEvent.click(within(table).getByRole("button", { name: /BLUE property/i }));
    fireEvent.click(within(table).getByRole("menuitem", { name: /Play as Property/i }));
    expect(onChoose).toHaveBeenLastCalledWith({
      type: "PlayProperty",
      card_id: "boardwalk_hand",
      color: "blue",
    });
  });

  test("opens a dimmed card detail overlay from the selected-card menu", () => {
    render(
      <PlayTable
        state={playableState}
        onChoose={() => undefined}
        onRunAi={() => undefined}
      />
    );

    const table = screen.getByRole("region", { name: "Prototype play table" });

    fireEvent.click(within(table).getByRole("button", { name: /Deal Breaker/i }));
    fireEvent.click(within(table).getByRole("menuitem", { name: /View card details/i }));
    const dialog = within(table).getByRole("dialog", { name: /Card details for Deal Breaker/i });

    expect(dialog).toHaveTextContent("Deal Breaker");
    expect(dialog).toHaveTextContent("$5M");
    expect(table.querySelector(".play-overlay-scrim")).toBeInTheDocument();
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
    const piles = within(table).getByRole("region", { name: "Board center" });
    expect(within(piles).getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  test("hand with more than four cards sets dense layout data attribute", () => {
    const fiveCardHand: InspectorState = {
      ...playableState,
      viewer: {
        ...playableState.viewer!,
        hand: [
          ...playableState.viewer!.hand,
          { id: "c4", name: "Card Four", kind: "money", value: 1 },
          { id: "c5", name: "Card Five", kind: "money", value: 1 },
        ],
      },
    };
    render(<PlayTable state={fiveCardHand} onChoose={() => undefined} onRunAi={() => undefined} />);
    const handRegion = screen.getByLabelText("Your hand");
    expect(handRegion).toHaveAttribute("data-hand-count", "5");
    expect(handRegion).toHaveAttribute("data-hand-dense", "true");
    expect(handRegion).toHaveAttribute("data-hand-spread", "fan");
    expect(handRegion.querySelectorAll(".play-card--fanned").length).toBe(5);
  });

  test("hand with four or fewer cards omits dense layout flag", () => {
    render(<PlayTable state={playableState} onChoose={() => undefined} onRunAi={() => undefined} />);
    const handRegion = screen.getByLabelText("Your hand");
    expect(handRegion).toHaveAttribute("data-hand-count", "3");
    expect(handRegion).not.toHaveAttribute("data-hand-dense");
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
    expect(longCard).toHaveAttribute("title", expect.stringContaining("International Ultra Mega Deal Breaker Deluxe Edition"));

    fireEvent.click(longCard);
    const panel = within(table).getByRole("menu", {
      name: /Actions for International Ultra Mega Deal Breaker Deluxe Edition/i,
    });
    expect(within(panel).getByText("Use International Ultra Mega Deal Breaker Deluxe Edition")).toBeInTheDocument();

    const propertyCards = within(table).getByLabelText("Your properties").querySelectorAll(".play-card--compact");
    expect(propertyCards.length).toBeGreaterThanOrEqual(6);
    for (const card of propertyCards) {
      expect(card).toHaveAttribute("title");
      expect(card.querySelector(".play-card__name")).not.toBeNull();
    }
  });

  test("renders four opponent seats and core table zones for a 5-player game", () => {
    render(<PlayTable state={fivePlayerState} onChoose={() => undefined} onRunAi={() => undefined} />);
    const table = screen.getByRole("region", { name: "Prototype play table" });
    const opponentRail = within(table).getByLabelText("Opponent seats");
    expect(opponentRail).toHaveAttribute("data-opponent-count", "4");
    expect(table.querySelectorAll(".opponent-seat").length).toBe(4);
    expect(within(table).getByText("Rival Two")).toBeInTheDocument();
    expect(within(table).getByText("Rival Five")).toBeInTheDocument();
    expect(within(table).queryByLabelText("Action zone")).not.toBeInTheDocument();
    expect(within(table).getByLabelText("Draw and discard piles")).toBeInTheDocument();
  });

  test("opponent bank and property summaries open detail overlays", () => {
    render(<PlayTable state={playableState} onChoose={() => undefined} onRunAi={() => undefined} />);
    const table = screen.getByRole("region", { name: "Prototype play table" });

    fireEvent.click(within(table).getByRole("button", { name: /AI Broker bank/i }));
    expect(within(table).getByRole("dialog", { name: /AI Broker bank/i })).toHaveTextContent("$3M");

    fireEvent.click(within(table).getByRole("button", { name: /Close details/i }));
    fireEvent.click(within(table).getByRole("button", { name: /AI Broker properties/i }));
    const dialog = within(table).getByRole("dialog", { name: /AI Broker properties/i });
    expect(dialog).toHaveTextContent("RED");
    expect(dialog).toHaveTextContent("$3M");
  });
});
