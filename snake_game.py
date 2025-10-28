"""Aurora Snake - a polished Snake game with menus, animations, and customization."""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pygame

Vec2 = Tuple[int, int]


@dataclass
class Settings:
    """Runtime configuration that can be adjusted from the settings screen."""

    grid_width: int = 22
    grid_height: int = 16
    move_speed: float = 6.0  # moves per second
    enable_sound: bool = True
    theme_index: int = 0

    def clamp(self) -> None:
        self.grid_width = max(12, min(40, self.grid_width))
        self.grid_height = max(10, min(30, self.grid_height))
        self.move_speed = max(3.0, min(14.0, self.move_speed))
        self.theme_index = max(0, min(len(THEMES) - 1, self.theme_index))

    @property
    def cell_size(self) -> int:
        base_size = 36
        max_width = 1280
        max_height = 860
        return max(
            18,
            min(
                base_size,
                max_width // self.grid_width,
                max_height // self.grid_height,
            ),
        )

    @property
    def window_size(self) -> Tuple[int, int]:
        padding = 160
        cell = self.cell_size
        return (self.grid_width * cell + padding, self.grid_height * cell + padding)


@dataclass
class Theme:
    name: str
    background_top: Tuple[int, int, int]
    background_bottom: Tuple[int, int, int]
    snake_head: Tuple[int, int, int]
    snake_body: Tuple[int, int, int]
    food_primary: Tuple[int, int, int]
    accent: Tuple[int, int, int]


THEMES: Sequence[Theme] = (
    Theme(
        "Aurora",
        (17, 24, 39),
        (59, 130, 246),
        (248, 250, 252),
        (165, 243, 252),
        (239, 68, 68),
        (217, 249, 157),
    ),
    Theme(
        "Sunset",
        (255, 126, 95),
        (254, 180, 123),
        (39, 39, 42),
        (74, 222, 128),
        (125, 211, 252),
        (30, 64, 175),
    ),
    Theme(
        "Cosmic",
        (30, 27, 75),
        (109, 40, 217),
        (236, 72, 153),
        (244, 114, 182),
        (165, 243, 252),
        (250, 204, 21),
    ),
)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


def generate_tone(frequency: float, duration_ms: int, volume: float = 0.5) -> pygame.mixer.Sound:
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)
    amplitude = int(32767 * volume)
    buffer = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        sample = int(amplitude * math.sin(2 * math.pi * frequency * t))
        buffer += sample.to_bytes(2, byteorder="little", signed=True)
    return pygame.mixer.Sound(buffer=bytes(buffer))


class Snake:
    def __init__(self, grid_width: int, grid_height: int):
        start_x = grid_width // 2
        start_y = grid_height // 2
        self.segments: List[Vec2] = [(start_x, start_y + i) for i in range(3)]
        self.last_positions: List[Vec2] = list(self.segments)
        self.direction: Vec2 = (0, -1)
        self.pending_direction: Vec2 = (0, -1)
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.grow_segments = 0

    def set_direction(self, direction: Vec2) -> None:
        if direction == self.direction:
            return
        if direction[0] == -self.direction[0] and direction[1] == -self.direction[1]:
            return
        self.pending_direction = direction

    def move(self) -> None:
        self.direction = self.pending_direction
        head_x, head_y = self.segments[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)
        self.last_positions = list(self.segments)
        self.segments.insert(0, new_head)
        if self.grow_segments > 0:
            self.grow_segments -= 1
        else:
            self.segments.pop()

    def collided(self) -> bool:
        head = self.segments[0]
        if not (0 <= head[0] < self.grid_width and 0 <= head[1] < self.grid_height):
            return True
        if head in self.segments[1:]:
            return True
        return False

    def grow(self) -> None:
        self.grow_segments += 1


class Food:
    def __init__(self, grid_width: int, grid_height: int):
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.position: Vec2 = (0, 0)

    def reposition(self, occupied: Sequence[Vec2]) -> None:
        free_cells = [
            (x, y)
            for x in range(self.grid_width)
            for y in range(self.grid_height)
            if (x, y) not in occupied
        ]
        if not free_cells:
            self.position = (-1, -1)
            return
        self.position = random.choice(free_cells)


class SnakeGameApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.font.init()
        try:
            pygame.mixer.init()
            self.audio_available = True
        except pygame.error:
            self.audio_available = False

        self.settings = Settings()
        self.theme: Theme = THEMES[self.settings.theme_index]
        self.window = pygame.display.set_mode(self.settings.window_size, pygame.RESIZABLE)
        pygame.display.set_caption("Aurora Snake")
        self.clock = pygame.time.Clock()

        self.font_large = pygame.font.SysFont("Segoe UI", 96, bold=True)
        self.font_medium = pygame.font.SysFont("Segoe UI", 48, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 28)

        self.state: str = "menu"
        self.wave_offset = 0.0

        self.snake: Optional[Snake] = None
        self.food: Optional[Food] = None
        self.score = 0
        self.high_score = 0
        self.move_timer = 0.0
        self.move_progress = 0.0
        self.transition_alpha = 0.0

        self.menu_buttons: List[Tuple[str, pygame.Rect, Callable[[], None]]] = []

        self.sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self._prepare_sounds()

    # ------------------------------------------------------------------
    # Sound helpers
    # ------------------------------------------------------------------

    def _prepare_sounds(self) -> None:
        if not self.audio_available:
            self.sounds = {"eat": None, "bump": None}
            return
        try:
            self.sounds["eat"] = generate_tone(660, 120, 0.35)
            self.sounds["bump"] = generate_tone(110, 280, 0.45)
        except pygame.error:
            self.sounds = {"eat": None, "bump": None}

    def play_sound(self, name: str) -> None:
        if not self.settings.enable_sound:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def start_game(self) -> None:
        self.settings.clamp()
        self.theme = THEMES[self.settings.theme_index % len(THEMES)]
        self.window = pygame.display.set_mode(self.settings.window_size, pygame.RESIZABLE)
        self.snake = Snake(self.settings.grid_width, self.settings.grid_height)
        self.food = Food(self.settings.grid_width, self.settings.grid_height)
        self.food.reposition(self.snake.segments)
        self.score = 0
        self.move_timer = 0.0
        self.move_progress = 0.0
        self.transition_alpha = 255.0
        self.state = "playing"

    def show_menu(self) -> None:
        self.state = "menu"
        self.transition_alpha = 0.0

    def show_settings(self) -> None:
        self.state = "settings"

    def show_game_over(self) -> None:
        self.state = "gameover"
        self.high_score = max(self.high_score, self.score)
        self.transition_alpha = 255.0

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_events(self, events: Sequence[pygame.event.Event]) -> bool:
        for event in events:
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.VIDEORESIZE:
                self.window = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.state == "playing":
                    self.show_menu()
                elif self.state in {"menu", "settings"}:
                    return False
                elif self.state == "gameover":
                    self.show_menu()

        if self.state == "menu":
            self.handle_menu_events(events)
        elif self.state == "settings":
            self.handle_settings_events(events)
        elif self.state == "playing":
            self.handle_playing_events(events)
        elif self.state == "gameover":
            self.handle_gameover_events(events)
        return True

    def handle_menu_events(self, events: Sequence[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_game()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for _, rect, action in self.menu_buttons:
                    if rect.collidepoint(event.pos):
                        action()
                        break

    def handle_settings_events(self, events: Sequence[pygame.event.Event]) -> None:
        previous_size = self.settings.window_size
        theme_changed = False
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key in (pygame.K_LEFTBRACKET, pygame.K_LEFT):
                self.settings.grid_width -= 1
            elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_RIGHT):
                self.settings.grid_width += 1
            elif event.key in (pygame.K_COMMA, pygame.K_DOWN):
                self.settings.grid_height -= 1
            elif event.key in (pygame.K_PERIOD, pygame.K_UP):
                self.settings.grid_height += 1
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.settings.move_speed -= 0.5
            elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                self.settings.move_speed += 0.5
            elif event.key == pygame.K_s:
                self.settings.enable_sound = not self.settings.enable_sound
            elif event.key == pygame.K_t:
                self.settings.theme_index = (self.settings.theme_index + 1) % len(THEMES)
                theme_changed = True
            elif event.key == pygame.K_RETURN:
                self.start_game()
            self.settings.clamp()
        if theme_changed:
            self.theme = THEMES[self.settings.theme_index % len(THEMES)]
        if self.settings.window_size != previous_size:
            self.window = pygame.display.set_mode(self.settings.window_size, pygame.RESIZABLE)

    def handle_playing_events(self, events: Sequence[pygame.event.Event]) -> None:
        if not self.snake:
            return
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key in (pygame.K_UP, pygame.K_w):
                self.snake.set_direction((0, -1))
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.snake.set_direction((0, 1))
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.snake.set_direction((-1, 0))
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.snake.set_direction((1, 0))

    def handle_gameover_events(self, events: Sequence[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self.start_game()

    # ------------------------------------------------------------------
    # Update routines
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.wave_offset = (self.wave_offset + dt * 0.4) % (2 * math.pi)
        if self.transition_alpha > 0:
            self.transition_alpha = max(0.0, self.transition_alpha - dt * 240)
        if self.state == "playing":
            self.update_playing(dt)

    def update_playing(self, dt: float) -> None:
        assert self.snake and self.food
        move_interval = 1.0 / max(2.0, self.settings.move_speed)
        self.move_timer += dt
        moved = False
        while self.move_timer >= move_interval:
            self.move_timer -= move_interval
            self.snake.move()
            moved = True
            if self.snake.collided():
                self.play_sound("bump")
                self.show_game_over()
                return
            if self.snake.segments[0] == self.food.position:
                self.score += 10
                self.snake.grow()
                self.food.reposition(self.snake.segments)
                self.play_sound("eat")
        if moved:
            self.move_progress = 0.0
        else:
            self.move_progress = min(1.0, self.move_timer / move_interval)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def draw(self) -> None:
        self.draw_background(self.window)
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "settings":
            self.draw_settings()
        elif self.state == "playing":
            self.draw_playing()
        elif self.state == "gameover":
            self.draw_playing()
            self.draw_game_over()
        if self.transition_alpha > 0:
            overlay = pygame.Surface(self.window.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(self.transition_alpha)))
            self.window.blit(overlay, (0, 0))
        pygame.display.flip()

    def draw_background(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        theme = self.theme
        phase = (self.wave_offset % (2 * math.pi)) / (2 * math.pi)
        for y in range(height):
            t = y / max(1, height - 1)
            color = lerp_color(theme.background_top, theme.background_bottom, (t + phase) % 1.0)
            pygame.draw.line(surface, color, (0, y), (width, y))
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        for i in range(6):
            phase = self.wave_offset + i * 0.8
            amplitude = height * 0.06 * (1 + i * 0.1)
            color = (*theme.accent, 28)
            points = []
            for x in range(0, width + 40, 40):
                y = height / 2 + math.sin(phase + x / 220) * amplitude
                points.append((x, y))
            if len(points) >= 2:
                pygame.draw.lines(overlay, color, False, points, 4)
        surface.blit(overlay, (0, 0))

    def draw_title(self, surface: pygame.Surface, text: str, center_y: int) -> None:
        theme = self.theme
        base = self.font_large.render(text, True, theme.accent)
        rect = base.get_rect(center=(surface.get_width() // 2, center_y))
        for i in range(5, 0, -1):
            glow = pygame.transform.rotozoom(base, 0, 1 + i * 0.05)
            glow.set_alpha(int(36 * i))
            glow_rect = glow.get_rect(center=rect.center)
            surface.blit(glow, glow_rect)
        surface.blit(base, rect)

    def draw_menu(self) -> None:
        surface = self.window
        self.draw_title(surface, "Aurora Snake", 160)
        instructions = [
            "Press ENTER or click Start to begin",
            "Arrow keys / WASD to move",
            "ESC pauses back to this menu",
        ]
        for i, text in enumerate(instructions):
            info = self.font_small.render(text, True, (240, 244, 255))
            rect = info.get_rect(center=(surface.get_width() // 2, 260 + i * 32))
            surface.blit(info, rect)

        options = [
            ("Start Game", self.start_game),
            ("Settings", self.show_settings),
            ("Quit", lambda: sys.exit(0)),
        ]
        self.menu_buttons = []
        for i, (label, action) in enumerate(options):
            rect = pygame.Rect(0, 0, 320, 68)
            rect.center = (surface.get_width() // 2, 360 + i * 90)
            self.menu_buttons.append((label, rect, action))
            is_hovered = rect.collidepoint(pygame.mouse.get_pos())
            color = self.theme.accent
            if is_hovered:
                color = tuple(min(255, int(c * 1.18)) for c in color)
            pygame.draw.rect(surface, color, rect, border_radius=28)
            text_surf = self.font_medium.render(label, True, (25, 25, 25))
            text_rect = text_surf.get_rect(center=rect.center)
            surface.blit(text_surf, text_rect)

    def draw_settings(self) -> None:
        surface = self.window
        self.draw_title(surface, "Settings", 150)
        options = [
            ("Grid Width", self.settings.grid_width, "[ / ]"),
            ("Grid Height", self.settings.grid_height, ", / ."),
            ("Speed", f"{self.settings.move_speed:.1f}", "- / +"),
            ("Sound", "On" if self.settings.enable_sound else "Off", "S"),
            ("Theme", THEMES[self.settings.theme_index % len(THEMES)].name, "T"),
        ]
        for i, (label, value, hint) in enumerate(options):
            text = f"{label}: {value}"
            value_surface = self.font_medium.render(text, True, (245, 245, 248))
            rect = value_surface.get_rect(center=(surface.get_width() // 2, 250 + i * 70))
            surface.blit(value_surface, rect)
            hint_surface = self.font_small.render(f"[{hint}]", True, (220, 220, 230))
            hint_rect = hint_surface.get_rect(midleft=(rect.right + 20, rect.centery))
            surface.blit(hint_surface, hint_rect)

        prompt = "Press ENTER to start, ESC to return"
        prompt_surface = self.font_small.render(prompt, True, (235, 235, 240))
        prompt_rect = prompt_surface.get_rect(center=(surface.get_width() // 2, surface.get_height() - 120))
        surface.blit(prompt_surface, prompt_rect)

    def draw_grid(self, surface: pygame.Surface) -> None:
        cell = self.settings.cell_size
        grid_w = self.settings.grid_width
        grid_h = self.settings.grid_height
        offset_x = (surface.get_width() - grid_w * cell) // 2
        offset_y = (surface.get_height() - grid_h * cell) // 2
        line_color = tuple(max(0, c - 60) for c in self.theme.background_bottom)
        for x in range(grid_w + 1):
            px = offset_x + x * cell
            pygame.draw.line(surface, line_color, (px, offset_y), (px, offset_y + grid_h * cell), 1)
        for y in range(grid_h + 1):
            py = offset_y + y * cell
            pygame.draw.line(surface, line_color, (offset_x, py), (offset_x + grid_w * cell, py), 1)

    def draw_snake(self, surface: pygame.Surface) -> None:
        assert self.snake
        cell = self.settings.cell_size
        offset_x = (surface.get_width() - self.settings.grid_width * cell) // 2
        offset_y = (surface.get_height() - self.settings.grid_height * cell) // 2
        for index, segment in enumerate(self.snake.segments):
            prev = self.snake.last_positions[index] if index < len(self.snake.last_positions) else segment
            x = lerp(prev[0], segment[0], self.move_progress)
            y = lerp(prev[1], segment[1], self.move_progress)
            rect = pygame.Rect(
                offset_x + x * cell,
                offset_y + y * cell,
                cell,
                cell,
            )
            rect.inflate_ip(-cell * 0.25, -cell * 0.25)
            base_color = lerp_color(self.theme.snake_body, self.theme.snake_head, index / max(1, len(self.snake.segments) - 1))
            if index == 0:
                base_color = self.theme.snake_head
            pygame.draw.rect(surface, base_color, rect, border_radius=12)
        head = self.snake.segments[0]
        glow_rect = pygame.Rect(
            offset_x + head[0] * cell,
            offset_y + head[1] * cell,
            cell,
            cell,
        )
        glow_surface = pygame.Surface((cell, cell), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (*self.theme.snake_head, 90), (cell // 2, cell // 2), cell // 2)
        surface.blit(glow_surface, glow_rect)

    def draw_food(self, surface: pygame.Surface) -> None:
        assert self.food
        cell = self.settings.cell_size
        offset_x = (surface.get_width() - self.settings.grid_width * cell) // 2
        offset_y = (surface.get_height() - self.settings.grid_height * cell) // 2
        fx, fy = self.food.position
        rect = pygame.Rect(
            offset_x + fx * cell,
            offset_y + fy * cell,
            cell,
            cell,
        )
        rect.inflate_ip(-cell * 0.35, -cell * 0.35)
        pygame.draw.rect(surface, self.theme.food_primary, rect, border_radius=18)
        pulsate = (math.sin(pygame.time.get_ticks() / 220) + 1) / 2
        glow_radius = int(rect.width * (1.15 + pulsate * 0.25))
        glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (*self.theme.food_primary, 85), (glow_radius, glow_radius), glow_radius)
        glow_rect = glow_surface.get_rect(center=rect.center)
        surface.blit(glow_surface, glow_rect)

    def draw_hud(self, surface: pygame.Surface) -> None:
        score_surface = self.font_medium.render(f"Score: {self.score}", True, (245, 245, 245))
        surface.blit(score_surface, (40, 40))
        best_surface = self.font_small.render(f"Best: {self.high_score}", True, (225, 225, 230))
        surface.blit(best_surface, (44, 100))

    def draw_playing(self) -> None:
        if not self.snake or not self.food:
            return
        surface = self.window
        self.draw_grid(surface)
        self.draw_snake(surface)
        self.draw_food(surface)
        self.draw_hud(surface)

    def draw_game_over(self) -> None:
        surface = self.window
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((9, 9, 14, 160))
        surface.blit(overlay, (0, 0))
        self.draw_title(surface, "Game Over", surface.get_height() // 2 - 60)
        score_text = self.font_medium.render(f"Score: {self.score}", True, (245, 245, 248))
        score_rect = score_text.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 + 20))
        surface.blit(score_text, score_rect)
        prompt_text = "Press ENTER to try again or ESC for menu"
        prompt_surface = self.font_small.render(prompt_text, True, (235, 235, 240))
        prompt_rect = prompt_surface.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 + 90))
        surface.blit(prompt_surface, prompt_rect)

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(120) / 1000.0
            events = pygame.event.get()
            running = self.handle_events(events)
            self.update(dt)
            self.draw()


def main() -> None:
    app = SnakeGameApp()
    app.run()


if __name__ == "__main__":
    main()
