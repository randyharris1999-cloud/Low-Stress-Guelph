"""Assemble index.html from scripts/index.src.html (run from the repo folder: python scripts/build_html.py)."""
import os
here = os.path.dirname(os.path.abspath(__file__))
css = open(os.path.join(here, "leaflet.min.css"), encoding="utf-8").read()
src = open(os.path.join(here, "index.src.html"), encoding="utf-8").read().replace("/*LEAFLET_CSS*/", css)
open(os.path.join(os.path.dirname(here), "index.html"), "w", encoding="utf-8").write(src)
print("index.html", len(src), "bytes")
