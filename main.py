import multiprocessing
multiprocessing.freeze_support()

import os
import webview
from api import Api


def main():
    api = Api()
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    window = webview.create_window(
        "Whiteboard Stitch",
        os.path.join(frontend_dir, "index.html"),
        js_api=api,
        width=1100,
        height=800,
        min_size=(800, 600),
    )
    api._window = window
    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
