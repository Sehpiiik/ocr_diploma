import sys
from PIL import Image
import argparse
from pathlib import Path

def crop_edges(image, crop_amount):
    width, height = image.size
    
    if crop_amount * 2 >= min(width, height):
        crop = min(width, height) // 2
        print(f"Warning: crop amount too large, using max possible ({crop}px)")
    else:
        crop = crop_amount
    
    return image.crop((crop, crop, width - crop, height - crop))

def rotate_image(image, angle):
    normalized_angle = angle % 360
    return image.rotate(normalized_angle, expand=True)

def prepare_images(folder_path, output_path, image_format, angle, crop_amount):

    image_files = [f for f in folder_path.iterdir() 
                   if f.is_file() and f.suffix.lower() == f".{image_format}"]
    
    if not image_files:
        raise FileNotFoundError(
                f"no image found in {folder_path}"
            )
    
    print(f"Find {len(image_files)} files of format '{image_format}'.")
    
    output_path.mkdir(parents=True, exist_ok=True)

    for file_path in image_files:
        try:
            with Image.open(file_path) as img:
                rotated_img = rotate_image(img, angle)
                
                output_file_path = output_path / file_path.name

                if crop_amount > 0:
                    result_img = crop_edges(rotated_img, crop_amount)
                else:
                    result_img = rotated_img 
                                   
                if image_format.lower() in ["jpg", "jpeg"]:
                    result_img.save(output_file_path, quality=85, subsampling=2)
                else:
                    result_img.save(output_file_path, compress_level=3)
                print(f"Processed: {file_path.name}")
                
        except Exception as e:
            print(f"Error occurred while processing {file_path.name}: {e}")
    
    print("Done!")

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Rotates all images in the hand by 270 degrees."
        )
    )
    p.add_argument("--input", "-i", required=True, type=Path,
                   help="Input dir containing images to rotate.")
    p.add_argument("--output", "-o", type=Path, default=Path("out"),
                   help="Output dir (default: ./out).")
    p.add_argument(
        "--format", required=True,
        choices=["jpg", "png", "jpeg"],
        default="png",
        help="Image format (default: png).",
    )
    p.add_argument("--angle", "-a", type=int, default=270,
                   help="Rotation angle in degrees (default: 270).")
    p.add_argument("--crop", "-c", type=int, default=0,
                   help="Amount to crop from each edge (default: 0).")
    return p

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    
    if not args.input.is_dir():
        print(f"error: input dir not found: {args.input}", file=sys.stderr)
        return 2

    prepare_images(args.input, args.output, args.format, args.angle, args.crop)

if __name__ == "__main__":
    raise SystemExit(main())