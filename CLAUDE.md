# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**whiteboard-stitch** combines multiple whiteboard/document photographs into a single composite image using computer vision. It aligns overlapping close-up photos against an establishing shot via homography, then blends them seamlessly.

Project page: http://joshuahhh.com/projects/whiteboard-stitch

## Commands

### Desktop app (primary UI)
```
uv run python main.py
```

### CLI stitching pipeline
```
uv run python stitch-cli.py whiteboards/concurrency/a.yaml
```

### Generate image pyramids for the legacy viewer
```
uv run python bundle.py whiteboards viewer/static/data
```

## Python Dependencies

Managed by `uv` (see `pyproject.toml`). Install with `uv sync`.

Key packages: opencv-python, numpy, pyclipper, imutils, pyyaml, pillow, pillow-heif, pywebview.

## Architecture

### Processing Pipeline

Images in (HEIC/JPEG/PNG) &rarr; SIFT feature detection &rarr; homography matching &rarr; Voronoi/stacked mask generation &rarr; detail transfer stitching &rarr; output (JPEG/PNG/WebP)

### Entry Points

- **main.py** &mdash; Desktop app entry point (pywebview native window)
- **api.py** &mdash; Python API class exposed to JS via pywebview bridge (file dialogs, thumbnails, stitch, progress, save)
- **pipeline.py** &mdash; Callable pipeline API with progress callback (`run_stitch()`); used by the desktop app
- **frontend/** &mdash; HTML/CSS/JS single-page app (index.html, style.css, app.js); communicates with Python via `pywebview.api.*`
- **stitch-cli.py** &mdash; Original CLI entry point; reads YAML config

### Key Python Modules

- **stitching.py** &mdash; Core `StitchingJob` class: mask generation (Voronoi or stacked), detail transfer blending
- **spimage.py** &mdash; Coordinate space abstraction layer (`ImageSpace`, `CoordSystem`, `Image`, `ImagePoint`, `ImageFunction`); supports HEIC via pillow-heif
- **sphomography.py** &mdash; SIFT feature detection/matching and RANSAC-based homography computation
- **spvoronoi.py** &mdash; Voronoi diagram generation for region partitioning (uses pyclipper)
- **library.py** &mdash; Pickle-based caching system with lazy thunk pattern; caches feature detection and tile generation
- **bundle.py** &mdash; Converts output PNGs to Deep Zoom tile pyramids (for legacy viewer)
- **deepzoom.py** &mdash; Deep Zoom tile generation (128x128 tiles, 2px overlap, bicubic resampling)

### Coordinate Space System (spimage.py)

Central design pattern: images and points carry explicit coordinate system metadata. `CoordSystem` maps between named `ImageSpace`s via affine transforms. `ImageFunction` (e.g., a Homography) transforms between spaces. This decouples image operations from coordinate bookkeeping.

### Config Format (YAML, for CLI only)

Each whiteboard has a YAML config specifying the establishing shot, close-up glob pattern, feature detection parameters (downsample scale), partition method (voronoi/stacked), and stitching parameters (canvas scale, detail transfer radius, edge blend radius).

### Legacy Web Viewer (viewer/)

React 0.14 app using OpenSeadragon for deep zoom rendering. Built with Webpack 1.9 + Babel. Largely superseded by the Streamlit app.
