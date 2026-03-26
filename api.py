import base64
import os
import shutil
import tempfile
import threading

import cv2
import pillow_heif
import webview
from PIL import Image as PILImage

from pipeline import run_stitch

pillow_heif.register_heif_opener()


class Api:
    def __init__(self):
        self._window = None
        self._progress = {"step": "", "fraction": 0.0}
        self._stitching = False
        self._result = None
        self._temp_dir = tempfile.mkdtemp(prefix="stitch_")

    def select_files(self):
        """Open native file dialog, return list of selected file paths."""
        file_types = ("Image Files (*.jpg;*.jpeg;*.png;*.heic;*.heif)",)
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=file_types,
        )
        if not result:
            return []
        return list(result)

    def get_thumbnails(self, paths):
        """Convert image paths to base64 thumbnails. Returns list of {name, path, data_url}."""
        thumbnails = []
        for path in paths:
            name = os.path.basename(path)
            try:
                if path.lower().endswith((".heic", ".heif")):
                    img = PILImage.open(path).convert("RGB")
                else:
                    img = PILImage.open(path).convert("RGB")

                # Resize to thumbnail
                img.thumbnail((400, 400))
                # Encode to JPEG bytes
                import io
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=80)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                data_url = f"data:image/jpeg;base64,{b64}"

                thumbnails.append({"name": name, "path": path, "data_url": data_url})
            except Exception as e:
                thumbnails.append({"name": name, "path": path, "data_url": "", "error": str(e)})
        return thumbnails

    def stitch(self, establishing_path, close_paths, settings):
        """Run stitching in a background thread. Returns immediately."""
        if self._stitching:
            return {"error": "Already stitching"}

        self._stitching = True
        self._result = None
        self._progress = {"step": "Starting...", "fraction": 0.0}

        output_dir = os.path.join(self._temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        def worker():
            try:
                result = run_stitch(
                    establishing_path=establishing_path,
                    close_paths=close_paths,
                    output_dir=output_dir,
                    on_progress=lambda step, frac: self._progress.update(
                        {"step": step, "fraction": frac}
                    ),
                    partition_method=settings.get("partition_method", "stacked"),
                    canvas_scale=settings.get("canvas_scale", 2.0),
                    detail_transfer_radius=settings.get("detail_transfer_radius", 3),
                    edge_blend_radius=settings.get("edge_blend_radius", 5),
                    output_format=settings.get("output_format", "jpeg"),
                    jpeg_quality=settings.get("jpeg_quality", 85),
                )
                self._result = result
            except Exception as e:
                self._result = {"error": str(e)}
            finally:
                self._stitching = False

        threading.Thread(target=worker, daemon=True).start()
        return {"status": "started"}

    def get_progress(self):
        """Poll current progress. Returns {step, fraction, done, result}."""
        resp = {
            "step": self._progress["step"],
            "fraction": self._progress["fraction"],
            "done": not self._stitching and self._result is not None,
        }
        if resp["done"]:
            resp["result"] = self._result
        return resp

    def get_image_data(self, path):
        """Read an image file and return as base64 data URL."""
        if not os.path.exists(path):
            return ""
        ext = os.path.splitext(path)[1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        content_type = mime.get(ext.lstrip("."), "image/png")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{content_type};base64,{b64}"

    def get_file_size(self, path):
        """Return file size in MB."""
        if not os.path.exists(path):
            return 0
        return round(os.path.getsize(path) / 1024 / 1024, 1)

    def save_result(self, src_path):
        """Open native save dialog, copy result file to chosen location."""
        basename = os.path.basename(src_path)
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=basename,
        )
        if result:
            dest = result if isinstance(result, str) else result[0]
            shutil.copy2(src_path, dest)
            return {"saved": dest}
        return {"cancelled": True}
