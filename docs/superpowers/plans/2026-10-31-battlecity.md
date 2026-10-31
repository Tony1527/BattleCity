# 坦克大战：全息军械库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete 8-level, local two-player tank defense game described by the spec, in pure pygame with procedural holo-armory visuals.

**Architecture:** A deterministic, testable simulation core (`config`, `geometry`, `levelgen`, `pathfinding`, `entities`, `skills`, `enemies`, `boss`, `upgrades`, `world`) is kept free of rendering concerns. `render`, `input`, `states`, and `main` provide the pygame shell. Logic modules are tested with pytest without opening a real window.

**Tech Stack:** Python 3.12+ (verified on 3.14), pygame-ce 2.5.x imported as `pygame`, pytest. No external image or audio assets.

**Spec:** `docs/superpowers/specs/2026-10-31-battlecity-design.md`

## Global Constraints

- Window 1280x720 at 60 FPS; playfield 24x13 tiles of 48 px; playfield offset x=64, y=0; HUD occupies y=624..719.
- Pure pygame drawing; all glow via additive surfaces (`BLEND_ADD`) or layered translucent fills. No image/audio files.
- Four-direction movement only; AABB collision against tiles; dt-based movement in px/s.
- Player HP default 3; hit invulnerability 0.5 s; respawn delay 3 s; respawn invulnerability 2 s; shared revives reset to 3 each level.
- Base HP 3 and resets each level; base occupies `BASE_TILES` (2x2) at the bottom center.
- Grenade: 6 s cooldown, 40 enemy damage, 35% friendly/self damage, 1.5-tile radius, destroys brick, never base.
- Laser: 5 s cooldown, 8-tile range, 60 damage, pierces enemies, stops at steel, destroys first brick and stops, never friendly fire or base.
- Normal bullets: no friendly fire, no base damage; destroy brick, stop at steel.
- Enemy count grows by level; elite levels are index 3 and 6; boss is index 7. Level quotas: `ENEMY_QUOTA`.
- Upgrade choice is same-screen sequential, P1 first then P2, no timer; eliminated players skip; each player independently picks one of three and stacking is capped.
- Every tuning value lives in `config.py` or `upgrades.py`, never inline in render/state code.
- All work happens on branch `feature/battlecity`; use the project venv `.venv`.

## Review Focus

- A generated level may seal the base with steel or collapse to one route; `test_levelgen.py` must reject a hand-built sealed grid and validate many seeds.
- Route overlap may be computed so loosely that three barely-different paths pass; `test_levelgen.py` must assert pairwise overlap <= 0.30 and at least two base entrance directions.
- Friendly fire may leak into normal bullets or lasers, or grenades may damage the base; `test_world_combat.py` must pin the full damage matrix.
- Downed players may consume revives incorrectly or prevent the "both eliminated" loss; `test_world_core.py` must cover order of death and elimination.
- Upgrade stacking may exceed caps or mutate the shared pool; `test_upgrades.py` must cover cap rejection and repeated rolls.
- Headless/CI environments have no display or audio device; renderer initialization and audio init must degrade gracefully (`test_render_smoke.py`).

---

### Task 1: Foundation — package, config, geometry

**Files:**
- Create: `requirements.txt`
- Create: `game/__init__.py`
- Create: `config.py`
- Create: `game/geometry.py`
- Modify: `.gitignore`
- Test: `tests/test_config.py`, `tests/test_geometry.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `config.Direction` (IntEnum UP/RIGHT/DOWN/LEFT with `.vector -> tuple[int,int]`, `.angle -> float`, `Direction.from_vector(dx,dy)`)
  - `config.Tile` (IntEnum EMPTY/BRICK/STEEL)
  - `config.PlayerStats` dataclass with fields `max_hp, speed, fire_interval, bullet_damage, bullet_speed, damage_reduction, grenade_cooldown, grenade_damage, grenade_radius, laser_cooldown, laser_damage, laser_range, extra_lives, base_shield, grenade_split, laser_reflect`
  - `config.EnemySpec` frozen dataclass and `config.ENEMY_SPECS` dict for `tracker`, `gunner`, `demolisher`
  - Constants listed under Global Constraints plus `BASE_TILES`, `BASE_ENTRANCES`, `ENEMY_SPAWNS`, `PLAYER_SPAWNS`, `ENEMY_QUOTA`, `MAX_ACTIVE_ENEMIES`, `SPAWN_INTERVAL`, `ELITE_LEVELS`, `BOSS_LEVEL`, `LEVEL_COUNT`, colors (`BG`, `FLOOR`, `GRID`, `STEEL`, `BRICK`, `P1_BLUE`, `P2_AMBER`, `ENEMY_RED`, `ENEMY_ORANGE`, `HOLO_WHITE`), `KEYMAP`
  - `game.geometry.tile_rect(tx,ty)->pygame.Rect`, `tile_center(tx,ty)->pygame.Vector2`, `point_to_tile(pos)->tuple[int,int]`, `in_bounds(tx,ty)->bool`

- [ ] **Step 1: Write failing tests**

`tests/conftest.py` sets `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` before importing pygame and calls `pygame.init()` once.

`tests/test_config.py` asserts: tile size 48, grid 24x13, playfield x 64, HUD y 624, `BASE_TILES` is exactly the 2x2 bottom-center block, `ENEMY_SPAWNS` has 3 distinct entries, `PlayerStats().max_hp == 3`, `PlayerStats().laser_range == 384.0`, default stats match the spec values, each `Direction.vector` is orthogonal, `Direction.from_vector(0,-1) is Direction.UP`, and `KEYMAP[0]["skill"] == pygame.K_f`.

`tests/test_geometry.py` asserts `tile_rect(0,0) == pygame.Rect(64,0,48,48)`, `tile_center(2,3) == pygame.Vector2(64+2*48+24, 3*48+24)`, round-trip `point_to_tile(tile_center(x,y)) == (x,y)`, and out-of-bounds detection.

- [ ] **Step 2: Run tests, expect import failure**

Run: `.venv/bin/pytest tests/test_config.py tests/test_geometry.py -q`
Expected: FAIL (modules missing).

- [ ] **Step 3: Implement config and geometry**

Use `from __future__ import annotations`. Keep all numeric tuning in `config.py`. `PlayerStats` includes a `clone()` method. `EnemySpec` fields: `kind, hp, speed, fire_interval, bullet_speed, bullet_damage, attack_range, score`; tracker `(2,78,1.5,230,1,5*TILE,10)`, gunner `(3,60,1.9,300,1,8*TILE,15)`, demolisher `(4,95,2.5,0,0,1.5*TILE,20)`. Add `pygame-ce>=2.5.0` and `pytest>=9.0` to `requirements.txt`. Add `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/` to `.gitignore`.

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/bin/pytest tests/test_config.py tests/test_geometry.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore config.py game/__init__.py game/geometry.py tests/conftest.py tests/test_config.py tests/test_geometry.py
git commit -m "feat: add config and geometry foundation"
```

---

### Task 2: Pathfinding and level generation

**Files:**
- Create: `game/pathfinding.py`
- Create: `game/levelgen.py`
- Test: `tests/test_pathfinding.py`, `tests/test_levelgen.py`

**Interfaces:**
- Consumes: `config.TILE`, `config.Tile`, `config.GRID_COLS`, `config.GRID_ROWS`, `config.BASE_TILES`, `config.BASE_ENTRANCES`, `config.ENEMY_SPAWNS`, `config.PLAYER_SPAWNS`, `game.geometry.in_bounds`.
- Produces:
  - `pathfinding.neighbors(tx,ty)->list[tuple[int,int]]`
  - `pathfinding.astar(start, goal, passable: Callable[[int,int],bool]) -> list[tuple[int,int]] | None` (includes start and goal)
  - `pathfinding.bfs_distances(start, passable) -> dict[tuple[int,int], int]`
  - `levelgen.Level` dataclass fields `grid: list[list[Tile]]`, `spawns: tuple[tuple[int,int],...]`, `base_tiles: tuple[tuple[int,int],...]`, `seed: int`
  - `levelgen.is_passable_for_routes(level, tx, ty) -> bool`
  - `levelgen.generate_level(seed:int) -> Level`
  - `levelgen.fallback_level() -> Level`
  - `levelgen.find_routes(level, max_routes:int=3) -> list[list[tuple[int,int]]]`
  - `levelgen.validate_level(level) -> bool`

- [ ] **Step 1: Write failing pathfinding tests**

Cover: path around steel in a 5x5 grid; `None` when fully walled; path includes start/goal; `bfs_distances` values on an open grid.

- [ ] **Step 2: Write failing level generation tests**

Cover: `generate_level(seed)` deterministic; seeds 0..9 all `validate_level`; `fallback_level()` validates; a grid with a full steel row between spawns and base fails; a grid with one narrow gap fails the 3-route / 2-direction requirement; returned grids are 13 rows x 24 cols; border is all steel except the base area; base tiles and `BASE_ENTRANCES` are not steel; 3x3 areas around all `ENEMY_SPAWNS` and `PLAYER_SPAWNS` contain no steel. Construct the sealed grid directly as a `Level`.

- [ ] **Step 3: Run tests, expect import failure**

Run: `.venv/bin/pytest tests/test_pathfinding.py tests/test_levelgen.py -q`
Expected: FAIL (modules missing).

- [ ] **Step 4: Implement pathfinding**

A* with Manhattan heuristic and deterministic neighbor order `UP, LEFT, RIGHT, DOWN`; `passable` receives tile coordinates. Use heap with `(f, g, counter, tile)` to avoid comparing tuples unpredictably.

- [ ] **Step 5: Implement level generation**

Generation algorithm: start from steel border, clear base 2x2 and all `BASE_ENTRANCES`, clear a 3x3 area around every tile in `ENEMY_SPAWNS` and `PLAYER_SPAWNS`; scatter bricks at 30% and steel at 6% inside the playfield, but force the three vertical corridor bands `cols 2..5`, `10..13`, `18..21` to contain no steel and at most sparse bricks; reject layouts that fail `validate_level`. Retry up to 60 deterministic seeds derived from the input seed, then return `fallback_level()`.

Route validation: `find_routes` builds candidates with `astar` from each spawn to each base entrance plus up to 40 seeded randomized DFS paths per spawn (randomized neighbor order, depth limit 200). Greedily select one shortest route per spawn, then add candidates with the lowest maximum pairwise overlap until 3 routes. Overlap ratio is `len(set(a) & set(b)) / min(len(a), len(b))`; all selected pairs must be <= 0.30. `validate_level` requires >=3 selected routes, one route per spawn, pairwise <=0.30, and at least 2 distinct base-entrance directions used.

Fallback: a fixed open three-corridor layout with brick clusters and a few steel pillars outside the corridors; it must validate.

- [ ] **Step 6: Run tests, verify pass**

Run: `.venv/bin/pytest tests/test_pathfinding.py tests/test_levelgen.py -q`
Expected: all pass, including 10 generated seeds.

- [ ] **Step 7: Commit**

```bash
git add game/pathfinding.py game/levelgen.py tests/test_pathfinding.py tests/test_levelgen.py
git commit -m "feat: add A* pathfinding and validated procedural mazes"
```

---

### Task 3: Upgrade pool and stat application

**Files:**
- Create: `game/upgrades.py`
- Test: `tests/test_upgrades.py`

**Interfaces:**
- Consumes: `config.PlayerStats`.
- Produces:
  - `upgrades.Upgrade` frozen dataclass fields `id, name, description, stat, op, amount, max_stacks` where `op` is `"add"` or `"mul"`.
  - `upgrades.UPGRADE_POOL: tuple[Upgrade, ...]` (16 entries covering cooldown, damage/range, normal fire, speed, armor/revive, base shield, split grenade, laser reflect).
  - `upgrades.upgrade_by_id(upgrade_id:str)->Upgrade`
  - `upgrades.roll_upgrades(rng: random.Random, levels: dict[str,int], count:int=3) -> list[Upgrade]`
  - `upgrades.apply_upgrade(stats: PlayerStats, levels: dict[str,int], upgrade_id:str) -> bool` (False when capped; increments levels only on success).

- [ ] **Step 1: Write failing tests**

Assert: every pool id is unique; pool has >=16 entries; `roll_upgrades` never returns duplicates or capped entries; a capped upgrade returns False and leaves stats unchanged; applying `fire_interval` multiplier three times respects cap and reaches `0.35 * 0.85**3`; applying a `max_hp` add raises `max_hp`; `grenade_split` and `laser_reflect` caps are obeyed; when fewer than 3 upgrades remain, `roll_upgrades` returns the available count.

- [ ] **Step 2: Run test, expect import failure**

Run: `.venv/bin/pytest tests/test_upgrades.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement upgrades**

Use `setattr(stats, upgrade.stat, getattr(stats, upgrade.stat) * amount)` for `mul`, add for `add`. Include ids: `overclock`, `heavy_rounds`, `servos`, `plated_hull`, `reactive_armor`, `rapid_loader`, `grenade_tuning`, `demo_charge`, `wide_blast`, `split_charge`, `laser_focus`, `laser_capacitor`, `laser_extender`, `prism`, `base_shield`, `spare_parts`. Use multiplier caps 2-4 and additive caps 2-4 from the task brief.

- [ ] **Step 4: Run test, verify pass**

Run: `.venv/bin/pytest tests/test_upgrades.py -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add game/upgrades.py tests/test_upgrades.py
git commit -m "feat: add stackable upgrade pool"
```

---

### Task 4: Core entities and input mapping

**Files:**
- Create: `game/entities.py`
- Create: `game/input.py`
- Test: `tests/test_entities.py`, `tests/test_input.py`

**Interfaces:**
- Consumes: `config` values, `game.geometry`.
- Produces:
  - `entities.Base` with `tiles`, `hp`, `max_hp`, `shield`, `alive`, `.rect`, `.center`, `.take_damage(amount:int)->None`, `.reset_for_level(shield:int=0)->None`
  - `entities.Bullet` with `pos`, `prev_pos`, `direction`, `speed`, `damage`, `owner_id`, `friendly`, `pierce`, `alive`, `.update(dt)`, `.rect`
  - `entities.Player` with `player_id`, `pos`, `direction`, `stats`, `hp`, `alive`, `eliminated`, `invuln`, `respawn_timer`, `fire_timer`, `grenade_timer`, `laser_timer`, `.rect`, `.center`, `.update_timers(dt)`, `.can_shoot()`, `.shoot_reset()`, `.take_damage(amount:int)->bool`, `.revive(pos)`
  - `input.PlayerInput` dataclass fields `move: Direction|None`, `shoot: bool`, `skill: bool`
  - `input.read_player_inputs(keys, skill_pressed: set[int] | None = None) -> list[PlayerInput]`
  - `input.choice_from_event(event, count:int=3) -> int|None`

- [ ] **Step 1: Write failing entity tests**

Assert: base starts at 3 HP; shields absorb before HP; `take_damage` kills at 0; `reset_for_level` restores HP and shield; bullet advances by `speed*dt`; player `take_damage` applies 15% armor reduction, sets 0.5 s invulnerability, ignores damage during invulnerability, and returns True on destruction; `revive` restores HP and sets 2 s invulnerability; player timers never go negative.

- [ ] **Step 2: Write failing input tests**

Use a dict-like fake key state. Assert WASD maps to P1 move and arrows to P2; Space/`.` set shoot; F/slash set skill only when their player id is in `skill_pressed`; holding both vertical keys does not produce diagonal movement; key `1`, `2`, `3` map to choices 0, 1, 2.

- [ ] **Step 3: Run tests, expect import failure**

Run: `.venv/bin/pytest tests/test_entities.py tests/test_input.py -q`
Expected: FAIL.

- [ ] **Step 4: Implement entities and input**

Player hitbox is 36x36 centered on `pos`; bullet hitbox is 8x8. Movement/collision is not implemented here (World owns it). `take_damage` uses `max(1, round(amount * (1 - stats.damage_reduction)))`. All numeric values come from config.

- [ ] **Step 5: Run tests, verify pass**

Run: `.venv/bin/pytest tests/test_entities.py tests/test_input.py -q`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add game/entities.py game/input.py tests/test_entities.py tests/test_input.py
git commit -m "feat: add entities and two-player input mapping"
```

---

### Task 5: Grenade and laser skills

**Files:**
- Create: `game/skills.py`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: `config.Direction`, `config.Tile`, `config.GRENADE_FLIGHT`, `config.GRENADE_RANGE`, `game.geometry`.
- Produces:
  - `skills.Cooldown` with `duration`, `remaining`, `.ready` property, `.trigger()->bool`, `.update(dt)`
  - `skills.Grenade` with `start`, `target`, `elapsed`, `duration`, `owner_id`, `damage`, `radius`, `split`, `exploded`, `.update(dt)->bool` (True on the frame it lands/explodes), `.position()->pygame.Vector2`, `.height()->float`, `.explosion_points()->list[pygame.Vector2]`
  - `skills.LaserBeam` with `origin`, `end`, `length`, `direction`, `brick_tile`, `life`
  - `skills.compute_laser(origin, direction, max_range, grid) -> LaserBeam`
  - `skills.point_near_segment(point, a, b, tolerance:float) -> bool`

- [ ] **Step 1: Write failing tests**

Assert: cooldown ready at 0, trigger fails while active, becomes ready after duration, update clamps at 0. Grenade reaches exactly `start + direction.vector * GRENADE_RANGE` (clamped to playfield) after `duration`, reports exploded once, and produces `1 + split` explosion points including the target. Laser in an open grid reaches `origin + vector*range`; a steel tile stops the beam before/at the steel tile and yields no brick; a brick tile stops it and records that tile; `point_near_segment` is true for a point 5 px from a segment and false 40 px away.

- [ ] **Step 2: Run test, expect import failure**

Run: `.venv/bin/pytest tests/test_skills.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement skills**

Sample the laser every 2 px along the ray (max 192 samples); stop at the first non-empty tile. Grenade target clamps inside the playfield with an 8 px margin. Arc height is `4 * 26 * t * (1-t)` px above the interpolated line. Split points are offset perpendicular to travel by 30 px for each split level.

- [ ] **Step 4: Run test, verify pass**

Run: `.venv/bin/pytest tests/test_skills.py -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add game/skills.py tests/test_skills.py
git commit -m "feat: add grenade and piercing laser skills"
```

---

### Task 6: Enemy AI

**Files:**
- Create: `game/enemies.py`
- Test: `tests/test_enemies.py`

**Interfaces:**
- Consumes: `config.ENEMY_SPECS`, `config.Direction`, `game.geometry`.
- Produces:
  - `enemies.Enemy` with `kind`, `pos`, `direction`, `hp`, `max_hp`, `speed`, `fire_timer`, `alive`, `.rect`, `.center`, `.take_damage(amount:int, world)->bool`, `.update(dt, world)`
  - `enemies.EliteEnemy` with shield, `shield_timer`, `summon_timer`, spread fire
  - `enemies.make_enemy(kind:str, tile:tuple[int,int]) -> Enemy` (`"elite"` returns `EliteEnemy`)
  - `enemies.follow_path(enemy, world, path, dt) -> Direction|None`

**World protocol expected by enemies (implemented in Tasks 8-10):**
`world.point_to_tile(pos)`, `world.tile_center(tx,ty)`, `world.is_brick(tx,ty)`, `world.players`, `world.base_entrances`, `world.find_path(start,goal)`, `world.move_enemy(enemy,direction,dt)->bool`, `world.enemy_fire(enemy,direction)`, `world.demolisher_blast(enemy)`, `world.spawn_enemy(kind,tile)`, `world.damage_player(player,amount)`, `world.random`.

- [ ] **Step 1: Write failing tests with a FakeWorld**

FakeWorld exposes the protocol above and records calls. Assert: `make_enemy` builds tracker/gunner/demolisher with the configured HP/speed; `take_damage` kills and sets `alive=False`; `EliteEnemy` regenerates shield on its timer but never above its shield cap; elite summons when its timer fires and does not exceed 2 living summons; tracker fires when the FakeWorld reports line of sight; demolisher calls `demolisher_blast` when within 1.5 tiles of a player; `follow_path` returns the direction of the next tile and snaps to tile centers.

- [ ] **Step 2: Run test, expect import failure**

Run: `.venv/bin/pytest tests/test_enemies.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement enemies**

Tracker: path to nearest base entrance, fire at the base when in line; fire at blocking bricks. Gunner: path toward a tile 4-6 tiles from the nearest living player, stop and fire when the player is in line and within `attack_range`; otherwise reposition. Demolisher: path toward the base, fires at bricks on its path twice as fast, and after a 0.6 s telegraph calls `demolisher_blast` when within 1.5 tiles of a player or base entrance. Elite extends gunner behavior with a 12-point regenerating shield, 3-shot spread, and summoning two trackers every 9 s. If no player is alive, gunner targets the base.

- [ ] **Step 4: Run test, verify pass**

Run: `.venv/bin/pytest tests/test_enemies.py -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add game/enemies.py tests/test_enemies.py
git commit -m "feat: add tracker, gunner, demolisher, and elite AI"
```

---

### Task 7: Multi-phase final boss

**Files:**
- Create: `game/boss.py`
- Test: `tests/test_boss.py`

**Interfaces:**
- Consumes: `config` boss constants, `game.geometry`, `config.Direction`.
- Produces:
  - `boss.Boss` with `pos`, `hp`, `max_hp`, `phase`, `alive`, `telegraph`, `phase_flash`, `.rect`, `.center`, `.take_damage(amount:int)->bool`, `.update(dt, world)`, `.phase_for_hp(hp:int)->int`
  - Boss constants in `config.py`: `BOSS_HP=360`, `BOSS_SPEED=32`, `BOSS_SIZE=96`, `BOSS_PHASE_THRESHOLDS=(0.66,0.33)`.

**World protocol expected by boss:** `world.players`, `world.base`, `world.enemy_fire_at(origin, target, speed, damage)`, `world.enemy_radial_burst(origin, count, speed, damage)`, `world.boss_laser(origin, direction)`, `world.spawn_enemy(kind,tile)`, `world.damage_player(player,amount)`, `world.random`, `world.playfield_rect`.

- [ ] **Step 1: Write failing tests with a FakeWorld**

Assert: phase 1 at full HP, phase 2 at <=66%, phase 3 at <=33%; phase never decreases when HP fluctuates; `take_damage` sets `alive=False` at 0 and stops attacks; an aimed attack fires through `enemy_fire_at`; a radial attack calls `enemy_radial_burst` with 8/12/16 bullets by phase; phase 2+ schedules a laser with a >=0.8 s telegraph before calling `boss_laser`; phase transitions set `phase_flash > 0`; summons never exceed 3 per transition.

- [ ] **Step 2: Run test, expect import failure**

Run: `.venv/bin/pytest tests/test_boss.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement boss**

Boss drifts horizontally near the top center and never leaves the playfield. Phase 1: aimed shot every 1.2 s, radial burst every 3.5 s. Phase 2: adds a 1.0 s telegraphed laser every 6 s and summons two trackers once on entry. Phase 3: aimed interval 0.8 s, radial interval 2.4 s, laser interval 4.5 s, radial count 16. Every attack has a visible telegraph field so the renderer can draw warning rings/lines.

- [ ] **Step 4: Run test, verify pass**

Run: `.venv/bin/pytest tests/test_boss.py -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add config.py game/boss.py tests/test_boss.py
git commit -m "feat: add three-phase boss"
```

---

### Task 8: World core — level state, movement, bullets, life cycle

**Files:**
- Create: `game/effects.py`
- Create: `game/world.py`
- Test: `tests/test_world_core.py`

**Interfaces:**
- Consumes: Tasks 1-7.
- Produces:
  - `effects.Particle` dataclass and `effects.Effects` with `particles`, `shake_amount`, `.burst(pos,color,count=12)`, `.update(dt)`, `.shake(amount)`, `.offset()->tuple[int,int]`, `.draw(surface, offset=(0,0))`
  - `world.World` construction `World(level_index:int, seed:int|None=None, player_stats:list[PlayerStats]|None=None, upgrade_levels:list[dict[str,int]]|None=None)`
  - Attributes: `level_index`, `level`, `grid`, `base`, `players`, `enemies`, `bullets`, `grenades`, `lasers`, `boss`, `effects`, `status` (`"playing" | "cleared" | "lost" | "victory"`), `shared_lives`, `quota_remaining`, `elapsed`, `seed`, `upgrade_levels`, `player_stats`
  - Methods: `point_to_tile`, `is_brick`, `is_steel`, `tile_center`, `destroy_brick(tx,ty)`, `move_entity(entity,direction,dt)->bool`, `update(dt, inputs:list[PlayerInput])->None`, `damage_player(player,amount)`, `damage_base(amount)`, `find_path(start,goal)`, `base_entrances`

**Bullet ownership convention:** `friendly=True` means player-owned; `owner_id` is the player id or `-1` for enemies.

- [ ] **Step 1: Write failing effects tests**

Particles lose life and disappear; shake decays to 0; `offset()` is `(0,0)` when shake is 0; draw works on a headless `pygame.Surface((320,240))`.

- [ ] **Step 2: Write failing world-core tests**

Assert: players spawn at `PLAYER_SPAWNS`; base starts at 3 with shield from stats; movement is blocked by brick and steel but slides along the free axis; a friendly bullet destroys a brick and disappears; a friendly bullet does not damage players or the base; an enemy bullet damages a player and the base; a player at 1 HP is destroyed and draws a revive after 3 s; a destroyed player consumes one shared life and respawns with 2 s invulnerability; with shared lives 0 the player is eliminated instead; both eliminated sets `status="lost"`; base at 0 sets `status="lost"`; `status="lost"` freezes further updates; player fire respects `fire_interval`; friendly bullets damage enemies.

- [ ] **Step 3: Run tests, expect import failure**

Run: `.venv/bin/pytest tests/test_world_core.py -q`
Expected: FAIL.

- [ ] **Step 4: Implement effects and world core**

`move_entity` does per-axis AABB sweeps against brick/steel and the playfield; tanks are 36x36 and enemies use their own size. Bullets move in substeps no larger than 6 px so they cannot tunnel through a tile. Bullet-vs-wall: brick destroyed, bullet dies; steel bullet dies. Bullet-vs-player only for non-friendly bullets; bullet-vs-base only for non-friendly. Player respawn uses `Player.revive` near the base. Level start sets `shared_lives = 3 + sum(stats.extra_lives for living players)` and `base.reset_for_level(sum(stats.base_shield))`. Use `world.effects.burst` and `world.effects.shake` on impacts. No skill/spawn logic yet (Tasks 9-10); `update` may call placeholder private hooks `_update_skills` and `_update_spawning` that do nothing in this task.

- [ ] **Step 5: Run tests, verify pass**

Run: `.venv/bin/pytest tests/test_world_core.py -q`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add game/effects.py game/world.py tests/test_world_core.py
git commit -m "feat: add world core, collisions, bullets, and revives"
```

---

### Task 9: World combat skills — grenades, lasers, and damage matrix

**Files:**
- Modify: `game/world.py`
- Test: `tests/test_world_combat.py`

**Interfaces:**
- Consumes: Task 8 world plus `game.skills`, Task 3 upgrades (for stats).
- Produces:
  - `World.throw_grenade(player)->bool`, `World.fire_laser(player)->bool`
  - `World.resolve_grenade(grenade)->None`
  - `World.apply_upgrade(player_id:int, upgrade_id:str)->bool`
  - `World.throw_grenade` respects `player.grenade_timer` and uses `stats.grenade_cooldown`; `fire_laser` respects `player.laser_timer` and `stats.laser_cooldown`.
  - Grenade explosion renders through `world.grenades` and `world.effects`; lasers remain in `world.lasers` for `0.12 s`.

- [ ] **Step 1: Write failing combat tests**

Assert the full matrix: player grenade damages enemies fully and both players at 35% (including the thrower), destroys brick tiles in radius, never damages the base; player laser damages every enemy along its path, ignores both players and the base, destroys exactly the first brick and ends there, and is blocked by steel; grenade that lands on steel still explodes and destroys nearby bricks; grenade split creates the configured number of explosions; laser range respects `PlayerStats.laser_range`; cooldowns prevent immediate reuse and tick down with time; `apply_upgrade` updates the live player's stats and rejects capped upgrades.

- [ ] **Step 2: Run tests, expect failure**

Run: `.venv/bin/pytest tests/test_world_combat.py -q`
Expected: FAIL (`throw_grenade`/`fire_laser` missing or incorrect).

- [ ] **Step 3: Implement skill resolution**

`throw_grenade` creates a `Grenade` toward `direction`, sets `player.grenade_timer`, and plays a subtle burst. On landing, `resolve_grenade` destroys every brick whose tile center is inside any explosion radius, damages every living enemy inside any radius by `grenade.damage`, and damages each living player inside any radius by `round(grenade.damage * 0.35)`; base is never touched. `fire_laser` calls `compute_laser`, sets `player.laser_timer`, appends the beam, kills the first brick, and damages each enemy whose center is within 18 px of the beam segment by `laser_damage`, respecting pierce. Grenade/laser never damage their owner's allies (players). Use `effects.burst`/`shake` on hit. Apply upgrade through `upgrades.apply_upgrade`; when `max_hp` increases, heal by the delta.

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/bin/pytest tests/test_world_combat.py -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add game/world.py tests/test_world_combat.py
git commit -m "feat: add grenade and laser combat resolution"
```

---

### Task 10: Enemy spawning, waves, elites, boss integration, and level progression

**Files:**
- Modify: `game/world.py`
- Test: `tests/test_world_progression.py`

**Interfaces:**
- Consumes: Tasks 6-9.
- Produces:
  - `World.spawn_enemy(kind:str, tile:tuple[int,int]|None=None) -> Enemy`
  - `World.find_path(start,goal) -> list[tuple[int,int]]|None`
  - `World.move_enemy(enemy,direction,dt)->bool`, `World.enemy_fire(enemy,direction)`, `World.demolisher_blast(enemy)`
  - `World.line_of_sight(a:pygame.Vector2,b:pygame.Vector2)->bool`
  - `World.enemy_fire_at(origin,target,speed,damage)`, `World.enemy_radial_burst(origin,count,speed,damage)`, `World.boss_laser(origin,direction)`
  - `World.spawn_quota`, `World.spawn_timer`, `World.max_active`, `World.elite_spawned`, `World.boss`
  - `World.remaining_enemies` property = living enemies + pending quota.
  - On boss death, `status="victory"`; on normal/elite clear, `status="cleared"`.

- [ ] **Step 1: Write failing progression tests**

Assert: `ENEMY_QUOTA[level]` becomes `quota_remaining`; spawning stops at `max_active`; spawn timer respects per-level `SPAWN_INTERVAL`; elite levels spawn exactly one elite plus normal enemies; boss level spawns a `Boss` and zero quota; clearing all enemies after quota reaches 0 sets `status="cleared"`; boss death sets `status="victory"`; `remaining_enemies` counts pending + living; enemy path avoids steel; enemy bullets damage players/base; demolisher blast damages nearby players and bricks; a full 8-level sequence can be constructed without error and every generated grid validates; `World` never spawns enemies on steel.

- [ ] **Step 2: Run tests, expect failure**

Run: `.venv/bin/pytest tests/test_world_progression.py -q`
Expected: FAIL (spawning/boss integration missing).

- [ ] **Step 3: Implement spawning and progression**

At level start: if `level_index == BOSS_LEVEL` create the boss at the top center and set quota 0; otherwise set quota from `ENEMY_QUOTA[level_index]`, `max_active = MAX_ACTIVE_ENEMIES[level_index]`, and if `level_index in ELITE_LEVELS`, spawn one elite immediately. The elite is additional pressure: it does not reduce `quota_remaining`, but it does occupy one active-enemy slot until killed. Spawns choose a random `ENEMY_SPAWNS` tile and avoid occupied tiles; if the chosen tile is occupied, try the next. Enemies update each frame through `Enemy.update(dt, world)`. Enemies killed by bullets/explosions/beams decrement living count naturally. `remaining_enemies` drives the clear condition; require quota 0 and no living enemies. On clear set status once. Boss death calls a `_on_boss_dead` hook that sets `"victory"` and spawns particles.

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/bin/pytest tests/test_world_progression.py -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add game/world.py tests/test_world_progression.py
git commit -m "feat: add waves, elite spawns, boss integration, and level clear"
```

---

### Task 11: Renderer and HUD

**Files:**
- Create: `game/render.py`
- Test: `tests/test_render_smoke.py`

**Interfaces:**
- Consumes: `config`, `game.world.World`, `game.upgrades.Upgrade`, `game.effects`.
- Produces:
  - `render.Renderer(screen: pygame.Surface)` with `.draw_world(world)`, `.draw_title(t:float)`, `.draw_controls()`, `.draw_upgrade(offers:list[list[Upgrade]], levels:list[dict[str,int]], choosing:int)`, `.draw_pause()`, `.draw_game_over(world,reason:str)`, `.draw_victory(world)`, `.draw_intro(level_index:int,remaining:float)`
  - HUD shows both players' HP/eliminated/respawn state, grenade and laser cooldown bars, shared revives, base HP/shield, level progress 1-8, enemies remaining.
  - Renderer uses English labels only (default pygame font), so it works without CJK fonts.

- [ ] **Step 1: Write failing smoke tests**

Headless tests: construct a `World(0, seed=1)`, call every `draw_*` method; assert no exception and that drawing a world changes at least 100 pixels from the background color; assert HUD area is not empty; assert title/upgrade cards render at least 3 distinct colors; assert no `pygame.error`.

- [ ] **Step 2: Run test, expect import failure**

Run: `.venv/bin/pytest tests/test_render_smoke.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement renderer**

Draw at native 1280x720. Background: deep blue-gray floor with a 48 px grid, subtle vignette and scanlines. Walls: brick with mortar lines, steel panels with bevels and white holo edges. Tanks: treads, hull, turret, direction barrel, additive glow; P1 cold blue, P2 amber, enemies red/orange, elite magenta, boss large with phase-colored core. Base: 2x2 prism with HP pips and shield ring. Bullets: bright additive circles; grenade: dotted arc, landing reticle, blast-radius ring; laser: white-blue core with wide additive glow; particles from `world.effects`. HUD bottom 96 px: two player cards, shared revive diamonds, base bar, 8-node level track, enemy counter. Overlays dim the field. Use `pygame.font.Font(None, size)` only. No random per-frame text.

- [ ] **Step 4: Run test, verify pass**

Run: `.venv/bin/pytest tests/test_render_smoke.py -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add game/render.py tests/test_render_smoke.py
git commit -m "feat: add holographic renderer and HUD"
```

---

### Task 12: Game state machine, audio, and entry point

**Files:**
- Create: `game/audio.py`
- Create: `game/states.py`
- Modify: `main.py`
- Test: `tests/test_states.py`

**Interfaces:**
- Consumes: Task 11 renderer, all simulation modules.
- Produces:
  - `audio.Audio` with `enabled`, `.play(name)`, `.toggle()`, generated tones only, silently disabled if mixer init fails.
  - `states.Game(screen)` with `.state`, `.running`, `.level_index`, `.world`, `.renderer`, `.handle_event(event)`, `.update(dt)`, `.draw()`, `.run()`
  - States: `"title"`, `"controls"`, `"playing"`, `"paused"`, `"upgrade"`, `"gameover"`, `"victory"`.
  - `main.py` supports `--seed`, `--width`, `--height` (window size only; playfield stays centered), initializes pygame/mixer defensively, and exits cleanly.
  - Run flow: title -> controls -> level 0..7; level clear -> upgrade (P1 then P2) -> next level; boss death -> victory; loss -> gameover; Enter restarts a fresh run.

- [ ] **Step 1: Write failing state tests**

Headless Game tests: starts on title; Enter on title goes to controls; Enter on controls starts level 0 in `"playing"`; Esc pauses and freezes `world.elapsed`; Esc resumes; forcing `world.status="cleared"` transitions to `"upgrade"` with 3 offers for each active player; choosing for P1 then P2 starts level 1; an eliminated player is skipped; forcing `world.status="lost"` goes to `"gameover"` and Enter starts a fresh run at level 0 with reset stats/upgrades; forcing the level-7 boss death to victory leads to `"victory"`; update+draw runs 120 frames without exception; audio disabled when mixer fails.

- [ ] **Step 2: Run test, expect import failure**

Run: `.venv/bin/pytest tests/test_states.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement audio, state machine, and main**

Audio generates 8-bit square/sine-ish tones with `pygame.mixer.Sound(buffer=bytes(...))`; no numpy. Names: `shoot`, `hit`, `explosion`, `laser`, `pick`, `lose`, `win`. All wrapped in try/except. State machine uses `pygame.time.Clock`; dt is clamped to 0.05 s. Upgrade screen uses keys 1/2/3; roll offers with `random.Random(seed + level*2 + player_id)`. New run creates fresh `PlayerStats` and empty upgrade levels. P1 then P2 selection, skipping eliminated players; current chooser shown in the renderer. Pause stores no state changes beyond the flag. Intro overlay lasts 1.2 s per level but simulation runs.

- [ ] **Step 4: Run test, verify pass**

Run: `.venv/bin/pytest tests/test_states.py -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add game/audio.py game/states.py main.py tests/test_states.py
git commit -m "feat: add state machine, menus, upgrades flow, and entry point"
```

---

### Task 13: Full-game integration, balance pass, and documentation

**Files:**
- Create: `tests/test_integration.py`
- Modify: `README.md`
- Modify: any modules needed for integration fixes
- Test: whole suite

**Interfaces:**
- Consumes: everything.
- Produces: a runnable `main.py` and a documented install/run/test workflow.

- [ ] **Step 1: Write failing integration tests**

Assert: constructing a `Game`, starting a new run, and simulating 120 update+draw frames at 1/60 s produces no exception; levels 0..7 each construct with valid grids and expected spawn setup; a complete simulated transition path (title -> controls -> playing -> upgrade -> next level ... -> boss victory) reaches `"victory"` by forcing world statuses; `requirements.txt` lists pygame-ce and pytest; README contains install, run, controls (WASD/Space/F and arrows/./slash), and test commands.

- [ ] **Step 2: Run tests, expect failures where integration is incomplete**

Run: `.venv/bin/pytest tests/test_integration.py -q`
Expected: FAIL until integration fixes are made.

- [ ] **Step 3: Implement integration fixes and README**

Update README in Chinese with: project overview, `python3 -m venv .venv`, `.venv/bin/pip install -r requirements.txt`, `.venv/bin/python main.py`, controls table, pytest command, design/plan links. Fix any wiring bugs found by the integration test. Keep all tunables in config/upgrades.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all tests pass, no warnings about unraisable exceptions.

- [ ] **Step 5: Run a headless smoke launch**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -c "import pygame; from game.states import Game; pygame.init(); s=pygame.display.set_mode((1280,720)); g=Game(s); [ (g.update(1/60), g.draw()) for _ in range(120) ]; print('ok')"`
Expected: prints `ok` with no traceback.

- [ ] **Step 6: Commit**

```bash
git add README.md tests/test_integration.py
git commit -m "test: verify full 8-level game integration and document usage"
```

---

## Self-Review

**Spec coverage:** Structure of 8 levels, quotas, elites, boss, win/loss, base, shared revives, damage matrix, skills, enemies, generation validation, upgrades, UI flow, controls, HUD, visuals, audio, tests, dt, config centralization are each owned by a task. Procedural audio is optional in the spec but included as a graceful-degradation module.

**Type consistency:** `PlayerInput` is defined in Task 4 and consumed by Tasks 8, 12. `PlayerStats` is defined in Task 1 and consumed by Tasks 3, 4, 8-10. `World` attribute names used by enemies/boss/renderer/states are pinned in Tasks 8 and 10. `status` values are fixed as `playing/cleared/lost/victory`.

**Uncovered review risks:** The six Review Focus lines each have a named test in Tasks 2, 9, 8, 3, and 11.
