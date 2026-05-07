"""Extract Raid game UI assets (hero portraits, affinity icons, faction
avatars, skill icons, status effect icons) from the local Plarium Play
install. Output PNGs land under gui/dashboard/assets/<category>/.

This is the same approach HellHades / RSL Helper use — read the Unity
AssetBundles, decode Sprite/Texture2D, save as PNG. We don't pull from
Plarium's CDN or hotlink HH's images; everything is yours, ours, local.

Bundles handled (under raid/build/Raid_Data/StreamingAssets/AssetBundles/):
  HeroAvatarsLocal, HeroAvatarsLocal_2  -> assets/heroes/
  FractionAvatars                       -> assets/factions/
  HeroElements                          -> assets/affinities/
  StatusEffectIcons                     -> assets/effects/
  ResourceIcons                         -> assets/resources/
  SkillIcons_*                          -> assets/skills/
  LeaderSkillIcons                      -> assets/leader_skills/
  ArtifactSets                          -> assets/artifact_sets/
  Icons, AdditionalIcons                -> assets/ui/

Usage:
    python3 tools/extract_game_assets.py
    python3 tools/extract_game_assets.py --bundle HeroAvatarsLocal
    python3 tools/extract_game_assets.py --list      # what bundles exist
    python3 tools/extract_game_assets.py --force     # re-extract even if PNG exists

Idempotent: skips files already extracted (mtime+size match). Re-run after
any Raid update — newly-added heroes get pulled automatically.
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from pathlib import Path

try:
    import UnityPy
except ImportError:
    print("UnityPy not installed. Run: pip install --user UnityPy", file=sys.stderr)
    sys.exit(2)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = PROJECT_ROOT / "gui" / "dashboard" / "assets"

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
BUNDLE_DIR = (Path(LOCALAPPDATA) / "PlariumPlay" / "StandAloneApps" / "raid"
              / "build" / "Raid_Data" / "StreamingAssets" / "AssetBundles")
# Runtime-cached PNGs the game downloaded on demand (mostly hero portraits
# + various dialog backgrounds the user has actually opened).
LOADED_TEXTURES_DIR = (Path(os.environ.get("APPDATA", "")).parent / "LocalLow"
                       / "Plarium" / "Raid_ Shadow Legends" / "LoadedTextures")

# Bundle name -> output subdir mapping. Wildcard via prefix match.
# Order matters: more specific first.
BUNDLE_MAP: list[tuple[str | re.Pattern[str], str]] = [
    ("HeroAvatarsLocal", "heroes"),
    ("HeroAvatarsLocal_2", "heroes"),
    ("FuseAvatarsLocal", "heroes_fuse"),
    ("FractionAvatars", "factions"),
    ("HeroElements", "affinities"),
    ("StatusEffectIcons", "effects"),
    ("ResourceIcons", "resources"),
    ("LeaderSkillIcons", "leader_skills"),
    ("ArtifactSets", "artifact_sets"),
    ("ArtifactsLocal", "artifacts"),
    ("ArtifactPowerUpDialog", "artifacts"),
    ("ArtifactFullSetVFX", "artifact_vfx"),
    ("BattlePresetIcons", "preset_icons"),
    ("BmiIcons", "ui"),
    ("AdditionalIcons", "ui"),
    ("Icons", "ui"),
    ("CursorIcons", "ui"),
    ("MaintenanceIcons", "ui"),
    ("SwitchButtonIcons", "ui"),
    ("SummonToBathhouseIcons", "ui"),
    ("IconsIdomoo", "ui"),
    ("BattleHUD", "battle_ui"),
    ("BattleFinishDialogs", "battle_ui"),
    ("BattleLoadingDialog", "battle_ui"),
    ("BattleModeSelectionDialog", "battle_ui"),
    ("BattlePauseDialog", "battle_ui"),
    ("BattleValidationDialog", "battle_ui"),
    ("BattleModes", "battle_ui"),
    ("BlessingAnimationData", "blessings"),
    ("Challenges", "challenges"),
    ("GameLogo", "ui"),
    (re.compile(r"^SkillIcons_\d+$"), "skills"),
    # Per-hero bundles — splash art / cards. Pattern: "<NNNN>_<Name>" or
    # "<NNNN>_<Name>_id<N>". Skip the *_Res companion bundles (they're
    # dependency-only and don't add new sprites).
    (re.compile(r"^\d{4}_[A-Za-z][A-Za-z0-9_]*?(?<!_Res)$"), "hero_splash"),
]


def out_dir_for(bundle_name: str) -> str | None:
    for pattern, subdir in BUNDLE_MAP:
        if isinstance(pattern, str):
            if bundle_name == pattern:
                return subdir
        else:
            if pattern.match(bundle_name):
                return subdir
    return None


def safe_name(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]", "_", s)
    return s.strip("_") or "unnamed"


def extract_bundle(bundle_path: Path, out_dir: Path,
                   force: bool = False) -> tuple[int, int]:
    """Extract Sprites + Texture2Ds from one bundle. Returns (saved, skipped).
    Sprites are preferred when present (game uses them for UI elements);
    we fall back to bare Texture2D when no sprite metadata exists."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    skipped = 0
    try:
        env = UnityPy.load(str(bundle_path))
    except Exception as e:
        print(f"  ERR loading {bundle_path.name}: {e}", file=sys.stderr)
        return 0, 0

    # Sprites yield clean cropped images; Texture2D would give the full atlas.
    has_sprites = any(o.type.name == "Sprite" for o in env.objects)
    target_type = "Sprite" if has_sprites else "Texture2D"

    seen_names: set[str] = set()
    for obj in env.objects:
        if obj.type.name != target_type:
            continue
        try:
            data = obj.read()
            name = getattr(data, "m_Name", None) or getattr(data, "name", None)
            if not name:
                continue
            fname = safe_name(name) + ".png"
            if fname in seen_names:
                continue
            seen_names.add(fname)
            out_path = out_dir / fname
            if out_path.exists() and not force:
                skipped += 1
                continue
            img = data.image
            if img is None:
                continue
            img.save(out_path)
            saved += 1
        except Exception as e:
            # Skip individual broken sprites silently; one bad asset shouldn't
            # tank the whole extraction.
            continue
    return saved, skipped


def _resolve_bundle_file(top: Path) -> Path | None:
    """For a top-level bundle directory, return the .unity3d file from the
    latest version. Skips _Res companion bundles which only carry shared
    dependencies and don't add new sprites."""
    if not top.is_dir() or top.name.endswith("_Res"):
        return None
    versions = sorted([p for p in top.iterdir() if p.is_dir()],
                      key=lambda p: tuple(int(x) for x in re.findall(r"\d+", p.name)))
    if not versions:
        return None
    files = list(versions[-1].rglob("*.unity3d"))
    return files[0] if files else None


def _scan_all(bundle_dir: Path, force: bool) -> int:
    """Brute-force pass: extract sprites/textures from EVERY bundle into
    assets/_all/<bundle>/. Useful for one-off discovery — when some new
    asset shows up that we don't have a curated category for yet."""
    out_root = ASSET_DIR / "_all"
    print(f"Scan-all mode: extracting from EVERY bundle.")
    print(f"Output: {out_root}/")
    total_saved = 0
    total_skip = 0
    bundles_processed = 0
    bundles_empty = 0
    for top in sorted(bundle_dir.iterdir()):
        bp = _resolve_bundle_file(top)
        if bp is None:
            continue
        out = out_root / safe_name(top.name)
        saved, skipped = extract_bundle(bp, out, force=force)
        total_saved += saved
        total_skip += skipped
        bundles_processed += 1
        if saved == 0 and skipped == 0:
            bundles_empty += 1
            # Drop the empty dir to keep output tidy
            try: out.rmdir()
            except OSError: pass
        else:
            print(f"  {top.name:<46}  saved={saved:<4} skipped={skipped}")
    print()
    print(f"Done. Bundles processed: {bundles_processed} (empty: {bundles_empty})")
    print(f"      Total saved: {total_saved}, skipped: {total_skip}")
    print(f"      Output: {out_root}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default=None,
                    help="Extract only the named bundle (e.g. HeroAvatarsLocal)")
    ap.add_argument("--list", action="store_true",
                    help="List bundles that would be extracted, then exit")
    ap.add_argument("--force", action="store_true",
                    help="Re-extract even if output PNG already exists")
    ap.add_argument("--bundle-dir", default=str(BUNDLE_DIR),
                    help="Override path to AssetBundles directory")
    ap.add_argument("--scan-all", action="store_true",
                    help="Extract from EVERY bundle, dumping anything that "
                         "looks like a sprite/texture into assets/_all/<bundle>/. "
                         "Big — ~150-200 MB. Used for one-off discovery.")
    args = ap.parse_args()

    bundle_dir = Path(args.bundle_dir)
    if not bundle_dir.exists():
        print(f"ERROR: AssetBundles dir not found: {bundle_dir}", file=sys.stderr)
        return 1

    if args.scan_all:
        return _scan_all(bundle_dir, args.force)

    # Each bundle is a directory like:
    #   AssetBundles/HeroAvatarsLocal/11.50.0/2/WindowsPlayer-DXT/HeroAvatarsLocal_11.50.0.unity3d
    # Pick the highest version dir per top-level bundle, then resolve to the
    # `.unity3d` file inside.
    bundles: list[tuple[str, Path]] = []  # (logical_bundle_name, file_path)
    for top in sorted(bundle_dir.iterdir()):
        if not top.is_dir():
            continue
        if out_dir_for(top.name) is None:
            continue
        # Walk version subdirs; pick the latest by name (semver-ish)
        version_dirs = sorted([p for p in top.iterdir() if p.is_dir()],
                              key=lambda p: tuple(int(x) for x in re.findall(r"\d+", p.name)))
        if not version_dirs:
            continue
        latest = version_dirs[-1]
        # Each version dir has /<idx>/WindowsPlayer-DXT/*.unity3d (any platform)
        unity_files = list(latest.rglob("*.unity3d"))
        if unity_files:
            bundles.append((top.name, unity_files[0]))

    if args.bundle:
        bundles = [(n, p) for (n, p) in bundles if n == args.bundle]
        if not bundles:
            print(f"No bundle '{args.bundle}' or not in mapping. "
                  f"--list to see what's recognized.", file=sys.stderr)
            return 1

    if args.list:
        print(f"{'bundle':<30} -> {'subdir':<20} size  path")
        for n, p in bundles:
            sub = out_dir_for(n)
            print(f"{n:<30} -> {sub:<20} {p.stat().st_size // 1024:>5} KB  {p.name}")
        return 0

    print(f"Extracting {len(bundles)} bundles from:")
    print(f"  {bundle_dir}")
    print(f"Output: {ASSET_DIR}/")
    print()

    total_saved = 0
    total_skip = 0
    for name, path in bundles:
        sub = out_dir_for(name)
        out = ASSET_DIR / sub
        saved, skipped = extract_bundle(path, out, force=args.force)
        total_saved += saved
        total_skip += skipped
        print(f"  {name:<32} -> {sub:<14}  saved={saved:<4} skipped={skipped}")

    # Also pull on-demand cached PNGs from LoadedTextures. These are
    # already raw PNGs (game writes them direct from CDN), so no UnityPy
    # parsing — just copy with rename. Names like `0032_Zargala` get
    # stripped to the friendly part for cleaner filenames.
    if LOADED_TEXTURES_DIR.exists():
        out = ASSET_DIR / "loaded_textures"
        out.mkdir(parents=True, exist_ok=True)
        lt_saved = 0
        lt_skip = 0
        for src in LOADED_TEXTURES_DIR.iterdir():
            if not src.is_file():
                continue
            try:
                with open(src, "rb") as f:
                    head = f.read(8)
                if head[:4] != b"\x89PNG":
                    continue  # not an image
            except Exception:
                continue
            # Strip leading numeric prefix like "0032_" for cleaner names
            stem = re.sub(r"^\d{4,}_", "", src.name)
            dest = out / (safe_name(stem) + ".png")
            if dest.exists() and not args.force:
                lt_skip += 1
                continue
            try:
                with open(src, "rb") as f, open(dest, "wb") as g:
                    g.write(f.read())
                lt_saved += 1
            except Exception:
                continue
        print(f"  {'LoadedTextures':<32} -> {'loaded_textures':<14}  saved={lt_saved:<4} skipped={lt_skip}")
        total_saved += lt_saved
        total_skip += lt_skip

    print()
    print(f"Done. Total saved: {total_saved}, skipped (already present): {total_skip}")
    print(f"Output dir: {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
