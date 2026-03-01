import asyncio
import random
from pathlib import Path

import pygame

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 540
FPS = 60

PLAYER_WIDTH = 50
PLAYER_HEIGHT = 60
PLAYER_SPEED = 320
STARTING_LIVES = 3

BULLET_WIDTH = 10
BULLET_HEIGHT = 20
BULLET_SPEED = 500

ENEMY_WIDTH = 50
ENEMY_HEIGHT = 60
ENEMY_SPEED = 120
ENEMY_SPAWN_INTERVAL = 2.0

HIT_REWARD = 100
COLLISION_PENALTY = 50

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BG = (16, 18, 30)
PLAYER_COLOR = (64, 190, 255)
BULLET_COLOR = (255, 230, 120)
ENEMY_COLOR = (255, 110, 110)
BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path(".")
ASSET_DIR = BASE_DIR / "1hrfps_assets"


def spawn_enemy(enemies):
    enemy_x = random.randint(0, SCREEN_WIDTH - ENEMY_WIDTH)
    enemies.append(pygame.Rect(enemy_x, -ENEMY_HEIGHT, ENEMY_WIDTH, ENEMY_HEIGHT))


def draw_text(surface, font, text, x, y, color=WHITE):
    surface.blit(font.render(text, True, color), (x, y))


def load_sprite(filename, size):
    try:
        image = pygame.image.load(ASSET_DIR / filename).convert_alpha()
        return pygame.transform.smoothscale(image, size)
    except Exception:
        return None


def resolve_asset_dir():
    candidates = [
        ASSET_DIR,
        Path("1hrfps_assets"),
    ]
    for candidate in candidates:
        if (candidate / "bg.png").exists():
            return candidate
    return candidates[0]


def reset_game():
    player = pygame.Rect(
        SCREEN_WIDTH // 2 - PLAYER_WIDTH // 2,
        SCREEN_HEIGHT - PLAYER_HEIGHT - 10,
        PLAYER_WIDTH,
        PLAYER_HEIGHT,
    )
    return {
        "player": player,
        "bullets": [],
        "enemies": [],
        "score": 0,
        "lives": STARTING_LIVES,
        "game_over": False,
        "game_over_message": "Game Over",
        "enemy_timer": 0.0,
    }


async def main():
    pygame.init()
    pygame.display.set_caption("One Hour Shooter")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    ui_font = pygame.font.SysFont("arial", 24)
    title_font = pygame.font.SysFont("arial", 56, bold=True)

    global ASSET_DIR
    ASSET_DIR = resolve_asset_dir()

    bg_image = load_sprite("bg.png", (SCREEN_WIDTH, SCREEN_HEIGHT))
    player_sprite = load_sprite("player.png", (PLAYER_WIDTH, PLAYER_HEIGHT))
    enemy_sprite = load_sprite("enemy.png", (ENEMY_WIDTH, ENEMY_HEIGHT))
    if enemy_sprite is not None:
        enemy_sprite = pygame.transform.flip(enemy_sprite, False, True)
    bullet_sprite = load_sprite("bullet.png", (BULLET_WIDTH, BULLET_HEIGHT))

    state = reset_game()
    player_x = float(state["player"].x)
    running = True

    while running:
        delta = min(clock.tick(FPS) / 1000.0, 1 / 20)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and not state["game_over"]:
                    player = state["player"]
                    bullet = pygame.Rect(
                        player.centerx - BULLET_WIDTH // 2,
                        player.top - 5,
                        BULLET_WIDTH,
                        BULLET_HEIGHT,
                    )
                    state["bullets"].append(bullet)
                elif event.key == pygame.K_r and state["game_over"]:
                    state = reset_game()
                    player_x = float(state["player"].x)
                elif event.key == pygame.K_q:
                    state["game_over"] = True
                    state["game_over_message"] = "Quit"

        keys = pygame.key.get_pressed()
        if not state["game_over"]:
            move_direction = int(keys[pygame.K_RIGHT] or keys[pygame.K_d]) - int(
                keys[pygame.K_LEFT] or keys[pygame.K_a]
            )
            player_x += move_direction * PLAYER_SPEED * delta
            player_x = max(0.0, min(player_x, float(SCREEN_WIDTH - PLAYER_WIDTH)))
            state["player"].x = int(player_x)

            for bullet in state["bullets"][:]:
                bullet.y -= int(BULLET_SPEED * delta)
                if bullet.bottom < 0:
                    state["bullets"].remove(bullet)

            state["enemy_timer"] += delta
            if state["enemy_timer"] >= ENEMY_SPAWN_INTERVAL:
                spawn_enemy(state["enemies"])
                state["enemy_timer"] = 0.0

            for enemy in state["enemies"][:]:
                enemy.y += int(ENEMY_SPEED * delta)
                if enemy.top > SCREEN_HEIGHT:
                    state["enemies"].remove(enemy)

            for bullet in state["bullets"][:]:
                hit_enemy = next(
                    (enemy for enemy in state["enemies"] if bullet.colliderect(enemy)),
                    None,
                )
                if hit_enemy is not None:
                    state["bullets"].remove(bullet)
                    state["enemies"].remove(hit_enemy)
                    state["score"] += HIT_REWARD

            for enemy in state["enemies"][:]:
                if enemy.colliderect(state["player"]):
                    state["enemies"].remove(enemy)
                    state["score"] = max(0, state["score"] - COLLISION_PENALTY)
                    state["lives"] -= 1
                    if state["lives"] <= 0:
                        state["game_over"] = True
                        state["game_over_message"] = "Game Over"
                    break

        if bg_image is not None:
            screen.blit(bg_image, (0, 0))
        else:
            screen.fill(BG)

        if player_sprite is not None:
            screen.blit(player_sprite, state["player"])
        else:
            pygame.draw.rect(screen, PLAYER_COLOR, state["player"], border_radius=6)

        for bullet in state["bullets"]:
            if bullet_sprite is not None:
                screen.blit(bullet_sprite, bullet)
            else:
                pygame.draw.rect(screen, BULLET_COLOR, bullet, border_radius=3)

        for enemy in state["enemies"]:
            if enemy_sprite is not None:
                screen.blit(enemy_sprite, enemy)
            else:
                pygame.draw.rect(screen, ENEMY_COLOR, enemy, border_radius=6)

        draw_text(screen, ui_font, f"Score: {state['score']}", 10, 8)
        draw_text(screen, ui_font, f"Lives: {state['lives']}", 10, 36)
        draw_text(screen, ui_font, "Move: A/D or Arrow Keys", 10, 72)
        draw_text(screen, ui_font, "Shoot: Space", 10, 100)
        draw_text(screen, ui_font, "Quit: Q  |  Restart: R", 10, 128)

        if state["game_over"]:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            screen.blit(overlay, (0, 0))

            title = title_font.render(state["game_over_message"], True, WHITE)
            subtitle = ui_font.render(f"Final Score: {state['score']}", True, WHITE)
            prompt = ui_font.render("Press R to Restart", True, WHITE)

            screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50)))
            screen.blit(
                subtitle,
                subtitle.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 6)),
            )
            screen.blit(
                prompt,
                prompt.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40)),
            )

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
