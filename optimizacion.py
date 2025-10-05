import argparse
import math
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageChops
except ImportError:
    print("Pillow is required. Install it with `pip install Pillow`.", file=sys.stderr)
    raise SystemExit(1)

# Allow processing ultra-large images such as NASA mosaics.
Image.MAX_IMAGE_PIXELS = None

if hasattr(Image, "Resampling"):
    RESAMPLING = Image.Resampling.LANCZOS
    MASK_RESAMPLING = Image.Resampling.NEAREST
else:
    RESAMPLING = Image.LANCZOS
    MASK_RESAMPLING = Image.NEAREST

TIF_SUFFIXES = {".tif", ".tiff"}
MASK_SUFFIXES = {".tif", ".tiff", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert .tif images into a slippy-map style tile pyramid (zoom/x/y)."
    )
    parser.add_argument("input", help="Path to a .tif file or a directory that contains .tif/.tiff files.")
    parser.add_argument("output", help="Directory where the tile pyramids will be written.")
    parser.add_argument("--tile-size", type=int, default=256, dest="tile_size", help="Tile size in pixels (default: 256).")
    parser.add_argument("--min-zoom", type=int, default=0, dest="min_zoom", help="Lowest zoom level to generate (default: 0).")
    parser.add_argument("--max-zoom", type=int, default=None, dest="max_zoom", help="Highest zoom level to generate. Defaults to the maximum needed for the image.")
    parser.add_argument(
        "--format",
        dest="image_format",
        default="png",
        choices=["png", "jpg", "jpeg", "webp"],
        help="Image format for the tiles (default: png).",
    )
    parser.add_argument("--quality", type=int, default=90, help="Quality for lossy formats like JPEG/WEBP (default: 90).")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the existing tile directory if it already exists.",
    )
    parser.add_argument(
        "--mask",
        default=None,
        help="Optional mask TIFF/PNG file or directory to use as alpha channel.",
    )
    return parser.parse_args()


def collect_tifs(input_path: Path) -> List[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() in TIF_SUFFIXES:
            return [input_path]
        raise ValueError(f"{input_path} is not a .tif/.tiff file.")
    if input_path.is_dir():
        files = sorted(p for p in input_path.rglob("*") if p.suffix.lower() in TIF_SUFFIXES)
        return files
    raise FileNotFoundError(f"No such file or directory: {input_path}")


def compute_zoom_bounds(
    width: int,
    height: int,
    tile_size: int,
    min_zoom: int,
    max_zoom_arg: Optional[int],
) -> Tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive.")
    if tile_size <= 0:
        raise ValueError("Tile size must be positive.")
    if min_zoom < 0:
        raise ValueError("min_zoom must be zero or positive.")

    max_dim = max(width, height)
    if max_dim <= tile_size:
        auto_max = min_zoom
    else:
        auto_max = min_zoom + math.ceil(math.log(max_dim / tile_size, 2))

    if max_zoom_arg is None:
        final_max = auto_max
    else:
        if max_zoom_arg < min_zoom:
            raise ValueError("max_zoom cannot be smaller than min_zoom.")
        final_max = max_zoom_arg

    return min_zoom, final_max


def save_tile(tile_image: Image.Image, path: Path, image_format: str, quality: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = image_format.lower()
    save_kwargs = {}
    image_to_save = tile_image
    converted = False

    if fmt in {"jpg", "jpeg"}:
        image_to_save = tile_image.convert("RGB")
        converted = True
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
        fmt = "JPEG"
    elif fmt == "png":
        fmt = "PNG"
    elif fmt == "webp":
        fmt = "WEBP"
        save_kwargs["quality"] = quality
    else:
        raise ValueError(f"Unsupported image format: {image_format}")

    image_to_save.save(path, format=fmt, **save_kwargs)

    if converted:
        image_to_save.close()


def apply_mask(base_image: Image.Image, mask_path: Path) -> None:
    try:
        with Image.open(mask_path) as mask_src:
            mask = mask_src.convert("L")
    except OSError as exc:
        raise ValueError(f"Failed to open mask {mask_path}: {exc}") from exc

    if mask.size != base_image.size:
        mask = mask.resize(base_image.size, MASK_RESAMPLING)

    base_alpha = base_image.getchannel("A")
    combined = ImageChops.multiply(base_alpha, mask)
    base_image.putalpha(combined)
    mask.close()


def generate_tiles(
    base_image: Image.Image,
    tile_size: int,
    min_zoom: int,
    max_zoom: int,
    tile_root: Path,
    image_format: str,
    quality: int,
) -> None:
    width, height = base_image.size
    total_tiles = 0

    for zoom in range(min_zoom, max_zoom + 1):
        scale_factor = 2 ** (max_zoom - zoom)
        if scale_factor == 1:
            level_image = base_image
            cleanup_level = False
        else:
            new_width = max(1, math.ceil(width / scale_factor))
            new_height = max(1, math.ceil(height / scale_factor))
            level_image = base_image.resize((new_width, new_height), RESAMPLING)
            cleanup_level = True

        tiles_x = math.ceil(level_image.width / tile_size)
        tiles_y = math.ceil(level_image.height / tile_size)
        print(f"    zoom {zoom}: {tiles_x} x {tiles_y} tiles")

        for x_index in range(tiles_x):
            for y_index in range(tiles_y):
                left = x_index * tile_size
                upper = y_index * tile_size
                right = min(left + tile_size, level_image.width)
                lower = min(upper + tile_size, level_image.height)

                tile_image = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
                tile_image.paste(level_image.crop((left, upper, right, lower)), (0, 0))
                tile_path = tile_root / str(zoom) / str(x_index) / f"{y_index}.{image_format.lower()}"
                save_tile(tile_image, tile_path, image_format, quality)
                tile_image.close()
                total_tiles += 1

        if cleanup_level:
            level_image.close()

    print(f"    generated {total_tiles} tiles")


def process_tif(
    tif_path: Path,
    mask_path: Optional[Path],
    output_root: Path,
    args: argparse.Namespace,
) -> bool:
    print(f"* {tif_path}")
    try:
        with Image.open(tif_path) as src:
            base_image = src.convert("RGBA")
    except OSError as exc:
        print(f"  ! Failed to open image: {exc}", file=sys.stderr)
        return False

    print(f"  - image size: {base_image.width}x{base_image.height}")

    if mask_path is not None:
        print(f"  - applying mask: {mask_path}")
        try:
            apply_mask(base_image, mask_path)
        except ValueError as exc:
            print(f"  ! {exc}", file=sys.stderr)
            base_image.close()
            return False

    try:
        min_zoom, max_zoom = compute_zoom_bounds(
            base_image.width,
            base_image.height,
            args.tile_size,
            args.min_zoom,
            args.max_zoom,
        )
    except ValueError as exc:
        print(f"  ! {exc}", file=sys.stderr)
        base_image.close()
        return False

    print(f"  - zoom levels: {min_zoom}-{max_zoom}")

    tile_root = output_root / tif_path.stem
    if tile_root.exists():
        if args.overwrite:
            shutil.rmtree(tile_root)
        else:
            print(f"  ! {tile_root} already exists. Use --overwrite to regenerate.", file=sys.stderr)
            base_image.close()
            return False

    tile_root.mkdir(parents=True, exist_ok=True)

    try:
        generate_tiles(base_image, args.tile_size, min_zoom, max_zoom, tile_root, args.image_format, args.quality)
    finally:
        base_image.close()

    print(f"  - Tiles saved in {tile_root} (zooms {min_zoom}-{max_zoom})")
    return True


def build_mask_lookup(mask_arg: Optional[str], tif_files: List[Path]) -> Dict[Path, Path]:
    if not mask_arg:
        return {}

    mask_path = Path(mask_arg).expanduser()
    if not mask_path.exists():
        raise FileNotFoundError(f"Mask path does not exist: {mask_path}")

    if mask_path.is_file():
        if len(tif_files) != 1:
            raise ValueError("A single mask file can only be used when processing one TIFF input.")
        return {tif_files[0]: mask_path}

    if mask_path.is_dir():
        mask_files = {
            p.stem: p
            for p in mask_path.rglob("*")
            if p.is_file() and p.suffix.lower() in MASK_SUFFIXES
        }
        if not mask_files:
            raise ValueError(f"No mask files were found inside {mask_path}.")

        mapping: Dict[Path, Path] = {}
        for tif_file in tif_files:
            candidate = mask_files.get(tif_file.stem)
            if candidate is not None:
                mapping[tif_file] = candidate
        return mapping

    raise FileNotFoundError(f"Mask path is neither a file nor directory: {mask_path}")


def main() -> int:
    args = parse_args()
    args.image_format = args.image_format.lower()

    input_path = Path(args.input).expanduser()
    output_root = Path(args.output).expanduser()

    if not input_path.exists():
        print(f"Input path does not exist: {input_path}", file=sys.stderr)
        return 1

    try:
        tif_files = collect_tifs(input_path)
    except (ValueError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if not tif_files:
        print("No .tif/.tiff files were found to process.", file=sys.stderr)
        return 1

    output_root.mkdir(parents=True, exist_ok=True)

    try:
        mask_lookup = build_mask_lookup(args.mask, tif_files)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    any_success = False
    for tif_file in tif_files:
        mask_for_image = mask_lookup.get(tif_file)
        if args.mask and mask_for_image is None:
            print(f"* {tif_file}\n  ! No matching mask found. Skipping.", file=sys.stderr)
            continue
        try:
            if process_tif(tif_file, mask_for_image, output_root, args):
                any_success = True
        except Exception as exc:  # noqa: BLE001
            print(f"  ! Unexpected error processing {tif_file}: {exc}", file=sys.stderr)

    if not any_success:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
