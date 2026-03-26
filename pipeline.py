import os
import cv2
import numpy as np

import spimage
import stitching


def run_stitch(
    establishing_path,
    close_paths,
    output_dir,
    on_progress=None,
    partition_method="stacked",
    downsample_scale=0.5,
    canvas_scale=2.0,
    detail_transfer_radius=3,
    edge_blend_radius=5,
    output_format="jpeg",
    jpeg_quality=85,
):
    """Run the full stitching pipeline.

    Args:
        establishing_path: Path to the wide-angle establishing shot.
        close_paths: List of paths to close-up detail photos.
        output_dir: Directory to write output files.
        on_progress: Optional callback(step_name: str, fraction: float).
        partition_method: "stacked" or "voronoi".
        downsample_scale: Scale factor for feature detection (0-1).
        canvas_scale: Output canvas scale multiplier, or None for auto.
        detail_transfer_radius: Blur radius for detail transfer.
        edge_blend_radius: Blur radius for edge blending.
        output_format: "png", "jpeg", or "webp".
        jpeg_quality: Quality for JPEG/WebP output (1-100).

    Returns:
        dict with keys "stitched", "homographies", "masks" pointing to output file paths.
    """

    def progress(name, fraction):
        if on_progress:
            on_progress(name, fraction)

    os.makedirs(output_dir, exist_ok=True)

    # Load images
    progress("Loading images", 0.0)
    establishing = spimage.Image.from_file(establishing_path)
    closes = [spimage.Image.from_file(p) for p in close_paths]

    job = stitching.StitchingJob(establishing, closes)

    # Feature detection & homography
    progress("Finding features & homographies", 0.10)
    job.find_homographies(downsample_scale=downsample_scale)

    # Homography visualization
    progress("Drawing homography boundaries", 0.25)
    canvas = job.establishing.copy()
    job.draw_homography_boundaries_onto(canvas)
    homographies_path = os.path.join(output_dir, "homographies.png")
    canvas.save(homographies_path)

    # Area calculation & canvas scale
    progress("Calculating areas", 0.30)
    job.calculate_areas()
    if canvas_scale is not None:
        job.canvas_scale = canvas_scale
    else:
        job.calculate_canvas_scale()

    # Mask generation
    progress("Generating masks", 0.35)
    if partition_method == "voronoi":
        job.generate_masks_voronoi()
    elif partition_method == "stacked":
        job.generate_masks_stacked()
    else:
        raise ValueError(f"Unknown partition_method: {partition_method}")

    # Mask visualization
    progress("Drawing mask boundaries", 0.40)
    canvas = job.establishing.copy()
    job.draw_mask_boundaries_onto(canvas)
    job.draw_masks_onto(canvas)
    masks_path = os.path.join(output_dir, "masks.png")
    canvas.save(masks_path)

    # Detail transfer stitching
    blur_op = lambda im: im.blur(detail_transfer_radius)
    stitch_kwargs = dict(
        detail_transfer_blur_op=blur_op,
        edge_blend_radius=edge_blend_radius,
    )

    progress("Detail transfer (part 1)", 0.45)
    job.detail_transfer_stitch_pt_1(**stitch_kwargs)

    progress("Detail transfer (part 2)", 0.75)
    job.detail_transfer_stitch_pt_2(**stitch_kwargs)

    # Save output
    progress("Saving output", 0.90)
    if output_format == "png":
        ext = "png"
        stitched_path = os.path.join(output_dir, "stitched.png")
        job.detail_transfer_stitch_output.save(stitched_path)
    elif output_format == "jpeg":
        ext = "jpg"
        stitched_path = os.path.join(output_dir, "stitched.jpg")
        arr = job.detail_transfer_stitch_output.array
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        cv2.imwrite(stitched_path, arr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    elif output_format == "webp":
        ext = "webp"
        stitched_path = os.path.join(output_dir, "stitched.webp")
        arr = job.detail_transfer_stitch_output.array
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        cv2.imwrite(stitched_path, arr, [cv2.IMWRITE_WEBP_QUALITY, jpeg_quality])
    else:
        raise ValueError(f"Unknown output_format: {output_format}")

    progress("Done", 1.0)

    return {
        "stitched": stitched_path,
        "homographies": homographies_path,
        "masks": masks_path,
    }
