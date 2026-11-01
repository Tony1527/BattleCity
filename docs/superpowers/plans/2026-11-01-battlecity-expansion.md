# Battle City Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add difficulty modes, retry-current-level, terrain hazards, pickups, per-level elites, faster spawns, and Chinese/English UI to the existing two-player pygame tank game.

**Architecture:** Extend the existing `World`/`Game` in place. `DifficultyProfile` centralizes all normal/hell scaling; `RunState` carries progression across level retries; new `Tile.RIVER`/`Tile.BRIDGE` values plus `Trap`/`Pickup` entities own the new world content; `game/i18n.py` owns all visible strings and `Renderer` translates every screen.

**Tech Stack:** Python 3.14, pygame-ce 2.5.x, pytest 9.2.x, fontTools only at font-subset build time.

**Spec:** `docs/superpowers/specs/2026-11-01-battlecity-expansion-design.md`

## Global Constraints

- Python 3.14; pygame-ce 2.5.x; pytest 9.2.x; 1280x720; 60 FPS; 24x13 grid; tile 48.
- Run tests with `.venv/bin/pytest -q`; run the game with `.venv/bin/python main.py`.
- All visible text must go through `game.i18n.tr` after Task 8. No new hardcoded UI strings in `game/render.py` or `game/states.py`.
- All new art is procedural pygame drawing. The only external asset is the OFL-licensed Noto Sans CJK SC font subset under `assets/fonts/`.
- No runtime network access and no runtime fontTools dependency.
- Preserve the existing controls and add only: `Left/Right` on title for difficulty, `L` for language, `Enter` to confirm/retry, `Esc` to pause/quit.
- Every task ends with a passing test command and a commit.
- Keep `DifficultyProfile`, spawn tables, elite tables, trap tables, and pickup tables in `config.py`/`game/difficulty.py`; do not scatter magic numbers through rendering or states.

## Review Focus

These are the five failure modes most likely to bite a player; each gets a test in the owning task.

1. **Retry restores the wrong base state** — a player-elimination retry must keep current base HP/shield; a base-destroyed retry must restore full HP. Test in Task 2.
2. **River validation accepts a disconnected map** — `validate_level` must treat `RIVER` as blocked and `BRIDGE` as passable so the three required routes are real. Test in Task 4.
3. **Traps chain-hold or fail to stop skills** — standing on a re-armed trap must not retrigger, and immobilization must block movement, normal fire, grenade, and laser. Test in Task 5.
4. **Hell multipliers stack incorrectly** — normal enemies, elites, summons, and Boss each use exactly one scaling path. Test in Tasks 1 and 3.
5. **Chinese UI has missing glyphs or overflowing text** — every Chinese translation character must be in the bundled font, and rendered menus must not raise or overflow. Test in Tasks 9 and 10.

---

## File Structure

### New files

- `game/difficulty.py` — `DifficultyProfile`, normal/hell profiles, enemy-spec scaling.
- `game/run.py` — `RunState` snapshot for progression and retry.
- `game/hazards.py` — `Trap` entity and cooldown/trigger logic.
- `game/pickups.py` — `Pickup` entity, kind weights, TTL.
- `game/i18n.py` — `LANGUAGES`, `TEXTS`, `tr`, `all_keys`, required glyph set.
- `assets/fonts/NotoSansCJKsc-Regular-subset.otf` — bundled Chinese font.
- `assets/fonts/OFL.txt` — Noto/SIL OFL license.
- `tools/build_font_subset.py` — regenerate the font subset from a source font.
- `tests/test_difficulty.py`, `tests/test_run_state.py`, `tests/test_elites.py`, `tests/test_terrain.py`, `tests/test_traps.py`, `tests/test_pickups.py`, `tests/test_stim.py`, `tests/test_i18n.py`, `tests/test_fonts.py` — new coverage.

### Modified files

- `config.py` — new tiles, difficulty/spawn/elite/trap/pickup constants, font path.
- `game/levelgen.py` — river/bridge carving, trap placement, river-aware route validation, fallback map.
- `game/world.py` — difficulty scaling, retry constructor params, rivers/bridges collision, traps, pickups, elites, twin laser, stim grenades.
- `game/enemies.py` — scaled specs, multi-elite support, immobilization, elite HP/shield/summon scaling.
- `game/boss.py` — difficulty HP/interval scaling.
- `game/entities.py` — `Base(max_hp=...)`, player timers/immobilization/invincibility.
- `game/skills.py` — laser ignores river/bridge; helper for offset laser origins.
- `game/states.py` — `RunState`, difficulty/language selection, retry flow, language toggle.
- `game/render.py` — new terrain/pickup/HUD drawing and all localized strings.
- `game/upgrades.py` — `Upgrade` uses `name_key`/`desc_key`.
- `tests/test_config.py`, `tests/test_states.py`, `tests/test_integration.py`, `tests/test_world_core.py`, `tests/test_world_combat.py`, `tests/test_enemies.py`, `tests/test_boss.py`, `tests/test_render_smoke.py`, `tests/test_upgrades.py` — update expectations.
- `README.md` — new features, controls, difficulty, language, font license.

---

### Task 1: Difficulty Profiles and Core Scaling

**Files:**
- Create: `game/difficulty.py`
- Modify: `config.py`, `game/world.py`, `game/entities.py`, `game/boss.py`
- Test: `tests/test_difficulty.py`, `tests/test_config.py`, `tests/test_world_core.py`, `tests/test_boss.py`

**Interfaces:**
- Consumes: existing `config.EnemySpec`, `config.SPAWN_INTERVAL`, `config.BASE_HP`, `World.__init__`, `Boss.__init__`, `Base.__init__`.
- Produces:
  - `config.SPAWN_INTERVAL = (4.8, 4.4, 4.0, 3.6, 3.2, 2.8, 2.4, 0.0)`
  - `game.difficulty.DifficultyProfile` with fields `key: str`, `enemy_hp_mult: float`, `enemy_fire_interval_mult: float`, `enemy_attack_range_mult: float`, `spawn_interval_mult: float`, `base_hp: int`, `boss_hp_mult: float`, `boss_interval_mult: float`, `elite_hp_mult: float`, `elite_shield_mult: float`.
  - `game.difficulty.get_profile(key: str) -> DifficultyProfile`
  - `game.difficulty.scaled_enemy_spec(kind: str, profile: DifficultyProfile) -> config.EnemySpec`
  - `World.__init__(..., difficulty: str = "normal")`
  - `Base.__init__(tiles=..., max_hp: int = config.BASE_HP)`
  - `Boss.__init__(pos=None, hp_mult: float = 1.0, interval_mult: float = 1.0)`

- [ ] **Step 1: Write failing difficulty tests**

```python
def test_profiles_match_spec():
    normal = difficulty.get_profile("normal")
    hell = difficulty.get_profile("hell")
    assert normal.base_hp == 3
    assert hell.base_hp == 6
    assert hell.enemy_hp_mult == 1.5
    assert hell.enemy_fire_interval_mult == 0.8
    assert hell.enemy_attack_range_mult == 1.15
    assert hell.spawn_interval_mult == 0.8
    assert hell.boss_hp_mult == 1.5
    assert hell.boss_interval_mult == 0.85

def test_hell_scales_normal_enemy_once():
    spec = difficulty.scaled_enemy_spec("tracker", difficulty.get_profile("hell"))
    assert spec.hp == 3
    assert spec.fire_interval == pytest.approx(1.2)
    assert spec.attack_range == pytest.approx(276.0)

def test_world_uses_difficulty_for_base_and_spawn_interval():
    normal = World(0, seed=1, difficulty="normal")
    hell = World(0, seed=1, difficulty="hell")
    assert normal.base.max_hp == 3
    assert hell.base.max_hp == 6
    assert hell._spawn_interval() == pytest.approx(normal._spawn_interval() * 0.8)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_difficulty.py -v`
Expected: FAIL with missing `game.difficulty` or missing constants.

- [ ] **Step 3: Implement profiles and scaling**

Create `game/difficulty.py` with the dataclass, `NORMAL`, `HELL`, `PROFILES`, `get_profile`, and `scaled_enemy_spec`. Use `dataclasses.replace` and `math.ceil` for HP. Update `config.SPAWN_INTERVAL`, `config.BASE_HP_NORMAL`, `config.BASE_HP_HELL`. Make `World` store `self.difficulty = get_profile(difficulty)`, construct `Base(self.difficulty.base_hp)`, multiply `_spawn_interval()` by `self.difficulty.spawn_interval_mult`, and call `scaled_enemy_spec` when spawning normal enemies. Make `Boss` accept `hp_mult`/`interval_mult` and use scaled HP and timers.

- [ ] **Step 4: Run the focused tests**

Run: `.venv/bin/pytest tests/test_difficulty.py tests/test_config.py tests/test_world_core.py tests/test_boss.py -v`
Expected: PASS after updating old expectations for the new `SPAWN_INTERVAL` and `Boss` signature.

- [ ] **Step 5: Commit**

```bash
git add game/difficulty.py config.py game/world.py game/entities.py game/boss.py tests/test_difficulty.py tests/test_config.py tests/test_world_core.py tests/test_boss.py
git commit -m "feat: add normal and hell difficulty scaling"
```

---

### Task 2: RunState, Retry Current Level, and Title Difficulty Selection

**Files:**
- Create: `game/run.py`
- Modify: `game/states.py`, `game/world.py`, `game/render.py`
- Test: `tests/test_run_state.py`, `tests/test_states.py`

**Interfaces:**
- Consumes: `DifficultyProfile`, `World.__init__(..., difficulty=..., shared_lives=..., base_hp=..., base_shield=...)`.
- Produces:
  - `game.run.RunState` with `run_seed: int`, `difficulty: str`, `language: str`, `level_index: int`, `player_stats: list[config.PlayerStats]`, `upgrade_levels: list[dict[str, int]]`, `shared_lives: int`.
  - `Game.__init__(..., difficulty: str = "normal", language: str = "zh")`.
  - `Game._capture_run_state() -> RunState`
  - `Game._retry_level() -> None`
  - `Game._loss_reason() -> str` returns `"base_destroyed"` or `"both_eliminated"`.
  - `Renderer.draw_title(t: float, difficulty: str = "normal") -> None`.
  - `World.__init__(..., shared_lives: int | None = None, base_hp: int | None = None, base_shield: int | None = None)`.

- [ ] **Step 1: Write failing retry tests**

```python
def test_player_elimination_retry_preserves_upgrades_lives_and_base(game):
    start_playing(game)
    game.world.apply_upgrade(0, "heavy_rounds")
    game.world.shared_lives = 0
    game.world.base.hp = 1
    game.world.base.shield = 2
    game.world.players[0].eliminated = True
    game.world.players[1].eliminated = True
    game.update(1 / 60)
    assert game.state == "gameover"

    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.state == "playing"
    assert game.level_index == 0
    assert game.world.upgrade_levels[0]["heavy_rounds"] == 1
    assert game.world.shared_lives == 0
    assert game.world.base.hp == 1
    assert game.world.base.shield == 2
    assert all(p.alive and not p.eliminated for p in game.world.players)

def test_base_destroyed_retry_restores_full_base(game):
    start_playing(game)
    game.world.base.hp = 0
    game.world.base.alive = False
    game.update(1 / 60)
    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.world.base.alive is True
    assert game.world.base.hp == game.world.base.max_hp
    assert game.world.level_index == 0

def test_gameover_escape_returns_to_title(game):
    start_playing(game)
    game.world.status = "lost"
    game.update(1 / 60)
    game.handle_event(key_event(config.PAUSE_KEY))
    assert game.state == "title"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_run_state.py -v`
Expected: FAIL because `gameover` still starts a fresh run and `RunState` does not exist.

- [ ] **Step 3: Implement RunState and retry**

Create `game/run.py`. In `Game`, keep `difficulty` and `language` fields, capture stats/levels/lives from the current world, and rebuild the same level with the same `_world_seed`. Pass `shared_lives=state.shared_lives`, and for base handling pass `base_hp=current_hp, base_shield=current_shield` when the base is alive, otherwise leave both `None`. Reset players to alive/full by constructing a new `World`. Update `handle_event`: Enter on `gameover` calls `_retry_level`; Esc returns to `title`. Add `Left/Right` on title to toggle `self.difficulty` and pass it to `draw_title`.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_run_state.py tests/test_states.py -v`
Expected: PASS after replacing the old “Enter starts a fresh run” expectation with “Enter retries the current level.”

- [ ] **Step 5: Commit**

```bash
git add game/run.py game/states.py game/world.py game/render.py tests/test_run_state.py tests/test_states.py
git commit -m "feat: retry current level and preserve run progression"
```

---

### Task 3: Elites on Every Level with Scaling Counts

**Files:**
- Modify: `config.py`, `game/enemies.py`, `game/world.py`
- Test: `tests/test_elites.py`, `tests/test_enemies.py`, `tests/test_integration.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `DifficultyProfile`, `World.difficulty`, `make_enemy`.
- Produces:
  - `config.ELITE_COUNTS = (1, 1, 2, 2, 2, 3, 3, 1)`
  - `config.ELITE_SPAWN_INTERVAL = 22.0`, `config.ELITE_RETRY_INTERVAL = 2.0`, `config.ELITE_MAX_ACTIVE = 2`
  - `config.ELITE_HP_BASE = 3`, `config.ELITE_SHIELD_BASE = 12`, `config.ELITE_SUMMON_INTERVAL = 10.0`, `config.ELITE_MAX_SUMMONS = 1`
  - `EliteEnemy.__init__(pos, direction=UP, level_index=0, hp_mult=1.0, shield_mult=1.0, spec=None)`
  - `make_enemy(kind, tile, spec=None, elite_level=0, elite_hp_mult=1.0, elite_shield_mult=1.0)`
  - `World.elite_target_count: int`, `World.elite_spawned_count: int`, `World.elite_spawn_timer: float`, `World._update_elite_spawning(dt: float) -> None`
  - `World.remaining_enemies` includes pending elites.

- [ ] **Step 1: Write failing elite tests**

```python
@pytest.mark.parametrize("level_index", range(config.LEVEL_COUNT))
def test_every_level_has_planned_elites(level_index):
    world = World(level_index, seed=100 + level_index)
    assert world.elite_target_count == config.ELITE_COUNTS[level_index]

def test_early_quota_clear_spawns_pending_elites_immediately():
    world = World(2, seed=3)
    assert world.elite_spawned_count == 1
    world.quota_remaining = 0
    world._update_elite_spawning(0.0)
    assert world.elite_spawned_count == 2

def test_hell_elite_scales_only_with_elite_multiplier():
    world = World(3, seed=4, difficulty="hell")
    elite = next(e for e in world.enemies if e.kind == "elite")
    assert elite.max_hp == math.ceil((3 + 3 // 2) * 1.5)
    assert elite.shield == math.ceil((12 + 3) * 1.5)

def test_boss_level_elite_does_not_block_victory():
    world = World(config.BOSS_LEVEL, seed=5)
    assert world.elite_target_count == 1
    world.boss.alive = False
    world._on_boss_dead()
    assert world.status == "victory"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_elites.py -v`
Expected: FAIL because `elite_target_count` and multi-elite scheduling do not exist.

- [ ] **Step 3: Implement multi-elite scheduling**

Replace the boolean `elite_spawned` with a count. In `_start_level`, set `elite_target_count` from `ELITE_COUNTS`, spawn one immediately, and set the timer to `ELITE_SPAWN_INTERVAL`. Add `_update_elite_spawning(dt)` called from `update` for all levels, including Boss. When `quota_remaining == 0`, set the timer to `0.0`. If the active elite count is at `ELITE_MAX_ACTIVE`, retry after `ELITE_RETRY_INTERVAL`; otherwise spawn and reset to 22 seconds. Update `_check_progression` to require `elite_spawned_count >= elite_target_count` and no living enemies on normal levels. Update `remaining_enemies` to include `elite_target_count - elite_spawned_count`.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_elites.py tests/test_enemies.py tests/test_integration.py tests/test_config.py -v`
Expected: PASS after replacing `ELITE_LEVELS` assertions with per-level counts.

- [ ] **Step 5: Commit**

```bash
git add config.py game/enemies.py game/world.py tests/test_elites.py tests/test_enemies.py tests/test_integration.py tests/test_config.py
git commit -m "feat: spawn scaling elites on every level"
```

---

### Task 4: Rivers, Bridges, and River-Aware Generation

**Files:**
- Modify: `config.py`, `game/levelgen.py`, `game/world.py`, `game/skills.py`
- Test: `tests/test_terrain.py`, `tests/test_config.py`, `tests/test_world_core.py`

**Interfaces:**
- Consumes: existing `Level`, `generate_level`, `validate_level`, `World.find_path`, `World.move_entity`, `compute_laser`.
- Produces:
  - `config.Tile.RIVER = 3`, `config.Tile.BRIDGE = 4`
  - `config.RIVER_BANDS = (0, 1, 1, 1, 2, 2, 2, 0)`, `config.BRIDGE_COUNT = 3`, `config.BRIDGE_WIDTH = 2`
  - `levelgen.is_passable_for_routes` returns false for `STEEL` and `RIVER`; true for `BRIDGE`, `BRICK`, `EMPTY`.
  - `World.find_path` blocks `STEEL` and `RIVER`.
  - `World._rect_collides_tiles` blocks `BRICK`, `STEEL`, `RIVER`.
  - `compute_laser` ignores `RIVER`/`BRIDGE`.

- [ ] **Step 1: Write failing terrain tests**

```python
@pytest.mark.parametrize("level_index", range(config.LEVEL_COUNT))
def test_all_levels_validate_with_rivers(level_index):
    world = World(level_index, seed=2000 + level_index)
    assert validate_level(world.level)
    if config.RIVER_BANDS[level_index] > 0:
        assert any(
            tile == config.Tile.RIVER
            for row in world.grid
            for tile in row
        )
        assert any(
            tile == config.Tile.BRIDGE
            for row in world.grid
            for tile in row
        )
    else:
        assert not any(
            tile == config.Tile.RIVER
            for row in world.grid
            for tile in row
        )

def test_river_blocks_tank_but_not_bullet_or_laser():
    world = World(1, seed=6)
    river = next(
        (tx, ty)
        for ty, row in enumerate(world.grid)
        for tx, tile in enumerate(row)
        if tile == config.Tile.RIVER
    )
    player = world.players[0]
    player.pos = world.tile_center(*river)
    assert world._rect_collides_tiles(player.rect) is True
    bullet = Bullet(player.center, config.Direction.RIGHT)
    bullet.pos = world.tile_center(*river)
    assert world._bullet_hits_wall(bullet) is False

def test_laser_passes_over_bridge_and_river():
    world = World(1, seed=6)
    grid = [
        [config.Tile.EMPTY for _ in range(config.GRID_COLS)]
        for _ in range(config.GRID_ROWS)
    ]
    grid[5][2] = config.Tile.RIVER
    grid[5][3] = config.Tile.BRIDGE
    origin = world.tile_center(2, 5)
    beam = compute_laser(
        origin, config.Direction.RIGHT, 3 * config.TILE, grid
    )
    assert beam.end.x == pytest.approx(origin.x + 3 * config.TILE)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_terrain.py -v`
Expected: FAIL with missing `Tile.RIVER` or routes ignoring water.

- [ ] **Step 3: Implement terrain and generation**

Add the Tile values and constants. In `levelgen`, carve 1-2 horizontal rivers on rows 4..9 for non-Boss levels, place three 2-tile bridges per river, and overwrite that row. Update `is_passable_for_routes` to block `RIVER`. Update `fallback_level` with a river and bridges. In `World`, block river movement/pathfinding and ignore river/bridge in bullet, line-of-sight, laser, and grenade destruction checks.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_terrain.py tests/test_config.py tests/test_world_core.py -v`
Expected: PASS; every level validates and Boss levels contain no river.

- [ ] **Step 5: Commit**

```bash
git add config.py game/levelgen.py game/world.py game/skills.py tests/test_terrain.py tests/test_config.py tests/test_world_core.py
git commit -m "feat: add rivers and bridges with river-aware generation"
```

---

### Task 5: Traps and Immobilization

**Files:**
- Create: `game/hazards.py`
- Modify: `config.py`, `game/levelgen.py`, `game/world.py`, `game/entities.py`, `game/enemies.py`
- Test: `tests/test_traps.py`

**Interfaces:**
- Consumes: `Level`, `World.move_entity`, `World.point_to_tile`, `Player`, `Enemy`.
- Produces:
  - `config.TRAP_COUNTS = (2, 2, 3, 3, 4, 4, 5, 2)`, `config.TRAP_DURATION = 3.0`, `config.TRAP_REARM_TIME = 5.0`
  - `Level.traps: tuple[tuple[int, int], ...] = ()`
  - `game.hazards.Trap` with `tile: tuple[int, int]`, `cooldown: float = 0.0`, `armed: bool`, `update(dt: float) -> None`, `try_trigger() -> bool`.
  - `World.traps: list[Trap]`, `World._trigger_trap(entity, previous_tile: tuple[int, int]) -> None`.
  - `Player.immobilized: float`, `Enemy.immobilized: float`.

- [ ] **Step 1: Write failing trap tests**

```python
def test_trap_immobilizes_player_for_three_seconds():
    world = World(0, seed=7)
    trap = world.traps[0]
    player = world.players[0]
    player.pos = world.tile_center(*trap.tile)
    world._trigger_trap(player, (-1, -1))
    assert player.immobilized == pytest.approx(config.TRAP_DURATION)
    player.update_timers(2.9)
    assert player.can_shoot() is False
    assert world.throw_grenade(player) is False
    assert world.fire_laser(player) is False

def test_trap_does_not_retrigger_while_standing_on_it():
    world = World(0, seed=8)
    trap = world.traps[0]
    player = world.players[0]
    player.pos = world.tile_center(*trap.tile)
    world._trigger_trap(player, (-1, -1))
    player.immobilized = 0.0
    trap.cooldown = 0.0
    world._trigger_trap(player, trap.tile)
    assert player.immobilized == 0.0

def test_trap_affects_enemy_but_not_boss():
    world = World(0, seed=9)
    trap = world.traps[0]
    enemy = make_enemy("tracker", trap.tile)
    world.enemies.append(enemy)
    world._trigger_trap(enemy, (-1, -1))
    assert enemy.immobilized == pytest.approx(config.TRAP_DURATION)
    boss = Boss()
    assert not hasattr(boss, "immobilized")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_traps.py -v`
Expected: FAIL because `World.traps` and player/enemy `immobilized` do not exist.

- [ ] **Step 3: Implement traps**

Create `game/hazards.py`. Add `Trap` and generation in `levelgen` using `TRAP_COUNTS`, placing only on reachable `EMPTY` tiles, not within 2 tiles of base, not on bridges/rivers/spawn safe zones, and outside the Boss arena. In `World`, build traps from `level.traps`, update cooldowns, and trigger only when the current tile changes from `previous_tile`. Add `immobilized` to `Player`/`Enemy`; decrement it in timers/update; skip movement/fire/skills while positive. `World.throw_grenade` and `World.fire_laser` must reject immobilized players. Boss gets no immobilization field.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_traps.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py game/hazards.py game/levelgen.py game/world.py game/entities.py game/enemies.py tests/test_traps.py
git commit -m "feat: add immobilizing traps for players and enemies"
```

---

### Task 6: Pickups: Repair, Stim Timer, and Invincibility

**Files:**
- Create: `game/pickups.py`
- Modify: `config.py`, `game/world.py`, `game/entities.py`
- Test: `tests/test_pickups.py`

**Interfaces:**
- Consumes: `World.point_to_tile`, `World.tile_center`, `World.find_path`, `Player`, `Effects`, `Audio`.
- Produces:
  - `config.ITEM_INITIAL_DELAY = 5.0`, `config.ITEM_SPAWN_INTERVAL = (16.0, 22.0)`, `config.ITEM_MAX_ON_MAP = 2`, `config.ITEM_TTL = 25.0`
  - `config.ITEM_WEIGHTS = {"repair": 74, "stim": 25, "invincible": 1}`
  - `game.pickups.Pickup` with `kind: str`, `pos: pygame.Vector2`, `ttl: float = config.ITEM_TTL`, `update(dt: float) -> bool`, `rect: pygame.Rect`.
  - `game.pickups.roll_pickup_kind(rng: random.Random) -> str`
  - `World.pickups: list[Pickup]`, `World.pickup_timer: float`, `World._update_pickups(dt: float) -> None`, `World._apply_pickup(player, pickup) -> bool` (returns whether the pickup was consumed).
  - `Player.stim_timer: float`, `Player.invincible_timer: float`.

- [ ] **Step 1: Write failing pickup tests**

```python
def test_repair_heals_one_and_is_not_consumed_at_full_hp():
    world = World(0, seed=10)
    player = world.players[0]
    player.hp = player.max_hp - 1
    pickup = Pickup("repair", player.center)
    assert world._apply_pickup(player, pickup) is True
    assert player.hp == player.max_hp

    pickup = Pickup("repair", player.center)
    assert world._apply_pickup(player, pickup) is False
    assert pickup.ttl == pytest.approx(config.ITEM_TTL)

def test_stim_sets_twenty_second_timer_and_does_not_stack():
    world = World(0, seed=11)
    player = world.players[0]
    player.stim_timer = 12.0
    world._apply_pickup(player, Pickup("stim", player.center))
    assert player.stim_timer == pytest.approx(20.0)

def test_invincibility_blocks_damage_for_six_seconds():
    world = World(0, seed=12)
    player = world.players[0]
    world._apply_pickup(player, Pickup("invincible", player.center))
    assert player.invincible_timer == pytest.approx(6.0)
    world.damage_player(player, player.max_hp)
    assert player.alive is True

def test_pickups_respect_map_cap_and_ttl():
    world = World(0, seed=13)
    world.pickups = [Pickup("repair", world.tile_center(3, 5)) for _ in range(2)]
    world._update_pickups(100.0)
    assert len(world.pickups) <= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pickups.py -v`
Expected: FAIL because `Pickup` and `World.pickups` do not exist.

- [ ] **Step 3: Implement pickups**

Create `game/pickups.py` with `Pickup`, weights, and TTL. In `World`, seed a dedicated `pickup_rng`, spawn on a 5-second initial delay and 16-22-second interval, enforce max 2, and choose only reachable `EMPTY` tiles that are not traps/river/bridge/spawn-safe. Apply repair, stim, and invincibility effects. Add `stim_timer`/`invincible_timer` to `Player`; decrement them in `update_timers`; `take_damage` returns false while `invincible_timer > 0`. Do not consume repair at full HP.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_pickups.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py game/pickups.py game/world.py game/entities.py tests/test_pickups.py
git commit -m "feat: add repair, stim, and invincibility pickups"
```

---

### Task 7: Stim Effects: Double Grenade Radius and Twin Laser

**Files:**
- Modify: `game/world.py`, `game/skills.py`
- Test: `tests/test_stim.py`

**Interfaces:**
- Consumes: `Player.stim_timer`, `PlayerStats.grenade_radius`, `PlayerStats.laser_damage`, `compute_laser`, `LaserBeam`, `World.grenades`, `World.lasers`.
- Produces:
  - `World.throw_grenade` uses `radius = stats.grenade_radius * (2.0 if player.stim_timer > 0 else 1.0)`.
  - `World.fire_laser` creates two `LaserBeam`s when `player.stim_timer > 0`.
  - `game.skills.offset_laser_origin(origin, direction, offset) -> pygame.Vector2`.
  - Twin laser damage per beam: `max(1, round(stats.laser_damage * 0.6))`.

- [ ] **Step 1: Write failing stim tests**

```python
def test_stim_doubles_grenade_radius():
    world = World(0, seed=14)
    player = world.players[0]
    player.stim_timer = 10.0
    world.throw_grenade(player)
    assert world.grenades[-1].radius == pytest.approx(player.stats.grenade_radius * 2)

def test_stim_laser_fires_two_beams_and_hits_each_enemy_once():
    world = World(0, seed=15)
    player = world.players[1]
    player.stim_timer = 10.0
    player.direction = config.Direction.RIGHT
    tx, ty = world.point_to_tile(player.center)
    for x in range(tx + 1, tx + 4):
        world.grid[ty][x] = config.Tile.EMPTY
    enemy = make_enemy("tracker", (tx + 2, ty))
    enemy.hp = 100
    world.enemies.append(enemy)
    before_hp = enemy.hp
    assert world.fire_laser(player) is True
    assert len(world.lasers) == 2
    assert enemy.hp == before_hp - max(1, round(player.stats.laser_damage * 0.6))

def test_twin_laser_does_not_double_hit_boss():
    world = World(config.BOSS_LEVEL, seed=16)
    player = world.players[1]
    player.stim_timer = 10.0
    player.pos = pygame.Vector2(
        world.boss.center.x, world.boss.center.y + 120
    )
    player.direction = config.Direction.UP
    before_hp = world.boss.hp
    world.fire_laser(player)
    assert world.boss.hp == before_hp - max(
        1, round(player.stats.laser_damage * 0.6)
    )

def test_twin_laser_uses_pre_fire_grid_for_bricks():
    world = World(0, seed=17)
    player = world.players[1]
    player.stim_timer = 10.0
    player.direction = config.Direction.UP
    tx, ty = world.point_to_tile(player.center)
    world.grid[ty - 1][tx] = config.Tile.EMPTY
    brick = (tx, ty - 2)
    world.grid[brick[1]][brick[0]] = config.Tile.BRICK
    world.fire_laser(player)
    assert world.grid[brick[1]][brick[0]] == config.Tile.EMPTY
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_stim.py -v`
Expected: FAIL because stim radius/twin beams are not implemented.

- [ ] **Step 3: Implement stim effects**

Add `offset_laser_origin` in `skills.py`. In `World.fire_laser`, when `stim_timer > 0`, copy the current grid to `snapshot`, compute both beams from offset origins using that snapshot, append both to `world.lasers`, and resolve damage with a `hit_enemy_ids` set and a single `hit_boss` flag so each target takes one beam. Destroy each beam's first brick at most once. Otherwise keep the existing single-beam path unchanged. In `throw_grenade`, multiply the radius when stim is active.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_stim.py tests/test_world_combat.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add game/world.py game/skills.py tests/test_stim.py tests/test_world_combat.py
git commit -m "feat: add stim-driven double grenade radius and twin laser"
```

---

### Task 8: i18n Core, Upgrade Keys, and All Screen Text

**Files:**
- Create: `game/i18n.py`
- Modify: `game/upgrades.py`, `game/states.py`, `game/render.py`
- Test: `tests/test_i18n.py`, `tests/test_upgrades.py`, `tests/test_render_smoke.py`

**Interfaces:**
- Consumes: `Upgrade` pool, all renderer screens, `Game.language`.
- Produces:
  - `game.i18n.LANGUAGES = ("zh", "en")`, `DEFAULT_LANGUAGE = "zh"`, `TEXTS`, `all_keys() -> set[str]`, `required_glyphs() -> set[str]`.
  - `game.i18n.tr(language: str, key: str, **kwargs) -> str` with English fallback and a development warning for missing keys.
  - `Upgrade` fields `name_key: str`, `desc_key: str`; each pool entry uses `upgrade.<id>.name` and `upgrade.<id>.desc`.
  - `Renderer.set_language(language: str) -> None`; `Renderer.tr(key: str, **kwargs) -> str`.
  - `Game.language: str`, `Game._toggle_language() -> None`.
  - `Game._loss_reason()` returns `"gameover.base_destroyed"` or `"gameover.both_eliminated"`.

- [ ] **Step 1: Write failing i18n tests**

```python
def test_language_key_sets_match():
    assert set(i18n.TEXTS["zh"]) == set(i18n.TEXTS["en"])

def test_every_upgrade_has_both_translations():
    for upgrade in upgrades.UPGRADE_POOL:
        assert upgrade.name_key in i18n.TEXTS["zh"]
        assert upgrade.name_key in i18n.TEXTS["en"]
        assert upgrade.desc_key in i18n.TEXTS["zh"]
        assert upgrade.desc_key in i18n.TEXTS["en"]

def test_tr_formats_and_falls_back():
    assert i18n.tr("zh", "hud.hp", current=2, maximum=3)
    assert i18n.tr("xx", "hud.hp", current=2, maximum=3)

def test_renderer_switches_language_without_error(screen):
    renderer = Renderer(screen)
    renderer.set_language("en")
    renderer.draw_title(0.0, "normal")
    renderer.set_language("zh")
    renderer.draw_title(0.0, "hell")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_i18n.py -v`
Expected: FAIL because `game.i18n` and `Upgrade.name_key` do not exist.

- [ ] **Step 3: Implement i18n and migrate UI strings**

Create `game/i18n.py` with both language dictionaries and all keys used by the title, controls, HUD, upgrades, pause, gameover, victory, difficulty, language, buffs, and terrain labels. Migrate `Upgrade` to `name_key`/`desc_key` and update the pool. Add `Renderer.set_language`/`tr`, replace every visible string in `render.py` with `self.tr(...)`, and update `draw_title` to show difficulty and language. Add `L` handling on title, controls, and pause; persist the choice in `Game.language`. Replace `_loss_reason` with translation keys.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_i18n.py tests/test_upgrades.py tests/test_render_smoke.py -v`
Expected: PASS; both languages render all screens without exceptions.

- [ ] **Step 5: Commit**

```bash
git add game/i18n.py game/upgrades.py game/states.py game/render.py tests/test_i18n.py tests/test_upgrades.py tests/test_render_smoke.py
git commit -m "feat: add Chinese and English UI with localized upgrades"
```

---

### Task 9: Bundled Chinese Font and Glyph Coverage

**Files:**
- Create: `assets/fonts/NotoSansCJKsc-Regular-subset.otf`, `assets/fonts/OFL.txt`, `assets/fonts/glyphs.json`, `tools/build_font_subset.py`
- Modify: `config.py`, `game/render.py`
- Test: `tests/test_fonts.py`

**Interfaces:**
- Consumes: `i18n.required_glyphs()`.
- Produces:
  - `config.ROOT = Path(__file__).resolve().parent`
  - `config.FONT_PATH = config.ROOT / "assets/fonts/NotoSansCJKsc-Regular-subset.otf"`
  - `config.FONT_LICENSE_PATH = config.ROOT / "assets/fonts/OFL.txt"`
  - `Renderer.font_path: Path | None` set to the bundled font when loaded.
  - `tools/build_font_subset.py` CLI: `python tools/build_font_subset.py SOURCE_FONT OUTPUT_FONT`.

- [ ] **Step 1: Write failing font tests**

```python
def test_font_assets_exist():
    assert config.FONT_PATH.exists()
    assert config.FONT_LICENSE_PATH.exists()

def test_font_loads_and_contains_required_glyphs():
    font = pygame.font.Font(str(config.FONT_PATH), 24)
    assert font.render("中文测试", True, (255, 255, 255)).get_width() > 0
    manifest = json.loads((config.FONT_PATH.parent / "glyphs.json").read_text())
    assert set(manifest) == i18n.required_glyphs()

def test_renderer_uses_bundled_font(screen):
    renderer = Renderer(screen)
    assert renderer.font_path == config.FONT_PATH
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_fonts.py -v`
Expected: FAIL because the font assets and `FONT_PATH` do not exist.

- [ ] **Step 3: Build the font subset**

Download the OFL-licensed Noto Sans CJK SC Regular source font and license to a temporary directory:

```bash
curl -L -o /tmp/NotoSansCJKsc-Regular.otf \
  https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf
curl -L -o assets/fonts/OFL.txt \
  https://github.com/notofonts/noto-cjk/raw/main/Sans/LICENSE
```

Add `fonttools` to the local venv only for the build:

```bash
.venv/bin/pip install fonttools
.venv/bin/python tools/build_font_subset.py \
  /tmp/NotoSansCJKsc-Regular.otf \
  assets/fonts/NotoSansCJKsc-Regular-subset.otf
```

The script writes `assets/fonts/glyphs.json` with the exact `i18n.required_glyphs()` set. Commit the subset, license, manifest, and tool. Update `Renderer` to load `config.FONT_PATH` for all five font sizes, with system-font fallback and a default-font last resort; set `self.font_path` only when the bundled font loads.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_fonts.py tests/test_i18n.py -v`
Expected: PASS; Chinese glyphs load and the manifest matches the required set.

- [ ] **Step 5: Commit**

```bash
git add assets/fonts config.py game/render.py tools/build_font_subset.py tests/test_fonts.py
git commit -m "feat: bundle OFL Chinese font subset for localized UI"
```

---

### Task 10: Render Terrain, Traps, Pickups, and Buff HUD

**Files:**
- Modify: `game/render.py`
- Test: `tests/test_render_smoke.py`, `tests/test_terrain.py`

**Interfaces:**
- Consumes: `World.grid`, `World.traps`, `World.pickups`, `Player.stim_timer`, `Player.invincible_timer`, `Player.immobilized`, `World.difficulty`.
- Produces:
  - `Renderer._draw_tiles` handles `RIVER`/`BRIDGE`.
  - `Renderer._draw_traps(world, offset)` and `Renderer._draw_pickups(world, offset)`.
  - `Renderer._draw_player_card` draws `R2`/`2X`/`INV`/`HOLD` chips.
  - `Renderer._draw_level_track` shows `NORMAL`/`HELL`.
  - All new labels use `self.tr`.

- [ ] **Step 1: Write failing render smoke tests**

```python
def test_draw_world_with_new_terrain_and_pickups(screen):
    world = World(5, seed=18)
    world.pickups = [Pickup("repair", world.tile_center(4, 5))]
    world.traps.append(Trap((5, 5)))
    renderer = Renderer(screen)
    renderer.draw_world(world)

def test_hud_with_buff_chips_draws_without_error(screen):
    world = World(0, seed=19)
    world.players[0].stim_timer = 12.0
    world.players[1].invincible_timer = 4.0
    renderer = Renderer(screen)
    renderer.draw_world(world)

def test_title_shows_hell_and_chinese(screen):
    renderer = Renderer(screen)
    renderer.set_language("zh")
    renderer.draw_title(0.0, "hell")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_render_smoke.py -v`
Expected: FAIL or draw no water/pickup/HUD content because the new draw paths are missing.

- [ ] **Step 3: Implement the new drawing**

Add river/bridge tile drawing with `world.elapsed` animation, trap plates with armed/triggered/cooldown states, pickup glows (green cross, cyan stim, gold invincibility), buff chips on player cards, difficulty label on the level card, and localized gameover retry/quit text. Keep all new visuals procedural and readable at 1280x720.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_render_smoke.py tests/test_terrain.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add game/render.py tests/test_render_smoke.py tests/test_terrain.py
git commit -m "feat: render rivers, bridges, traps, pickups, and buff HUD"
```

---

### Task 11: Integration, Balance, README, and Full Verification

**Files:**
- Modify: `README.md`, `tests/test_integration.py`, `tests/test_config.py`
- Test: full suite and headless smoke.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: updated user-facing documentation and end-to-end tests for normal/hell, retry, terrain, pickups, elites, and bilingual UI.

- [ ] **Step 1: Write failing integration tests**

```python
def test_full_run_normal_and_hell_construct_all_levels():
    for mode in ("normal", "hell"):
        for level_index in range(config.LEVEL_COUNT):
            world = World(level_index, seed=3000 + level_index, difficulty=mode)
            assert validate_level(world.level)
            for _ in range(120):
                world.update(1 / 60, [PlayerInput() for _ in world.players])
            assert world.elapsed == pytest.approx(2.0)

def test_retry_flow_and_language_switch(game):
    start_playing(game)
    game.world.status = "lost"
    game.update(1 / 60)
    game.handle_event(key_event(config.CONFIRM_KEY))
    assert game.state == "playing"
    game.handle_event(key_event(config.PAUSE_KEY))
    assert game.state == "paused"
    before = game.language
    game.handle_event(key_event(pygame.K_l))
    assert game.language != before
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_integration.py -v`
Expected: FAIL until the final integration behavior and docs are wired.

- [ ] **Step 3: Update README and integration coverage**

Document difficulty selection, `L` language toggle, retry-current-level, pickups, rivers/bridges/traps, elite counts, and the bundled font license. Extend integration tests to cover both difficulties, all levels, retry, and language switching.

- [ ] **Step 4: Run full verification**

Run: `.venv/bin/pytest -q`
Expected: PASS, all tests.

Run: `.venv/bin/python -c "import pygame; pygame.init(); ..."` or the existing headless smoke command to run 120 frames of title/playing in both languages.
Expected: no exception.

Run: `.venv/bin/python main.py --help`
Expected: exits 0 and prints usage.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_integration.py tests/test_config.py
git commit -m "test: verify expansion integration and document new features"
```

---

## Self-Review

### Spec coverage

- Difficulty normal/hell, title selection, base HP, enemy HP/aggression/spawn: Task 1, Task 2, Task 3.
- Retry current level, preserved upgrades/revives/base: Task 2.
- Rivers, bridges, traps, invincible terrain: Task 4, Task 5.
- Pickups: repair, stim, invincibility, HUD: Task 6, Task 7, Task 10.
- Elites every level and scaling: Task 3.
- Faster spawns: Task 1.
- Chinese/English UI and font: Task 8, Task 9.
- Rendering and integration: Task 10, Task 11.
- Readme and full verification: Task 11.

### Review Focus tests

- Retry base state: Task 2 `test_player_elimination_retry_preserves_upgrades_lives_and_base`, `test_base_destroyed_retry_restores_full_base`.
- River-aware validation: Task 4 `test_all_levels_validate_with_rivers`.
- Trap re-entry/skill lockout: Task 5 `test_trap_immobilizes_player_for_three_seconds`, `test_trap_does_not_retrigger_while_standing_on_it`.
- Hell scaling composition: Task 1 `test_hell_scales_normal_enemy_once`, Task 3 `test_hell_elite_scales_only_with_elite_multiplier`.
- Chinese glyphs/overflow: Task 9 `test_font_loads_and_contains_required_glyphs`, Task 10 `test_title_shows_hell_and_chinese`.

### Type consistency

- `DifficultyProfile` field names are used consistently in `World`, `Boss`, and tests.
- `RunState` fields match `Game._capture_run_state` and `World` constructor params.
- `Trap`/`Pickup` fields match renderer and world tests.
- `Upgrade.name_key`/`desc_key` match i18n tests and renderer translation calls.
- `Renderer.set_language`/`tr` are defined in Task 8 and used by Task 10.

### Open items

- None. Visual texture details, final Chinese wording, and test-file splitting are explicitly builder-owned in the spec.
