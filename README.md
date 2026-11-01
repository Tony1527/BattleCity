# 坦克大战：全息军械库（Battle City: Holographic Armory）

一款使用 pygame 实现的本地同屏双人合作坦克防守游戏。两名玩家共用同一块键盘，在程序生成、可破坏的网格迷宫中抵御敌人、保护基地，依次通过 3 个普通关（第 1-3 关）、精英关 1（第 4 关）、2 个普通关（第 5-6 关）、精英关 2（第 7 关），最后挑战最终 Boss（第 8 关），共 8 关（5 个普通关、2 个精英关和 1 个 Boss 关）。

两位玩家的定位不同：P1 使用范围爆炸的手榴弹清群，P2 使用高伤直线激光点杀和穿透。每关结束后两人各自三选一升级，形成不同流派；本关已出局的玩家跳过该关升级，并在下一关开始时回归。游戏不依赖任何外部图片或音频素材，所有画面与音效均由 pygame 程序化生成。

## 安装

需要 Python 3。建议使用项目内的虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows 下请将 `.venv/bin/` 替换为 `.venv\Scripts\`。

依赖见 `requirements.txt`：`pygame-ce` 与 `pytest`。

## 运行

```bash
.venv/bin/python main.py
```

可选参数：

```bash
.venv/bin/python main.py --seed 42 --width 1280 --height 720
```

`--seed` 用于复现同一局关卡与升级随机序列，`--width` / `--height` 用于指定窗口尺寸。

## 操作

| 功能 | P1（冷蓝） | P2（琥珀） |
| --- | --- | --- |
| 移动 | `WASD` | 方向键 `↑` `↓` `←` `→` |
| 普通射击 | `Space` | `.`（句点） |
| 技能 | `F` 手榴弹 | `/` 激光 |

| 通用按键 | 功能 |
| --- | --- |
| `Esc` | 暂停 / 继续 |
| `Enter` | 确认、开始游戏、结算后重新开始 |
| `1` `2` `3` | 在关间升级界面选择对应升级 |

## 测试

运行完整测试套件：

```bash
.venv/bin/pytest -q
```

无窗口环境下的冒烟运行示例：

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -c "import pygame; from game.states import Game; pygame.init(); s=pygame.display.set_mode((1280, 720)); g=Game(s); [(g.update(1/60), g.draw()) for _ in range(120)]; print('ok')"
```

## 设计与计划

- 设计文档：[docs/superpowers/specs/2026-10-31-battlecity-design.md](docs/superpowers/specs/2026-10-31-battlecity-design.md)
- 实现计划：[docs/superpowers/plans/2026-10-31-battlecity.md](docs/superpowers/plans/2026-10-31-battlecity.md)
