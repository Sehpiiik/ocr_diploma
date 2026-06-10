# Noise generator

[English](./README.md) | [Русский](./README_RU.md)

Apply realistic scanner / photocopier **photometric** distortions to clean
document images **in place**. Image dimensions and the input bbox
annotations are preserved exactly - no rotation, no perspective warp, no
polygon tracking.

The pass is opt-in per document: only pairs whose annotation JSON has
`"augment": true` are touched.

## Input

```
<input_dir>/
  images/       doc_00001.png, doc_00002.png, ...
  annotations/  doc_00001.json, doc_00002.json, ...
```

Each annotation uses the schema produced by `documents_generator`. To mark a
document for augmentation, set the top-level `augment` flag to `true`:

```json
{
  "image": "doc_00001.png",
  "width": 2480,
  "height": 3508,
  "bbox_format": "xywh",
  "augment": true,
  "objects": [
    {"text": "...", "bbox": [x, y, w, h], "type": "line"}
  ]
}
```

Pairs without `"augment": true` (missing key, `false`, etc.) are skipped.

## Behaviour

For every flagged pair the generator:

1. Writes `--variants` augmented copies into the **same** `images/` and
   `annotations/` folders, named with an `_au_NN` suffix:

   ```
   <input_dir>/
     images/       doc_00001_au_01.png, doc_00001_au_02.png, ...
     annotations/  doc_00001_au_01.json, doc_00001_au_02.json, ...
   ```

2. Each new annotation is a verbatim copy of the source annotation with
   only the `image` field rewritten to the new variant filename.

3. After all variants for that pair have been written successfully, the
   **original** image and annotation are deleted.

If any write fails, the originals are left in place so the run can be
retried. Pass `--keep-originals` to disable the delete step entirely.

## Applied distortions

Per image a random subset of the catalogue fires (each effect has its own
probability, order is shuffled per image):

1. **Paper & ink** (augraphy):
   - `InkBleed`, `LowInkRandomLines`, `Letterpress`
   - `BleedThrough` (content showing from the reverse side)
2. **Photocopier / scanner artifacts** (augraphy):
   - `BadPhotoCopy` — faded regions, memory streaks
   - `DirtyDrum`, `DirtyRollers` — vertical/horizontal tonal streaks
   - `LightingGradient`, `ShadowCast` — uneven illumination
   - `BrightnessTexturize`, `SubtleNoise`
3. **Custom sensor / optics** (OpenCV + NumPy):
   - Vignette (radial darkening)
   - Scanner highlight (bright glare patch)
   - Dust & scratches
   - Horizontal scan streaks
   - Motion blur (slight scanner-bar smear)
   - Low-DPI resample (downsample + upsample, dimensions preserved)
   - Gaussian sensor noise
   - JPEG compression

All effects are pixel-level - they never change image dimensions, so bbox
coordinates remain valid for the augmented variants.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
python noise_generator.py \
    --input ../documents_generator/out \
    --variants 3 \
    --seed 42
```

| Flag | Description |
|------|-------------|
| `--input DIR` | Directory containing `images/` + `annotations/` (required). Augmented files are written back into these folders. |
| `--variants N` | Augmented variants to write per flagged pair (default: 1). Variant index is zero-padded in the `_au_NN` suffix. |
| `--seed INT` | Reproducible RNG seed. |
| `--preset {light,medium,heavy,scanner,photocopy}` | Intensity / flavour. |
| `--debug-boxes` | Draw the xywh bboxes on each saved augmented image. |
| `--limit N` | Process only the first N flagged pairs. |
| `--workers N` | Parallel worker processes (default: 1). |
| `--keep-originals` | Do not delete the source pair after writing variants. |

## Example

```bash
# Generate clean pairs and decide which ones to augment...
cd ../documents_generator && python doc_generator.py --corpus sample_corpus.txt -n 5
# (toolchain / manual step that sets "augment": true on the JSONs you want)

# ...then noise the flagged ones in place.
cd ../noise_generator
python noise_generator.py --input ../documents_generator/out --variants 2 --seed 0
```

After the run, the flagged source pair `doc_00001.{png,json}` is gone and is
replaced by `doc_00001_au_01.{png,json}` and `doc_00001_au_02.{png,json}`.

