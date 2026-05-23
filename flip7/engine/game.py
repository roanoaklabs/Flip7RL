import random
from typing import Optional, TYPE_CHECKING
from .cards import BaseCard, NumberCard, ModifierCard, ActionCard, ModifierOp, ActionType
from .deck import Deck, DECK_COMPOSITION
from .state import (
    GameState, RoundState, PlayerRoundState,
    PlayerStatus, HitStay,
)

if TYPE_CHECKING:
    from ..players.base import BasePlayer, GameObservation

WIN_SCORE = 200


class GameEngine:
    def __init__(self, num_players: int, seed: Optional[int] = None):
        self.num_players = num_players
        self.seed = seed
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_game(self) -> tuple[GameState, Deck]:
        """Initialize a fresh game state and shuffled deck."""
        deck = Deck()
        deck.shuffle(seed=self._rng.randint(0, 2**31))
        state = GameState(
            cumulative_scores=tuple(0 for _ in range(self.num_players)),
            round_number=0,
            dealer_idx=0,
            num_players=self.num_players,
            round_state=None,
            t=0,
        )
        return state, deck

    def play_game(self, players: list) -> list[GameState]:
        """Play a full game, return log of all GameState snapshots."""
        state, deck = self.new_game()
        discard: list[BaseCard] = []
        log: list[GameState] = [state]

        while True:
            state, deck, discard, round_log = self.play_round(
                state, deck, discard, players
            )
            log.extend(round_log)

            # Check win condition after round ends
            if max(state.cumulative_scores) >= WIN_SCORE:
                break

        return log

    def play_round(
        self,
        state: GameState,
        deck: Deck,
        discard: list[BaseCard],
        players: list,
    ) -> tuple[GameState, Deck, list[BaseCard], list[GameState]]:
        """Play one complete round. Returns (final_state, deck, discard, log)."""
        log: list[GameState] = []

        # Advance round number and rotate dealer
        new_dealer = (state.dealer_idx + 1) % self.num_players if state.round_number > 0 else state.dealer_idx
        round_number = state.round_number + 1

        # Build initial player round states
        player_states = tuple(
            PlayerRoundState(
                player_id=i,
                number_cards=(),
                modifier_cards=(),
                action_cards=(),
                status=PlayerStatus.ACTIVE,
            )
            for i in range(self.num_players)
        )

        round_state = RoundState(
            player_states=player_states,
            deck_remaining=deck.remaining,
            current_player_idx=new_dealer,
            action_queue=(),
            phase="deal",
        )
        state = GameState(
            cumulative_scores=state.cumulative_scores,
            round_number=round_number,
            dealer_idx=new_dealer,
            num_players=self.num_players,
            round_state=round_state,
            t=state.t + 1,
        )
        log.append(state)

        # --- DEAL PHASE: one card to each active player ---
        state, deck, discard, deal_log = self._deal_initial_cards(state, deck, discard, players)
        log.extend(deal_log)

        # --- MAIN PHASE: players hit/stay in turn order ---
        if not self._is_round_over(state):
            state = self._set_phase(state, "main")
            log.append(state)
            state, deck, discard, main_log = self._run_main_phase(state, deck, discard, players)
            log.extend(main_log)

        # --- End of round: score ---
        state = self._end_round(state)
        log.append(state)

        return state, deck, discard, log

    # ------------------------------------------------------------------
    # Phase helpers
    # ------------------------------------------------------------------

    def _set_phase(self, state: GameState, phase: str) -> GameState:
        rs = state.round_state
        new_rs = RoundState(
            player_states=rs.player_states,
            deck_remaining=rs.deck_remaining,
            current_player_idx=rs.current_player_idx,
            action_queue=rs.action_queue,
            phase=phase,
        )
        return GameState(
            cumulative_scores=state.cumulative_scores,
            round_number=state.round_number,
            dealer_idx=state.dealer_idx,
            num_players=state.num_players,
            round_state=new_rs,
            t=state.t + 1,
        )

    def _deal_initial_cards(
        self, state: GameState, deck: Deck, discard: list[BaseCard], players: list
    ) -> tuple[GameState, Deck, list[BaseCard], list[GameState]]:
        """Deal one card to each active player in turn order (starting from dealer)."""
        log: list[GameState] = []
        dealer = state.dealer_idx
        order = [(dealer + i) % self.num_players for i in range(self.num_players)]

        for pid in order:
            pstate = state.round_state.player_states[pid]
            if pstate.status in (PlayerStatus.FROZEN, PlayerStatus.BUSTED, PlayerStatus.STAYED):
                continue
            # Skip players who already received cards via FLIP_THREE during this deal phase
            if pstate.number_cards or pstate.modifier_cards or pstate.action_cards:
                continue
            state, deck, discard, card_log = self._deal_card_to_player(state, deck, discard, pid, players)
            log.extend(card_log)
            if self._is_round_over(state):
                break

        return state, deck, discard, log

    def _run_main_phase(
        self, state: GameState, deck: Deck, discard: list[BaseCard], players: list
    ) -> tuple[GameState, Deck, list[BaseCard], list[GameState]]:
        """Run the main hit/stay phase until round ends."""
        log: list[GameState] = []

        # Determine turn order starting from dealer
        dealer = state.dealer_idx
        order = [(dealer + i) % self.num_players for i in range(self.num_players)]

        # Cycle through players until round over
        max_iterations = self.num_players * 100  # safety limit
        iteration = 0
        order_idx = 0

        while not self._is_round_over(state) and iteration < max_iterations:
            iteration += 1
            pid = order[order_idx % len(order)]
            order_idx += 1

            pstate = state.round_state.player_states[pid]
            if pstate.status != PlayerStatus.ACTIVE:
                # Skip non-active players
                continue

            # Ask player for decision
            obs = self._make_observation(state, pid)
            players[pid].observe(obs)
            decision = players[pid].decide(obs)

            if decision == HitStay.STAY:
                state = self._apply_stay(state, pid)
                log.append(state)
            else:
                # HIT: deal a card
                state, deck, discard, card_log = self._deal_card_to_player(
                    state, deck, discard, pid, players
                )
                log.extend(card_log)
                players[pid].on_hit_result(self._make_observation(state, pid))

        return state, deck, discard, log

    # ------------------------------------------------------------------
    # Card dealing and resolution
    # ------------------------------------------------------------------

    def _deal_card_to_player(
        self,
        state: GameState,
        deck: Deck,
        discard: list[BaseCard],
        player_id: int,
        players: list,
    ) -> tuple[GameState, Deck, list[BaseCard], list[GameState]]:
        """Draw one card, resolve it for the player, then process action queue."""
        log: list[GameState] = []

        # Reshuffle discard into deck if empty
        if deck.is_empty():
            deck, discard = self._reshuffle_discard(deck, discard)

        card = deck.draw()
        if card is None:
            return state, deck, discard, log

        state, deck, discard, resolve_log = self._resolve_card(
            state, deck, discard, player_id, card, players
        )
        log.extend(resolve_log)

        # Process action queue after resolution
        state, deck, discard, queue_log = self._process_action_queue(
            state, deck, discard, players
        )
        log.extend(queue_log)

        return state, deck, discard, log

    def _resolve_card(
        self,
        state: GameState,
        deck: Deck,
        discard: list[BaseCard],
        player_id: int,
        card: BaseCard,
        players: list,
    ) -> tuple[GameState, Deck, list[BaseCard], list[GameState]]:
        """Handle a newly drawn card for player_id."""
        log: list[GameState] = []
        pstate = state.round_state.player_states[player_id]

        if isinstance(card, NumberCard):
            # Check for duplicate
            if card.value in pstate.unique_number_values():
                # Bust — unless they have Second Chance
                if pstate.has_second_chance():
                    state = self._apply_second_chance(state, player_id, card)
                    discard.append(card)  # discard the duplicate
                    log.append(state)
                else:
                    state = self._apply_bust(state, player_id, card.value)
                    discard.append(card)
                    log.append(state)
            else:
                # Normal number card
                new_numbers = pstate.number_cards + (card,)
                new_pstate = PlayerRoundState(
                    player_id=player_id,
                    number_cards=new_numbers,
                    modifier_cards=pstate.modifier_cards,
                    action_cards=pstate.action_cards,
                    status=pstate.status,
                )
                state = self._update_player(state, player_id, new_pstate)
                log.append(state)

                # Check flip 7
                updated_pstate = state.round_state.player_states[player_id]
                if updated_pstate.has_flip7():
                    # Round ends for all — no further action
                    pass

        elif isinstance(card, ModifierCard):
            new_modifiers = pstate.modifier_cards + (card,)
            new_pstate = PlayerRoundState(
                player_id=player_id,
                number_cards=pstate.number_cards,
                modifier_cards=new_modifiers,
                action_cards=pstate.action_cards,
                status=pstate.status,
            )
            state = self._update_player(state, player_id, new_pstate)
            log.append(state)

        elif isinstance(card, ActionCard):
            if card.type == ActionType.SECOND_CHANCE:
                state, discard, sc_log = self._handle_second_chance_drawn(
                    state, discard, player_id, card, players
                )
                log.extend(sc_log)
            elif card.type == ActionType.FREEZE:
                # Queue it: (card, acting_player_id)
                new_queue = state.round_state.action_queue + ((card, player_id),)
                state = self._update_queue(state, new_queue)
                log.append(state)
            elif card.type == ActionType.FLIP_THREE:
                new_queue = state.round_state.action_queue + ((card, player_id),)
                state = self._update_queue(state, new_queue)
                log.append(state)

        return state, deck, discard, log

    def _handle_second_chance_drawn(
        self,
        state: GameState,
        discard: list[BaseCard],
        player_id: int,
        card: ActionCard,
        players: list,
    ) -> tuple[GameState, list[BaseCard], list[GameState]]:
        """Handle a Second Chance card being drawn."""
        log: list[GameState] = []
        pstate = state.round_state.player_states[player_id]

        if not pstate.has_second_chance():
            # Give it to this player
            new_pstate = PlayerRoundState(
                player_id=player_id,
                number_cards=pstate.number_cards,
                modifier_cards=pstate.modifier_cards,
                action_cards=pstate.action_cards + (card,),
                status=pstate.status,
            )
            state = self._update_player(state, player_id, new_pstate)
            log.append(state)
        else:
            # Already has one — give to another active player without SC
            target = self._find_sc_target(state, exclude=player_id)
            if target is not None:
                tpstate = state.round_state.player_states[target]
                new_tpstate = PlayerRoundState(
                    player_id=target,
                    number_cards=tpstate.number_cards,
                    modifier_cards=tpstate.modifier_cards,
                    action_cards=tpstate.action_cards + (card,),
                    status=tpstate.status,
                )
                state = self._update_player(state, target, new_tpstate)
                log.append(state)
            else:
                # Discard
                discard.append(card)

        return state, discard, log

    def _find_sc_target(self, state: GameState, exclude: int) -> Optional[int]:
        """Find an active player without Second Chance, excluding `exclude`."""
        for pstate in state.round_state.player_states:
            if pstate.player_id == exclude:
                continue
            if pstate.status == PlayerStatus.ACTIVE and not pstate.has_second_chance():
                return pstate.player_id
        return None

    # ------------------------------------------------------------------
    # Action queue processing
    # ------------------------------------------------------------------

    def _process_action_queue(
        self, state: GameState, deck: Deck, discard: list[BaseCard], players: list
    ) -> tuple[GameState, Deck, list[BaseCard], list[GameState]]:
        """Process all pending items in the action queue."""
        log: list[GameState] = []

        while state.round_state.action_queue and not self._is_round_over(state):
            queue = list(state.round_state.action_queue)
            card, acting_player_id = queue.pop(0)
            new_queue = tuple(queue)
            state = self._update_queue(state, new_queue)

            # Find valid targets (active players, not the acting player for Freeze/FlipThree
            # but acting player may target themselves in some interpretations;
            # standard rules: choose any active player)
            active_players = [
                p for p in state.round_state.player_states
                if p.status == PlayerStatus.ACTIVE
            ]

            if not active_players:
                # No valid targets, discard the card
                discard.append(card)
                continue

            # Discard if the acting player is no longer active (e.g. frozen after card was queued)
            acting_pstate = state.round_state.player_states[acting_player_id]
            if acting_pstate.status != PlayerStatus.ACTIVE:
                discard.append(card)
                continue

            # Ask acting player to choose target
            obs = self._make_observation(state, acting_player_id)
            players[acting_player_id].observe(obs)
            target_id = players[acting_player_id].choose_target(card, obs)

            # Validate target
            target_pstate = state.round_state.player_states[target_id]
            if target_pstate.status != PlayerStatus.ACTIVE:
                # Target no longer valid, discard
                discard.append(card)
                continue

            if card.type == ActionType.FREEZE:
                state = self._apply_freeze(state, target_id)
                discard.append(card)
                log.append(state)

            elif card.type == ActionType.FLIP_THREE:
                state, deck, discard, ft_log = self._apply_flip_three(
                    state, deck, discard, target_id, players
                )
                discard.append(card)
                log.extend(ft_log)

        return state, deck, discard, log

    # ------------------------------------------------------------------
    # Action card effects
    # ------------------------------------------------------------------

    def _apply_freeze(self, state: GameState, target_id: int) -> GameState:
        """Bank target's points and mark as FROZEN."""
        pstate = state.round_state.player_states[target_id]
        if pstate.status not in (PlayerStatus.ACTIVE,):
            return state  # Already done, no-op

        new_pstate = PlayerRoundState(
            player_id=target_id,
            number_cards=pstate.number_cards,
            modifier_cards=pstate.modifier_cards,
            action_cards=pstate.action_cards,
            status=PlayerStatus.FROZEN,
        )
        return self._update_player(state, target_id, new_pstate)

    def _apply_flip_three(
        self,
        state: GameState,
        deck: Deck,
        discard: list[BaseCard],
        target_id: int,
        players: list,
    ) -> tuple[GameState, Deck, list[BaseCard], list[GameState]]:
        """Deal 3 cards to target, stop early on bust or flip7."""
        log: list[GameState] = []

        for _ in range(3):
            if self._is_round_over(state):
                break
            tpstate = state.round_state.player_states[target_id]
            if tpstate.status != PlayerStatus.ACTIVE:
                break

            # Reshuffle if needed
            if deck.is_empty():
                deck, discard = self._reshuffle_discard(deck, discard)

            card = deck.draw()
            if card is None:
                break

            state, deck, discard, resolve_log = self._resolve_card(
                state, deck, discard, target_id, card, players
            )
            log.extend(resolve_log)

            # Check if player busted or flip7 after this card
            tpstate = state.round_state.player_states[target_id]
            if tpstate.status == PlayerStatus.BUSTED:
                break
            if tpstate.has_flip7():
                break

        return state, deck, discard, log

    def _apply_second_chance(
        self, state: GameState, player_id: int, duplicate_card: NumberCard
    ) -> GameState:
        """Use Second Chance to save from bust: discard SC and duplicate, player continues."""
        pstate = state.round_state.player_states[player_id]

        # Remove one Second Chance from action_cards
        action_cards = list(pstate.action_cards)
        for i, a in enumerate(action_cards):
            if a.type == ActionType.SECOND_CHANCE:
                action_cards.pop(i)
                break

        new_pstate = PlayerRoundState(
            player_id=player_id,
            number_cards=pstate.number_cards,
            modifier_cards=pstate.modifier_cards,
            action_cards=tuple(action_cards),
            status=pstate.status,  # still active
        )
        return self._update_player(state, player_id, new_pstate)

    def _apply_bust(self, state: GameState, player_id: int, bust_card_value: int | None = None) -> GameState:
        """Mark player as busted."""
        pstate = state.round_state.player_states[player_id]
        new_pstate = PlayerRoundState(
            player_id=player_id,
            number_cards=pstate.number_cards,
            modifier_cards=pstate.modifier_cards,
            action_cards=pstate.action_cards,
            status=PlayerStatus.BUSTED,
            bust_card_value=bust_card_value,
        )
        return self._update_player(state, player_id, new_pstate)

    def _apply_stay(self, state: GameState, player_id: int) -> GameState:
        """Mark player as stayed."""
        pstate = state.round_state.player_states[player_id]
        new_pstate = PlayerRoundState(
            player_id=player_id,
            number_cards=pstate.number_cards,
            modifier_cards=pstate.modifier_cards,
            action_cards=pstate.action_cards,
            status=PlayerStatus.STAYED,
        )
        return self._update_player(state, player_id, new_pstate)

    # ------------------------------------------------------------------
    # Round end
    # ------------------------------------------------------------------

    def _is_round_over(self, state: GameState) -> bool:
        """Check if round end condition is met."""
        if state.round_state is None:
            return True

        players = state.round_state.player_states

        # Condition 1: all players done
        all_done = all(
            p.status in (PlayerStatus.STAYED, PlayerStatus.BUSTED, PlayerStatus.FROZEN)
            for p in players
        )
        if all_done:
            return True

        # Condition 2: any player has Flip 7
        if any(p.has_flip7() for p in players):
            return True

        return False

    def _end_round(self, state: GameState) -> GameState:
        """Compute round scores and update cumulative scores."""
        round_scores = self._calculate_round_scores(state)
        new_cumulative = tuple(
            state.cumulative_scores[i] + round_scores[i]
            for i in range(self.num_players)
        )
        return GameState(
            cumulative_scores=new_cumulative,
            round_number=state.round_number,
            dealer_idx=state.dealer_idx,
            num_players=state.num_players,
            round_state=state.round_state,
            t=state.t + 1,
        )

    def _calculate_round_scores(self, state: GameState) -> tuple:
        """Calculate scores for all players this round. BUSTED players score 0.

        ACTIVE players who achieved Flip 7 also score (the round ended due to flip7).
        """
        scores = []
        for pstate in state.round_state.player_states:
            if pstate.status in (PlayerStatus.STAYED, PlayerStatus.FROZEN):
                scores.append(pstate.current_sum())
            elif pstate.status == PlayerStatus.ACTIVE and pstate.has_flip7():
                # Round ended due to this player's Flip 7 — they score
                scores.append(pstate.current_sum())
            else:
                scores.append(0)
        return tuple(scores)

    # ------------------------------------------------------------------
    # State mutation helpers (produce new immutable states)
    # ------------------------------------------------------------------

    def _update_player(
        self, state: GameState, player_id: int, new_pstate: PlayerRoundState
    ) -> GameState:
        """Return a new GameState with player_id's state replaced."""
        rs = state.round_state
        old_players = list(rs.player_states)
        old_players[player_id] = new_pstate
        new_rs = RoundState(
            player_states=tuple(old_players),
            deck_remaining=rs.deck_remaining,
            current_player_idx=rs.current_player_idx,
            action_queue=rs.action_queue,
            phase=rs.phase,
        )
        return GameState(
            cumulative_scores=state.cumulative_scores,
            round_number=state.round_number,
            dealer_idx=state.dealer_idx,
            num_players=state.num_players,
            round_state=new_rs,
            t=state.t + 1,
        )

    def _update_queue(self, state: GameState, new_queue: tuple) -> GameState:
        """Return a new GameState with updated action queue."""
        rs = state.round_state
        new_rs = RoundState(
            player_states=rs.player_states,
            deck_remaining=rs.deck_remaining,
            current_player_idx=rs.current_player_idx,
            action_queue=new_queue,
            phase=rs.phase,
        )
        return GameState(
            cumulative_scores=state.cumulative_scores,
            round_number=state.round_number,
            dealer_idx=state.dealer_idx,
            num_players=state.num_players,
            round_state=new_rs,
            t=state.t + 1,
        )

    def _update_deck_remaining(self, state: GameState, remaining: int) -> GameState:
        rs = state.round_state
        new_rs = RoundState(
            player_states=rs.player_states,
            deck_remaining=remaining,
            current_player_idx=rs.current_player_idx,
            action_queue=rs.action_queue,
            phase=rs.phase,
        )
        return GameState(
            cumulative_scores=state.cumulative_scores,
            round_number=state.round_number,
            dealer_idx=state.dealer_idx,
            num_players=state.num_players,
            round_state=new_rs,
            t=state.t + 1,
        )

    def _reshuffle_discard(
        self, deck: Deck, discard: list[BaseCard]
    ) -> tuple[Deck, list[BaseCard]]:
        """When deck is empty, reshuffle discard pile into a new deck."""
        if not discard:
            return deck, discard
        new_deck = Deck(cards=discard)
        new_deck.shuffle(seed=self._rng.randint(0, 2**31))
        return new_deck, []

    # ------------------------------------------------------------------
    # Observation builder
    # ------------------------------------------------------------------

    def _make_observation(self, state: GameState, player_id: int):
        """Build a GameObservation for the given player."""
        from ..players.base import GameObservation
        rs = state.round_state
        my_pstate = rs.player_states[player_id]
        other_players = tuple(
            p for p in rs.player_states if p.player_id != player_id
        )
        return GameObservation(
            my_player_id=player_id,
            my_number_cards=my_pstate.number_cards,
            my_modifier_cards=my_pstate.modifier_cards,
            my_action_cards=my_pstate.action_cards,
            my_status=my_pstate.status,
            other_players=other_players,
            cumulative_scores=state.cumulative_scores,
            round_number=state.round_number,
            num_players=state.num_players,
            deck_remaining=rs.deck_remaining,
        )
