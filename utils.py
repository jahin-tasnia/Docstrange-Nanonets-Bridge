# utils.py
import io, json, time, requests
from urllib.parse import urlencode
from config import (
    URL,
    HEADERS,
    REQUEST_TIMEOUT,
    POLL_SLEEP_SEC,
    POLL_MAX_SECONDS,
    MAX_RETRIES,
    RETRY_SLEEP_BASE,
)


def _print_server_error(resp, output_type):
    print(f"❌ HTTP {resp.status_code} for {output_type}. Server said:")
    try:
        print(resp.text[:2000])
    except Exception:
        pass


def poll_until_ready(record_id: str):
    """
    Poll the GET endpoint until processing completes.
    Most Docstrange deployments support either:
      GET /extract?record_id=...         (query param)
    or sometimes:
      GET /extract/<record_id>           (path param)
    We try query first, then path.
    """
    deadline = time.time() + POLL_MAX_SECONDS
    last_err = None

    while time.time() < deadline:
        # Try query-param style
        try:
            q = {"record_id": str(record_id)}
            resp = requests.get(
                f"{URL}?{urlencode(q)}", headers=HEADERS, timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                data = resp.json()
                status = str(data.get("processing_status", "")).lower()
                pages = int(data.get("pages_processed", 0))
                # Heuristic: completed when status says done/complete or we see pages > 0 and content/tables present
                if (
                    status in {"completed", "done", "finished", "succeeded"}
                    or pages > 0
                    or data.get("content")
                    or data.get("tables")
                ):
                    return data
            else:
                last_err = resp
        except Exception as e:
            last_err = e

        # Fallback: path-param style (ignore if 404)
        try:
            resp2 = requests.get(
                f"{URL}/{record_id}", headers=HEADERS, timeout=REQUEST_TIMEOUT
            )
            if resp2.status_code == 200:
                data2 = resp2.json()
                status2 = str(data2.get("processing_status", "")).lower()
                pages2 = int(data2.get("pages_processed", 0))
                if (
                    status2 in {"completed", "done", "finished", "succeeded"}
                    or pages2 > 0
                    or data2.get("content")
                    or data2.get("tables")
                ):
                    return data2
        except Exception:
            pass

        time.sleep(POLL_SLEEP_SEC)

    # If we ran out of time, surface whatever we last got
    if isinstance(last_err, requests.Response):
        _print_server_error(last_err, f"poll record_id={record_id}")
        raise RuntimeError(
            f"Polling timed out for record_id={record_id} (HTTP {last_err.status_code})"
        )
    raise RuntimeError(f"Polling timed out for record_id={record_id}")


def post_extract(file_bytes: bytes, output_type: str):
    """Submit job, then poll until finished. Returns the FINAL result JSON."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            file_obj = io.BytesIO(file_bytes)  # fresh each attempt
            files = {"file": ("chunk.pdf", file_obj, "application/pdf")}
            data = {"output_type": output_type}

            resp = requests.post(
                URL, headers=HEADERS, files=files, data=data, timeout=REQUEST_TIMEOUT
            )

            if resp.status_code >= 400:
                _print_server_error(resp, output_type)
                resp.raise_for_status()

            # Response may be either final or a receipt
            try:
                data_out = resp.json()
            except ValueError:
                raise RuntimeError(
                    f"Response was not valid JSON. Snippet:\n{resp.text[:500]}"
                )

            status = str(data_out.get("processing_status", "")).lower()
            content = data_out.get("content")
            tables = data_out.get("tables")
            pages = int(data_out.get("pages_processed", 0))
            rid = data_out.get("record_id")

            # If already done (some outputs finish synchronously), return
            if (
                status in {"completed", "done", "finished", "succeeded"}
                or content
                or tables
                or pages > 0
            ):
                return data_out

            # Otherwise we must poll; require a record_id
            if not rid:
                raise RuntimeError(
                    f"Server returned no record_id; cannot poll. Body:\n{json.dumps(data_out)[:800]}"
                )

            return poll_until_ready(str(rid))

        except requests.RequestException as e:
            last_err = e
            print(f"⚠️ Attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
            time.sleep(RETRY_SLEEP_BASE * (attempt + 1))

    raise RuntimeError(f"Extraction failed after {MAX_RETRIES} attempts: {last_err}")
