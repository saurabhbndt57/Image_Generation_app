# app.py  — paste this whole file

import re
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# =========================
# CONFIG
# =========================
N8N_WEBHOOK_URL = "https://reinventdigital12.app.n8n.cloud/webhook/1f5a9c05-cc1e-4d19-b6f5-f42b22e10efe"

st.set_page_config(page_title="RD's Image Generation", page_icon="🖼️", layout="wide")

# =========================
# UI: Header
# =========================
st.markdown(
    "<h1 style='text-align:center; color:#1E88E5;'>RD's Image Generation</h1>",
    unsafe_allow_html=True,
)
st.caption(
    "Paste a **Google Slides** link. The n8n workflow will read the deck, "
    "generate images, save them to Google Drive, and we'll display the results here."
)

# =========================
# Helpers
# =========================
def _best_img_url(file_obj: Dict[str, Any]) -> Optional[str]:
    """
    Pick the most displayable URL from a Google Drive file object.
    Prefer webContentLink (direct), else thumbnailLink, else webViewLink.
    """
    return (
        file_obj.get("webContentLink")
        or file_obj.get("thumbnailLink")
        or file_obj.get("webViewLink")
    )


def _render_drive_array(file_objs: List[Dict[str, Any]]) -> None:
    """
    Render when n8n returns a raw list of Google Drive file objects.
    """
    if not file_objs:
        st.warning("Response list is empty.")
        return

    st.markdown("### 🖼️ Generated Images")
    cols = st.columns(5)
    shown = 0
    for i, obj in enumerate(file_objs):
        url = _best_img_url(obj)
        if not url:
            continue
        with cols[shown % 5]:
            try:
                st.image(url, caption=obj.get("name", f"Image {i+1}"), use_container_width=True)
            except Exception:
                st.warning("Couldn’t render image; link below may require Drive permission.")
                st.markdown(f"[Open image]({url})")
        shown += 1

    if shown == 0:
        st.warning("No displayable image URLs found. "
                   "Ensure Drive sharing is set to “Anyone with the link: Viewer”."
                   )


def _render_slides_map(slides_map: Dict[str, List[str]]) -> None:
    """
    Render when n8n returns a tidy slides map:
    { "slides": { "Slide 1": [url1, url2, ...], ... } }
    """
    st.markdown("### 🖼️ Generated Images")
    for slide_title, urls in slides_map.items():
        st.subheader(f"📑 {slide_title}")
        cols = st.columns(5)
        for i, img_url in enumerate(urls):
            with cols[i % 5]:
                try:
                    st.image(img_url, caption=f"Image {i+1}", use_container_width=True)
                except Exception:
                    st.warning(f"Couldn’t render Image {i+1}; opening as link.")
                    st.markdown(f"[Open image]({img_url})")


def looks_like_slides_url(u: str) -> bool:
    """
    Quick client-side sanity check for a Google Slides URL.
    Accepts:
      - https://docs.google.com/presentation/d/<id>/edit
      - any URL that contains ?id=<id> or ?presentationId=<id>
    """
    return bool(
        re.search(r"docs\.google\.com/presentation/", u) and
        (re.search(r"/presentation/d/[a-zA-Z0-9_-]+", u) or
         re.search(r"[?&](id|presentationId)=[a-zA-Z0-9_-]+", u))
    )

# =========================
# UI: URL input + action
# =========================
slides_url = st.text_input(
    "📎 Google Slides URL",
    placeholder="https://docs.google.com/presentation/d/XXXXXXXXXXXXXXXXXXXXXXXXXXXX/edit",
).strip()

if st.button("🚀 Generate Images"):
    st.info("⏳ Sending link to the n8n workflow. Please wait...")

    if not slides_url:
        st.error("Please paste a Google Slides link first.")
        st.stop()

    if not looks_like_slides_url(slides_url):
        st.warning("This doesn't look like a Google Slides link. I'll still try, but double-check the URL.")

    try:
        # Send JSON (important: NOT multipart/form-data)
        payload = {"presentationUrl": slides_url}
        resp = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=1800)

        if resp.status_code != 200:
            st.error(f"❌ n8n responded with HTTP {resp.status_code}")
            st.text(resp.text)
            st.stop()

        # n8n may return one of:
        #  A) { "slides": { "Slide 1": [urls...] , ... } }
        #  B) [ { drive file object }, ... ]
        #  C) { ...single drive file object... }
        try:
            data = resp.json()
        except Exception:
            st.error("Response was not JSON. Raw text below:")
            st.text(resp.text)
            st.stop()

        st.success("✅ Workflow executed successfully!")

        if isinstance(data, dict) and "slides" in data and isinstance(data["slides"], dict):
            _render_slides_map(data["slides"])

        elif isinstance(data, list):
            _render_drive_array(data)

        elif isinstance(data, dict) and data.get("kind") == "drive#file":
            _render_drive_array([data])

        else:
            st.warning("Response format not recognized. Showing raw JSON for debugging:")
            st.json(data)

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to connect to n8n: {e}")
