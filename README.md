# 坦克大战：全息军械库（Battle City: Holographic Armory）

一款使用 pygame 实现的本地同屏双人合作坦克防守游戏。两名玩家共用同一块键盘，在程序生成、可破坏的网格迷宫中抵御敌人、保护基地，依次通过 7 个普通关（第 1-7 关，每关都会出现精英敌人），最后挑战最终 Boss（第 8 关），共 8 关（7 个普通关和 1 个 Boss 关）。

两位玩家的定位不同：P1 使用范围爆炸的手榴弹清群，P2 使用高伤直线激光点杀和穿透。每关结束后两人各自三选一升级，形成不同流派；两名玩家每关都参与升级。除内置的中文字体外，游戏不依赖任何外部图片或音频素材，所有画面与音效均由 pygame 程序化生成。

## 难度

标题界面用 `←` / `→` 切换难度，进入战场后本局难度固定：

| 难度 | 基地生命 | 敌人生命 | 敌人开火间隔 | 敌人射程 | 敌人生成间隔 | 精英生命/护盾 | Boss 生命 | Boss 攻击间隔 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 普通 | 4 | 标准 | 标准 | 标准 | 标准 | 标准 | 标准 | 标准 |
| 地狱 | 8 | ×1.5 | ×0.8 | ×1.15 | ×0.8 | ×1.5 | ×1.5 | ×0.85 |

## 关卡与敌人

游戏共 8 关，每关都会生成精英敌人。第 1 至第 7 关会在基础精英之外额外生成 1 只高速精英 X，X 的移动速度是普通炮手的 2 倍；第 1 至第 7 关的总精英数量依次为 2、2、3、3、3、4、4，第 8 关为首领战加 1 只普通精英（没有 X）。精英拥有护盾，会召唤援军并发射散射弹；X 保留护盾和召唤，但只发射单发弹，不再散射，移动更快、颜色更醒目。

## 升级

- 反应装甲：每 20 秒获得 1 秒无敌；每次选择使间隔缩短 2 秒，最低 4 秒，最多 9 层。

## 地形、陷阱与补给

- 河流：坦克无法驶入，炮弹可以飞越；有河流的关卡会在河上架设 3 座桥，每座宽 2 格。
- 桥：与普通地面一样可通行，是跨越河流的唯一通道。
- 陷阱：踩上后定身 3 秒，触发后 5 秒重新武装；对玩家和敌人同样有效。
- 基地护块：每次战斗会在基地正前方 2 格随机生成 1 个铁块（钢墙），位置在基地两列之一。
- 补给：随机出现在战场，踩到即拾取：
  - 维修：恢复 1 点生命。
  - 强化：20 秒内手雷爆炸范围翻倍，激光变为双束。
  - 无敌：6 秒内免疫伤害。

## 安装

需要 Python 3。建议使用项目内的虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows 下请将 `.venv/bin/` 替换为 `.venv\Scripts\`。

运行时依赖见 `requirements.txt`：`pygame-ce` 与 `pytest`。字体子集工具与字体元数据测试需要 `requirements-dev.txt` 中的 `fonttools` 与 `brotli`。

## 运行

```bash
.venv/bin/python main.py
```

可选参数：

```bash
.venv/bin/python main.py --seed 42 --width 1280 --height 720
```

`--seed` 用于复现同一局的关卡与升级随机序列；不传时每局都会随机生成新的本局种子，同一局内各关的种子由本局种子加上关卡序号得到。`--width` / `--height` 用于指定窗口尺寸。

## 操作

| 功能 | P1（冷蓝） | P2（琥珀） |
| --- | --- | --- |
| 移动 | `WASD` | 方向键 `↑` `↓` `←` `→` |
| 普通射击 | `Space` | `.`（句点） |
| 技能 | `F` 手榴弹 | `/` 激光 |

| 通用按键 | 功能 |
| --- | --- |
| `Esc` | 暂停 / 继续；在操作、失败、胜利界面返回标题 |
| `Enter` | 确认、开始游戏、失败后重试本关、胜利后重新开始 |
| `L` | 在标题、操作和暂停界面切换中文 / English |
| `1` `2` `3` | 在关间升级界面选择对应升级 |

## 语言

标题、操作和暂停界面按 `L` 在中文与 English 之间切换。中文文本使用项目自带的 Noto Sans SC（Noto Sans CJK 的简体中文家族）子集字体渲染。

## 失败与重试

基地被摧毁时进入结算界面。玩家被击毁后会在 3 秒后无限次复活，因此两名玩家同时阵亡不会结束本局。按 `Enter` 直接重试当前关卡，保留已获得的升级，并把基地恢复为满血；按 `Esc` 返回标题。胜利后按 `Enter` 开始新一局。

## 字体与许可

中文界面使用 `assets/fonts/NotoSansSC-Regular-subset.otf`（Noto Sans SC，Noto Sans CJK 的简体中文家族子集）。该字体按 SIL Open Font License 1.1 分发，版权归 Adobe/Source 所有，许可证全文见 `assets/fonts/OFL.txt`。

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
