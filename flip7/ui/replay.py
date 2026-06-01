"""Pygame-based replay viewer for a recorded Flip 7 game log."""

import sys
from dataclasses import dataclass, replace as _replace
import pygame
from ..engine.state import GameState, PlayerStatus
from ..engine.cards import ModifierOp, ActionType, NumberCard

# ── Window dimensions ─────────────────────────────────────────────────────────

W, H = 1280, 720

HEADER_H   = 54
CONTROLS_H = 52
EVENT_H    = 68
MAIN_TOP   = HEADER_H
MAIN_BOT   = H - CONTROLS_H - EVENT_H
MAIN_H     = MAIN_BOT - MAIN_TOP

# ── Palette ───────────────────────────────────────────────────────────────────

BG            = ( 22,  27,  34)
HEADER_BG     = ( 15,  20,  30)
EVENT_BG      = ( 18,  23,  32)
STATUS_BAR    = ( 20,  25,  35)
DIVIDER       = ( 50,  60,  80)

PANEL_ACTIVE  = ( 38,  50,  70)
PANEL_STAYED  = ( 32,  60,  42)
PANEL_BUSTED  = ( 65,  32,  32)
PANEL_FROZEN  = ( 32,  48,  75)

BORDER_ACTIVE = ( 80, 120, 200)
BORDER_STAYED = ( 80, 180, 100)
BORDER_BUSTED = (200,  80,  80)
BORDER_FROZEN = ( 80, 140, 220)

TEXT_BRIGHT   = (230, 230, 230)
TEXT_NORMAL   = (180, 180, 180)
TEXT_DIM      = (110, 110, 110)
TEXT_YELLOW   = (255, 210,  50)
TEXT_GREEN    = (100, 210, 100)
TEXT_RED      = (220,  80,  80)
TEXT_BLUE     = (120, 170, 240)

CARD_NUM_BG      = (240, 240, 220)
CARD_NUM_TEXT    = ( 20,  20,  20)
CARD_BUST_BG     = (240, 130, 130)  # duplicate / incoming bust card
CARD_MOD_ADD_BG  = (150, 210, 155)
CARD_MOD_MUL_BG  = (155, 155, 225)
CARD_ACTION_BG   = (225, 195, 120)
CARD_TEXT        = ( 20,  20,  20)
CARD_BORDER      = ( 60,  60,  60)

CARD_W,  CARD_H  = 42, 56
CARD_GAP         =  5
CHIP_W,  CHIP_H  = 54, 26
CHIP_GAP         =  5
ACTION_W         = 82


# ── Display frames (log expansion) ───────────────────────────────────────────

@dataclass
class _DisplayFrame:
    state: GameState
    note: str = ""  # if non-empty, shown in event log instead of auto-diff


def _expand_log(log: list[GameState]) -> list[_DisplayFrame]:
    """Return display frames, inserting synthetic pause-frames for bust cards
    and action cards so the player can see each drawn card before its effect."""
    if not log:
        return []
    frames: list[_DisplayFrame] = [_DisplayFrame(state=log[0])]
    for i in range(1, len(log)):
        for syn_state, note in _make_intermediates(log[i - 1], log[i]):
            frames.append(_DisplayFrame(state=syn_state, note=note))
        frames.append(_DisplayFrame(state=log[i]))
    return frames


def _make_intermediates(prev: GameState, curr: GameState) -> list[tuple[GameState, str]]:
    """Synthetic frames to insert between prev and curr, with their event-log notes."""
    if prev.round_state is None or curr.round_state is None:
        return []

    prs, crs = prev.round_state, curr.round_state
    result: list[tuple[GameState, str]] = []
    verb = "dealt" if prs.phase == "deal" else "drew"

    # Case 1 — Bust: show the duplicate card in the player's hand before the bust lands.
    # We mark it via bust_card_value on an otherwise-ACTIVE player state so the
    # renderer can highlight it in red.
    for pid in range(curr.num_players):
        pp = prs.player_states[pid]
        cp = crs.player_states[pid]
        if (pp.status == PlayerStatus.ACTIVE and
                cp.status == PlayerStatus.BUSTED and
                cp.bust_card_value is not None):
            syn_p = _replace(pp,
                             number_cards=pp.number_cards + (NumberCard(value=cp.bust_card_value),),
                             bust_card_value=cp.bust_card_value)
            new_ps = list(prs.player_states)
            new_ps[pid] = syn_p
            syn_state = _replace(prev, round_state=_replace(prs, player_states=tuple(new_ps)))
            result.append((syn_state, f"P{pid} {verb} #{cp.bust_card_value} — duplicate!"))

    # Case 2 — Action card (Freeze / FlipThree): show the card sitting in the
    # player's hand for one frame before it moves to the action queue.
    if len(crs.action_queue) > len(prs.action_queue):
        for card, actor in crs.action_queue[len(prs.action_queue):]:
            if card.type in (ActionType.FREEZE, ActionType.FLIP_THREE):
                ap = prs.player_states[actor]
                syn_ap = _replace(ap, action_cards=ap.action_cards + (card,))
                new_ps = list(prs.player_states)
                new_ps[actor] = syn_ap
                syn_state = _replace(prev, round_state=_replace(prs, player_states=tuple(new_ps)))
                result.append((syn_state, f"P{actor} {verb} {card.type.value}"))

    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def replay_game(log: list[GameState], title: str = "Flip 7 — Replay",
                player_names: list[str] | None = None) -> None:
    """Step through a recorded game log in a pygame window.

    Controls:
      ←/→ or A/D    step back / forward
      Space / N      step forward
      P              auto-play toggle
      + / −          speed up / slow down auto-play
      Home / End     jump to first / last step
      Q / Escape     quit
    """
    try:
        import pygame  # noqa: F401
    except ImportError:
        sys.exit("pygame is required for visualization.  Run: pip install flip7[ui]")

    pygame.init()
    pygame.display.set_caption(title)
    screen = pygame.display.set_mode((W, H))
    clock  = pygame.time.Clock()

    fonts  = _load_fonts()
    frames = _expand_log(log)
    total  = len(frames)

    idx       = 0
    auto      = False
    auto_ms   = 800
    last_auto = 0

    running = True
    while running:
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                k = event.key
                if k in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif k in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_n, pygame.K_d):
                    idx = min(idx + 1, total - 1)
                    last_auto = now
                elif k in (pygame.K_LEFT, pygame.K_a):
                    idx = max(idx - 1, 0)
                elif k == pygame.K_p:
                    auto = not auto
                    last_auto = now
                elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    auto_ms = max(100, auto_ms - 100)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    auto_ms = min(3000, auto_ms + 200)
                elif k == pygame.K_HOME:
                    idx = 0
                elif k == pygame.K_END:
                    idx = total - 1

        if auto and (now - last_auto) >= auto_ms:
            if idx < total - 1:
                idx += 1
                last_auto = now
            else:
                auto = False

        frame      = frames[idx]
        prev_frame = frames[idx - 1] if idx > 0 else None

        screen.fill(BG)
        _render(screen, fonts, frame.state,
                prev_frame.state if prev_frame else None,
                idx, total, auto, auto_ms, note=frame.note,
                player_names=player_names)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


# ── Font loading ──────────────────────────────────────────────────────────────

def _load_fonts() -> dict:
    candidates = ["Menlo", "Consolas", "DejaVu Sans Mono", "monospace", None]
    def _font(size, bold=False):
        for name in candidates:
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                if f:
                    return f
            except Exception:
                continue
        return pygame.font.Font(None, size)

    return {
        "big":   _font(22, bold=True),
        "med":   _font(17),
        "small": _font(14),
        "tiny":  _font(12),
    }


# ── Top-level render ──────────────────────────────────────────────────────────

def _render(screen, fonts, state, prev, idx, total, auto, auto_ms, note="", player_names=None):
    _draw_header(screen, fonts, state, idx, total)

    if state.round_state is not None:
        _draw_players(screen, fonts, state, player_names)
    else:
        _draw_between_rounds(screen, fonts, state)

    if note:
        lines = [note]
    elif prev is not None:
        lines = _describe_change(prev, state)
    else:
        lines = []
    _draw_event_log(screen, fonts, lines)

    _draw_controls(screen, fonts, auto, auto_ms)


# ── Header bar ────────────────────────────────────────────────────────────────

def _draw_header(screen, fonts, state: GameState, idx: int, total: int):
    pygame.draw.rect(screen, HEADER_BG, (0, 0, W, HEADER_H))
    pygame.draw.line(screen, DIVIDER, (0, HEADER_H - 1), (W, HEADER_H - 1))

    blit = screen.blit
    y = 15

    title = fonts["big"].render("FLIP  7", True, TEXT_YELLOW)
    blit(title, (16, y))

    parts = [f"Round {state.round_number}"]
    if state.round_state:
        parts.append(f"Phase: {state.round_state.phase}")
        parts.append(f"Deck: {state.round_state.deck_remaining}")
    parts.append(f"Step {idx + 1}/{total}")

    x = 140
    for part in parts:
        s = fonts["med"].render(part, True, TEXT_NORMAL)
        blit(s, (x, y + 1))
        x += s.get_width() + 28

    score_str = "  ".join(f"P{i}: {v}" for i, v in enumerate(state.cumulative_scores))
    ss = fonts["med"].render(score_str, True, TEXT_BRIGHT)
    blit(ss, (W - ss.get_width() - 16, y + 1))


# ── Player panels ─────────────────────────────────────────────────────────────

_PANEL_COLORS = {
    PlayerStatus.ACTIVE: (PANEL_ACTIVE,  BORDER_ACTIVE),
    PlayerStatus.STAYED: (PANEL_STAYED,  BORDER_STAYED),
    PlayerStatus.BUSTED: (PANEL_BUSTED,  BORDER_BUSTED),
    PlayerStatus.FROZEN: (PANEL_FROZEN,  BORDER_FROZEN),
}

_STATUS_LABELS = {
    PlayerStatus.ACTIVE: ("ACTIVE", TEXT_BLUE),
    PlayerStatus.STAYED: ("STAYED", TEXT_GREEN),
    PlayerStatus.BUSTED: ("BUSTED", TEXT_RED),
    PlayerStatus.FROZEN: ("FROZEN", TEXT_BLUE),
}


def _draw_players(screen, fonts, state: GameState, player_names=None):
    rs   = state.round_state
    n    = state.num_players
    gap  = 8
    pw   = (W - gap * (n + 1)) // n
    ph   = MAIN_H - 16
    top  = MAIN_TOP + 8

    for i, ps in enumerate(rs.player_states):
        x = gap + i * (pw + gap)
        bg, border = _PANEL_COLORS[ps.status]
        pygame.draw.rect(screen, bg,     (x, top, pw, ph), border_radius=8)
        pygame.draw.rect(screen, border, (x, top, pw, ph), width=2, border_radius=8)
        _draw_player_contents(screen, fonts, state, ps, x, top, pw, ph, player_names)


def _draw_player_contents(screen, fonts, state, ps, px, py, pw, ph, player_names=None):
    ix = px + 10       # inner x
    cy = py + 10       # current y cursor

    # --- Heading row ---
    heading = fonts["med"].render(f"Player {ps.player_id}", True, TEXT_BRIGHT)
    screen.blit(heading, (ix, cy))
    cy += heading.get_height() + 2
    if player_names and ps.player_id < len(player_names):
        ts = fonts["tiny"].render(f"({player_names[ps.player_id]})", True, TEXT_DIM)
        screen.blit(ts, (ix, cy))
        cy += ts.get_height() + 4
    else:
        cy += 4

    label, lc = _STATUS_LABELS[ps.status]
    ls = fonts["small"].render(label, True, lc)
    screen.blit(ls, (px + pw - ls.get_width() - 10, py + 12))  # right-aligned with heading row

    # Cumulative score
    total = state.cumulative_scores[ps.player_id]
    ts = fonts["small"].render(f"Total: {total}", True, TEXT_NORMAL)
    screen.blit(ts, (ix, cy))
    cy += ts.get_height() + 8

    # Divider
    _, border = _PANEL_COLORS[ps.status]
    pygame.draw.line(screen, border, (px + 6, cy), (px + pw - 6, cy))
    cy += 8

    max_w = pw - 20

    # --- Number cards ---
    # bust_card_value on an ACTIVE player signals a synthetic pause frame:
    # the duplicate is shown in red so the player can see it before the bust lands.
    dup_val = ps.bust_card_value if ps.status == PlayerStatus.ACTIVE else None
    if ps.number_cards:
        _section_label(screen, fonts, "Numbers", ix, cy)
        cy += fonts["tiny"].get_height() + 3
        cy = _draw_number_cards(screen, fonts, ps.number_cards, ix, cy, max_w, duplicate_value=dup_val)
        cy += 6

    # --- Modifier cards ---
    if ps.modifier_cards:
        _section_label(screen, fonts, "Modifiers", ix, cy)
        cy += fonts["tiny"].get_height() + 3
        cy = _draw_chip_row(screen, fonts, ps.modifier_cards, "mod", ix, cy)
        cy += 6

    # --- Action cards held (Second Chance) ---
    if ps.action_cards:
        _section_label(screen, fonts, "Actions", ix, cy)
        cy += fonts["tiny"].get_height() + 3
        cy = _draw_chip_row(screen, fonts, ps.action_cards, "action", ix, cy)

    # --- Sum pinned to bottom ---
    if ps.status == PlayerStatus.BUSTED:
        bust_s = fonts["med"].render("BUSTED — 0 pts", True, TEXT_RED)
        screen.blit(bust_s, (ix, py + ph - bust_s.get_height() - 10))
    else:
        sum_text = f"Sum: {ps.current_sum()}"
        color = TEXT_YELLOW if ps.has_flip7() else TEXT_BRIGHT
        if ps.has_flip7():
            sum_text += "  ★ FLIP 7!"
        ss = fonts["med"].render(sum_text, True, color)
        screen.blit(ss, (ix, py + ph - ss.get_height() - 10))


def _section_label(screen, fonts, text, x, y):
    s = fonts["tiny"].render(text, True, TEXT_DIM)
    screen.blit(s, (x, y))


def _draw_number_cards(screen, fonts, cards, x, y, max_w, duplicate_value=None) -> int:
    per_row = max(1, (max_w + CARD_GAP) // (CARD_W + CARD_GAP))
    cx, cy  = x, y
    seen: set[int] = set()
    for i, card in enumerate(sorted(cards, key=lambda c: c.value)):
        if i > 0 and i % per_row == 0:
            cx = x
            cy += CARD_H + CARD_GAP
        is_dup = duplicate_value is not None and card.value == duplicate_value and card.value in seen
        bg = CARD_BUST_BG if is_dup else CARD_NUM_BG
        seen.add(card.value)
        _draw_card_rect(screen, fonts["med"], bg, cx, cy, CARD_W, CARD_H,
                        str(card.value), CARD_NUM_TEXT)
        cx += CARD_W + CARD_GAP
    return cy + CARD_H


def _draw_chip_row(screen, fonts, cards, kind, x, y) -> int:
    cx = x
    for card in cards:
        if kind == "mod":
            bg    = CARD_MOD_MUL_BG if card.op == ModifierOp.MULTIPLY else CARD_MOD_ADD_BG
            label = f"x{card.value}" if card.op == ModifierOp.MULTIPLY else f"+{card.value}"
            w = CHIP_W
        else:
            bg    = CARD_ACTION_BG
            label = {
                ActionType.SECOND_CHANCE: "2nd Ch.",
                ActionType.FREEZE:        "Freeze",
                ActionType.FLIP_THREE:    "Flip 3",
            }[card.type]
            w = ACTION_W
        _draw_card_rect(screen, fonts["small"], bg, cx, y, w, CHIP_H, label, CARD_TEXT)
        cx += w + CHIP_GAP
    return y + CHIP_H


def _draw_card_rect(screen, font, bg, x, y, w, h, text, text_color, radius=5):
    pygame.draw.rect(screen, bg,          (x, y, w, h), border_radius=radius)
    pygame.draw.rect(screen, CARD_BORDER, (x, y, w, h), width=1, border_radius=radius)
    s  = font.render(text, True, text_color)
    tx = x + (w - s.get_width())  // 2
    ty = y + (h - s.get_height()) // 2
    screen.blit(s, (tx, ty))


# ── Between-round screen ──────────────────────────────────────────────────────

def _draw_between_rounds(screen, fonts, state: GameState):
    mid_x = W // 2
    mid_y = MAIN_TOP + MAIN_H // 2

    if state.round_number == 0:
        msg = "Game starting…"
    else:
        msg = f"End of Round {state.round_number}"

    ms = fonts["big"].render(msg, True, TEXT_YELLOW)
    screen.blit(ms, (mid_x - ms.get_width() // 2, mid_y - 22))

    score_str = "  ".join(f"P{i}: {v}" for i, v in enumerate(state.cumulative_scores))
    ss = fonts["med"].render(score_str, True, TEXT_BRIGHT)
    screen.blit(ss, (mid_x - ss.get_width() // 2, mid_y + 16))


# ── Event log strip ───────────────────────────────────────────────────────────

def _draw_event_log(screen, fonts, lines: list[str]):
    pygame.draw.rect(screen, EVENT_BG, (0, MAIN_BOT, W, EVENT_H))
    pygame.draw.line(screen, DIVIDER,  (0, MAIN_BOT), (W, MAIN_BOT))
    y = MAIN_BOT + 8
    for line in lines[:3]:
        s = fonts["small"].render(line, True, TEXT_NORMAL)
        screen.blit(s, (16, y))
        y += s.get_height() + 5


# ── Controls footer ───────────────────────────────────────────────────────────

_BINDINGS = [
    ("← →",   "step"),
    ("Space",  "forward"),
    ("P",      "auto"),
    ("+ −",    "speed"),
    ("Home/End","jump"),
    ("Q",      "quit"),
]


def _draw_controls(screen, fonts, auto: bool, auto_ms: int):
    pygame.draw.rect(screen, STATUS_BAR, (0, H - CONTROLS_H, W, CONTROLS_H))
    pygame.draw.line(screen, DIVIDER, (0, H - CONTROLS_H), (W, H - CONTROLS_H))

    x = 16
    y = H - CONTROLS_H + 14
    for key, desc in _BINDINGS:
        ks = fonts["small"].render(key, True, TEXT_YELLOW)
        ds = fonts["tiny"].render(f" {desc}", True, TEXT_DIM)
        screen.blit(ks, (x, y))
        screen.blit(ds, (x + ks.get_width(), y + 3))
        x += ks.get_width() + ds.get_width() + 18

    auto_str = f"AUTO: {'ON' if auto else 'OFF'}  {auto_ms}ms/step"
    asurf = fonts["small"].render(auto_str, True, TEXT_GREEN if auto else TEXT_DIM)
    screen.blit(asurf, (W - asurf.get_width() - 16, y))


# ── Change description ────────────────────────────────────────────────────────

def _describe_change(prev: GameState, curr: GameState) -> list[str]:
    """Return up to 3 human-readable strings describing what changed."""
    lines: list[str] = []

    if prev.round_number != curr.round_number:
        lines.append(f"Round {curr.round_number} begins  (dealer: P{curr.dealer_idx})")
        return lines

    if curr.cumulative_scores != prev.cumulative_scores:
        gains = [
            f"P{i} +{curr.cumulative_scores[i] - prev.cumulative_scores[i]}"
            f" → {curr.cumulative_scores[i]}"
            for i in range(curr.num_players)
            if curr.cumulative_scores[i] != prev.cumulative_scores[i]
        ]
        lines.append("Round scored:  " + "   ".join(gains))
        return lines

    prs, crs = prev.round_state, curr.round_state
    if prs is None or crs is None:
        return lines

    if prs.phase != crs.phase:
        lines.append(f"Deal complete — main phase begins")
        return lines

    verb = "dealt" if crs.phase == "deal" else "drew"

    # Collect "plays" lines first so cause appears before effect (e.g. "P0 plays Freeze" → "P1 Frozen")
    cause_lines: list[str] = []
    if len(crs.action_queue) < len(prs.action_queue):
        for card, actor in prs.action_queue[:len(prs.action_queue) - len(crs.action_queue)]:
            cause_lines.append(f"P{actor} plays {card.type.value}")

    for pid in range(curr.num_players):
        pp, cp = prs.player_states[pid], crs.player_states[pid]

        if pp.status != cp.status:
            label = {
                PlayerStatus.STAYED: f"P{pid} STAYED  (sum {cp.current_sum()})",
                PlayerStatus.BUSTED: (
                    f"P{pid} BUSTED — duplicate #{cp.bust_card_value}"
                    if cp.bust_card_value else f"P{pid} BUSTED"
                ),
                PlayerStatus.FROZEN: f"P{pid} FROZEN  (sum {cp.current_sum()})",
            }.get(cp.status, f"P{pid} → {cp.status.value}")
            lines.append(label)

        new_nums = (
            set(c.value for c in cp.number_cards) -
            set(c.value for c in pp.number_cards)
        )
        for v in sorted(new_nums):
            hand = [c.value for c in sorted(cp.number_cards, key=lambda c: c.value)]
            lines.append(f"P{pid} {verb} #{v}  hand={hand}  sum={cp.current_sum()}")
            if cp.has_flip7():
                lines.append(f"★ P{pid} FLIP 7!  round score = {cp.current_sum()}")

        new_mods = cp.modifier_cards[len(pp.modifier_cards):]
        for m in new_mods:
            s = f"x{m.value}" if m.op == ModifierOp.MULTIPLY else f"+{m.value}"
            lines.append(f"P{pid} {verb} modifier {s}  sum={cp.current_sum()}")

        new_acs = cp.action_cards[len(pp.action_cards):]
        for a in new_acs:
            lines.append(f"P{pid} received {a.type.value}")

        if len(cp.action_cards) < len(pp.action_cards):
            pp_sc = sum(1 for a in pp.action_cards if a.type == ActionType.SECOND_CHANCE)
            cp_sc = sum(1 for a in cp.action_cards if a.type == ActionType.SECOND_CHANCE)
            if cp_sc < pp_sc:
                lines.append(f"P{pid} used SECOND_CHANCE — saved from bust")

    if len(crs.action_queue) > len(prs.action_queue):
        for card, actor in crs.action_queue[len(prs.action_queue):]:
            # If the card was in the actor's action_cards in prev (synthetic pause frame),
            # say "played" rather than "drew" to avoid repeating the draw message.
            was_shown = any(a.type == card.type for a in prs.player_states[actor].action_cards)
            if was_shown:
                lines.append(f"P{actor} played {card.type.value} → queued")
            else:
                lines.append(f"P{actor} drew {card.type.value} — queued")

    return (cause_lines + lines) or ["—"]
