# diagnostics.py
import os, sys
from pypdf import PdfReader


def human(n):  # bytes -> human-readable
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f} {u}"
        n /= 1024
    return f"{n:.2f} PB"


def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnostics.py <path-to-pdf>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        sys.exit(1)

    size = os.path.getsize(path)
    print(f"📄 File: {path}")
    print(f"   Size: {human(size)}")

    try:
        reader = PdfReader(path)
    except Exception as e:
        print(f"❌ PdfReader failed to open: {e}")
        sys.exit(1)

    if getattr(reader, "is_encrypted", False):
        try:
            ok = reader.decrypt("")  # try empty password
            print(f"🔐 Encrypted: YES (decrypt empty pwd ok={ok})")
        except Exception as e:
            print(f"🔐 Encrypted: YES (decrypt failed: {e})")
            sys.exit(1)
    else:
        print("🔓 Encrypted: NO")

    n = len(reader.pages)
    print(f"🧾 Pages: {n}")

    # sample 3 pages for mediabox sanity
    for idx in [0, n // 2, n - 1]:
        if idx < 0 or idx >= n:
            continue
        mb = reader.pages[idx].mediabox
        w, h = float(mb.width), float(mb.height)
        print(f"   - Page {idx+1}: size = {w:.1f} × {h:.1f} (points)")

    print("✅ Diagnostics complete. If size > 80–100 MB, chunking is essential.")


if __name__ == "__main__":
    main()
