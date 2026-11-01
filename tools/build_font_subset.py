from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game import i18n  # noqa: E402


def build_subset(source: Path, output: Path) -> list[str]:
    from fontTools.subset import Options, Subsetter
    from fontTools.ttLib import TTFont

    glyphs = sorted(i18n.required_glyphs())
    font = TTFont(str(source))
    try:
        available = set(font.getBestCmap())
        missing = [glyph for glyph in glyphs if ord(glyph) not in available]
        if missing:
            print(
                "warning: source font is missing glyphs: "
                + "".join(missing),
                file=sys.stderr,
            )

        options = Options()
        subsetter = Subsetter(options=options)
        subsetter.populate(unicodes=[ord(glyph) for glyph in glyphs])
        subsetter.subset(font)
        font.flavor = None
        output.parent.mkdir(parents=True, exist_ok=True)
        font.save(str(output))
    finally:
        font.close()

    manifest_path = output.parent / "glyphs.json"
    manifest_path.write_text(
        json.dumps(glyphs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return glyphs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Subset an OFL font to the game's required glyphs."
    )
    parser.add_argument("source_font", type=Path)
    parser.add_argument("output_font", type=Path)
    args = parser.parse_args(argv)

    glyphs = build_subset(args.source_font, args.output_font)
    print(
        f"wrote {args.output_font} and "
        f"{args.output_font.parent / 'glyphs.json'} ({len(glyphs)} glyphs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
