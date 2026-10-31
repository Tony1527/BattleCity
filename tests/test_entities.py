import pygame
import pytest

import config
from game import entities, geometry


def test_base_starts_at_configured_full_health():
    base = entities.Base()

    assert base.tiles == config.BASE_TILES
    assert base.hp == config.BASE_HP == 3
    assert base.max_hp == config.BASE_HP
    assert base.shield == 0
    assert base.alive is True


def test_base_rect_and_center_cover_its_tiles():
    base = entities.Base()

    rects = [geometry.tile_rect(tx, ty) for tx, ty in config.BASE_TILES]
    expected = pygame.Rect(
        min(rect.left for rect in rects),
        min(rect.top for rect in rects),
        max(rect.right for rect in rects) - min(rect.left for rect in rects),
        max(rect.bottom for rect in rects) - min(rect.top for rect in rects),
    )
    assert base.rect == expected
    assert base.rect.width == 2 * config.TILE
    assert base.rect.height == 2 * config.TILE
    assert base.center == pygame.Vector2(expected.center)


def test_base_shield_absorbs_damage_before_health():
    base = entities.Base()
    base.reset_for_level(shield=2)

    base.take_damage(1)
    assert base.shield == 1
    assert base.hp == 3

    base.take_damage(2)
    assert base.shield == 0
    assert base.hp == 2
    assert base.alive is True


def test_base_take_damage_kills_at_zero_health():
    base = entities.Base()
    base.reset_for_level()

    base.take_damage(config.BASE_HP)

    assert base.hp == 0
    assert base.alive is False

    base.take_damage(5)
    assert base.hp == 0
    assert base.alive is False


def test_base_reset_for_level_restores_health_shield_and_alive():
    base = entities.Base()
    base.take_damage(config.BASE_HP)
    assert base.alive is False

    base.reset_for_level(shield=3)

    assert base.hp == base.max_hp == config.BASE_HP
    assert base.shield == 3
    assert base.alive is True


def test_bullet_update_moves_along_direction_and_keeps_previous_position():
    start = pygame.Vector2(100, 100)
    bullet = entities.Bullet(
        pos=start,
        direction=config.Direction.RIGHT,
        speed=240.0,
        damage=2,
        owner_id=1,
        friendly=False,
    )

    bullet.update(0.5)

    assert bullet.prev_pos == start
    assert bullet.pos == pygame.Vector2(220, 100)
    assert bullet.rect.size == (config.BULLET_SIZE, config.BULLET_SIZE)
    assert bullet.rect.center == (220, 100)


def test_bullet_rect_is_centered_on_position():
    bullet = entities.Bullet(pos=(60, 80), direction=config.Direction.UP)

    assert bullet.rect.width == config.BULLET_SIZE
    assert bullet.rect.height == config.BULLET_SIZE
    assert bullet.rect.center == (60, 80)
    assert bullet.alive is True
    assert bullet.pierce is False


def test_player_starts_with_stats_health_and_hitbox():
    stats = config.PlayerStats(max_hp=4)
    player = entities.Player(0, (120, 240), stats=stats)

    assert player.player_id == 0
    assert player.pos == pygame.Vector2(120, 240)
    assert player.center == pygame.Vector2(120, 240)
    assert player.direction == config.Direction.UP
    assert player.hp == 4
    assert player.alive is True
    assert player.eliminated is False
    assert player.invuln == 0
    assert player.respawn_timer == 0
    assert player.fire_timer == 0
    assert player.grenade_timer == 0
    assert player.laser_timer == 0
    assert player.rect.size == (config.PLAYER_SIZE, config.PLAYER_SIZE)
    assert player.rect.center == (120, 240)


def test_player_take_damage_applies_armor_reduction_and_invulnerability():
    stats = config.PlayerStats(max_hp=100, damage_reduction=0.15)
    player = entities.Player(0, (0, 0), stats=stats)

    destroyed = player.take_damage(100)

    assert destroyed is False
    assert player.hp == 100 - round(100 * (1 - 0.15))
    assert player.invuln == pytest.approx(config.HIT_INVULN)
    assert player.alive is True


def test_player_ignores_damage_while_invulnerable():
    stats = config.PlayerStats(max_hp=10)
    player = entities.Player(1, (0, 0), stats=stats)
    player.take_damage(1)
    health_before = player.hp

    destroyed = player.take_damage(100)

    assert destroyed is False
    assert player.hp == health_before


def test_player_take_damage_returns_true_on_destruction():
    stats = config.PlayerStats(max_hp=1, damage_reduction=0.15)
    player = entities.Player(0, (0, 0), stats=stats)

    destroyed = player.take_damage(10)

    assert destroyed is True
    assert player.hp == 0
    assert player.alive is False


def test_player_damage_never_drops_below_zero():
    stats = config.PlayerStats(max_hp=1)
    player = entities.Player(0, (0, 0), stats=stats)

    player.take_damage(999)

    assert player.hp == 0
    assert player.alive is False


def test_player_revive_restores_health_position_and_respawn_invulnerability():
    stats = config.PlayerStats(max_hp=5)
    player = entities.Player(1, (10, 10), stats=stats)
    player.take_damage(999)
    player.respawn_timer = 2.5

    player.revive((300, 400))

    assert player.pos == pygame.Vector2(300, 400)
    assert player.hp == 5
    assert player.alive is True
    assert player.eliminated is False
    assert player.invuln == pytest.approx(config.RESPAWN_INVULN)
    assert player.respawn_timer == 0


def test_player_update_timers_never_goes_negative():
    player = entities.Player(0, (0, 0))
    player.invuln = 0.1
    player.respawn_timer = 0.2
    player.fire_timer = 0.3
    player.grenade_timer = 0.4
    player.laser_timer = 0.5

    player.update_timers(10.0)

    assert player.invuln == 0
    assert player.respawn_timer == 0
    assert player.fire_timer == 0
    assert player.grenade_timer == 0
    assert player.laser_timer == 0


def test_player_can_shoot_only_when_alive_and_fire_timer_elapsed():
    stats = config.PlayerStats(fire_interval=0.35)
    player = entities.Player(0, (0, 0), stats=stats)

    assert player.can_shoot() is True
    player.shoot_reset()
    assert player.fire_timer == pytest.approx(0.35)
    assert player.can_shoot() is False

    player.update_timers(0.35)
    assert player.can_shoot() is True

    player.alive = False
    assert player.can_shoot() is False
