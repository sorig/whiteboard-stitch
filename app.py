import os
import tempfile
import streamlit as st
import pillow_heif
from PIL import Image as PILImage
from pipeline import run_stitch

pillow_heif.register_heif_opener()

st.set_page_config(page_title="Whiteboard Stitch", layout="wide")
st.title("Whiteboard Stitch")
st.caption("Combine multiple whiteboard photos into a single high-resolution image")

# --- File upload ---
uploaded_files = st.file_uploader(
    "Drop your photos here",
    type=["jpg", "jpeg", "png", "heic", "heif"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("Upload at least 2 photos: one wide-angle establishing shot and one or more close-up detail shots.")
    st.stop()

if len(uploaded_files) < 2:
    st.warning("Need at least 2 photos (1 establishing + 1 close-up).")
    st.stop()

# --- Write uploaded files to temp dir, converting HEIC to JPEG ---
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp(prefix="stitch_")

temp_dir = st.session_state.temp_dir
file_paths = {}
for f in uploaded_files:
    is_heic = f.name.lower().endswith((".heic", ".heif"))
    # Convert HEIC to JPEG so Streamlit and OpenCV can read them
    save_name = os.path.splitext(f.name)[0] + ".jpg" if is_heic else f.name
    path = os.path.join(temp_dir, save_name)
    if not os.path.exists(path):
        if is_heic:
            img = PILImage.open(f)
            img.save(path, "JPEG", quality=95)
        else:
            with open(path, "wb") as out:
                out.write(f.getbuffer())
    file_paths[f.name] = path

# --- Thumbnail grid & establishing shot selector ---
st.subheader("Click a photo to select it as the establishing (wide-angle) shot")

names = sorted(file_paths.keys())

if "establishing_name" not in st.session_state:
    st.session_state.establishing_name = names[0]

cols_per_row = min(len(names), 4)
for row_start in range(0, len(names), cols_per_row):
    cols = st.columns(cols_per_row)
    for col_idx, name in enumerate(names[row_start:row_start + cols_per_row]):
        is_selected = name == st.session_state.establishing_name
        with cols[col_idx]:
            if is_selected:
                st.markdown(
                    f":white_check_mark: **{name}**<br><small>Establishing shot</small>",
                    unsafe_allow_html=True,
                )
            st.image(file_paths[name], use_container_width=True)
            if is_selected:
                st.button("Selected", key=f"sel_{name}", disabled=True, use_container_width=True)
            else:
                if st.button("Use as establishing", key=f"sel_{name}", use_container_width=True):
                    st.session_state.establishing_name = name
                    st.rerun()

establishing_name = st.session_state.establishing_name
close_names = [n for n in names if n != establishing_name]
st.write(f"**Establishing shot:** {establishing_name}  |  **Close-ups:** {len(close_names)} photos")

# --- Settings sidebar ---
with st.sidebar:
    st.header("Settings")
    partition_method = st.selectbox("Partition method", ["stacked", "voronoi"], index=0)
    canvas_scale_auto = st.checkbox("Auto canvas scale", value=False)
    canvas_scale = None if canvas_scale_auto else st.slider("Canvas scale", 1.0, 4.0, 2.0, 0.5)
    detail_transfer_radius = st.slider("Detail transfer radius", 1, 10, 3)
    edge_blend_radius = st.slider("Edge blend radius", 1, 20, 5)
    output_format = st.selectbox("Output format", ["jpeg", "png", "webp"], index=0)
    jpeg_quality = st.slider("Output quality", 50, 100, 85) if output_format != "png" else 85

# --- Stitch button ---
if st.button("Stitch", type="primary", use_container_width=True):
    output_dir = os.path.join(temp_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    progress_bar = st.progress(0.0)
    status_text = st.empty()

    def on_progress(step_name, fraction):
        progress_bar.progress(fraction, text=step_name)
        status_text.text(step_name)

    try:
        result = run_stitch(
            establishing_path=file_paths[establishing_name],
            close_paths=[file_paths[n] for n in close_names],
            output_dir=output_dir,
            on_progress=on_progress,
            partition_method=partition_method,
            canvas_scale=canvas_scale,
            detail_transfer_radius=detail_transfer_radius,
            edge_blend_radius=edge_blend_radius,
            output_format=output_format,
            jpeg_quality=jpeg_quality,
        )
        st.session_state.result = result
    except Exception as e:
        st.error(f"Stitching failed: {e}")
        st.stop()

    progress_bar.progress(1.0, text="Done!")
    status_text.text("")

# --- Results ---
if "result" in st.session_state:
    result = st.session_state.result

    st.subheader("Result")
    st.image(result["stitched"], use_container_width=True)

    stitched_size = os.path.getsize(result["stitched"]) / 1024 / 1024
    st.caption(f"Output: {stitched_size:.1f} MB")

    with open(result["stitched"], "rb") as f:
        stitched_basename = os.path.basename(result["stitched"])
        st.download_button(
            f"Download {stitched_basename}",
            f,
            file_name=stitched_basename,
            use_container_width=True,
        )

    with st.expander("Diagnostic images"):
        col1, col2 = st.columns(2)
        with col1:
            st.caption("Homography boundaries")
            st.image(result["homographies"], use_container_width=True)
        with col2:
            st.caption("Mask regions")
            st.image(result["masks"], use_container_width=True)
