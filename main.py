# main.py
import os
from config import DEFAULT_CHUNK_SIZE, MIN_CHUNK_SIZE
from utils import (
    split_pdf_to_chunks,
    post_extract,
    save_text,
    save_json,
    ensure_dir,
    _should_shrink,
)

INPUT_PDF = "samples/annual_report.pdf"  
DOC_STEM = os.path.splitext(os.path.basename(INPUT_PDF))[0]

OUT_MD_DIR = "output/markdown"
OUT_BOX_DIR = "output/boxes"
OUT_TAB_DIR = "output/tables"
OUT_HIER_DIR = "output/hierarchy"


def extract_mode_adaptive(
    input_pdf: str, mode: str, out_dir: str, merge_markdown=False
):
    """Run extraction with adaptive chunk size: shrink if the API complains."""
    print(f"\n=== Extracting {mode} ===")
    ensure_dir(out_dir)

    chunk_size = DEFAULT_CHUNK_SIZE
    merged_md = []
    start_page = 1

    # We’ll manually stride through pages so we can retry the *same range* smaller on failure
    # without resplitting the whole PDF.
    import io
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)

    while start_page <= total_pages:
        end_page = min(start_page + chunk_size - 1, total_pages)
        # Build this chunk
        writer = PdfWriter()
        for p in range(start_page - 1, end_page):
            try:
                writer.add_page(reader.pages[p])
            except Exception as e:
                print(f"⚠️ Skipping problematic page {p+1}: {e}")
                from pypdf import PageObject

                blank = PageObject.create_blank_page(width=612, height=792)
                writer.add_page(blank)
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()
        tag = f"p{start_page}-{end_page}"
        print(
            f"  -> chunk [{tag}] (pages {start_page}-{end_page}, size {len(pdf_bytes)/1024/1024:.2f} MB)"
        )

        try:
            res = post_extract(pdf_bytes, output_type=mode)
        except Exception as e:
            # If server likely wants smaller chunks, shrink and retry same range
            msg = str(e)
            code = None
            # try to parse an HTTP code from the message
            for c in ("408", "413", "429", "500", "502", "503", "504"):
                if c in msg:
                    code = int(c)
                    break
            if (
                code is not None or _should_shrink(code or 0, msg)
            ) and chunk_size > MIN_CHUNK_SIZE:
                new_size = max(MIN_CHUNK_SIZE, chunk_size // 2)
                print(
                    f"🔁 Shrinking chunk size {chunk_size} → {new_size} and retrying same range."
                )
                chunk_size = new_size
                continue
            else:
                print(f"❌ Irrecoverable error on [{tag}]: {e}")
                # Save a small error marker for audit
                err_path = os.path.join(out_dir, f"{DOC_STEM}_{tag}.error.txt")
                save_text(f"{e}", err_path)
                # Skip this range to progress
                start_page = end_page + 1
                continue

        # Save successful chunk
        chunk_out = os.path.join(
            out_dir,
            f"{DOC_STEM}_{tag}.json" if mode != "markdown" else f"{DOC_STEM}_{tag}.md",
        )
        if mode == "markdown":
            md = res.get("content", "")
            save_text(md, chunk_out)
            if merge_markdown:
                merged_md.append(md.rstrip() + "\n\n<!-- PAGE-CHUNK BREAK -->\n\n")
        else:
            save_json(res, chunk_out)

        # Advance to next range; keep current (possibly reduced) chunk_size
        start_page = end_page + 1

    # Merge markdown if requested
    if merge_markdown and merged_md:
        final_md = "".join(merged_md)
        final_path = os.path.join(out_dir, f"{DOC_STEM}.md")
        save_text(final_md, final_path)
        print(f"✅ Merged markdown saved: {final_path}")


def main():
    # 1) Markdown (merge)
    extract_mode_adaptive(
        INPUT_PDF, mode="markdown", out_dir=OUT_MD_DIR, merge_markdown=True
    )
    # 2) Boxes
    extract_mode_adaptive(
        INPUT_PDF, mode="ocr-with-bounding-boxes", out_dir=OUT_BOX_DIR
    )
    # 3) Tables
    extract_mode_adaptive(INPUT_PDF, mode="tables", out_dir=OUT_TAB_DIR)
    # 4) Hierarchy
    extract_mode_adaptive(INPUT_PDF, mode="hierarchy_output", out_dir=OUT_HIER_DIR)
    print(
        "\n🎉 All modes attempted. Check *.error.txt files (if any) for failing ranges."
    )


if __name__ == "__main__":
    main()
