"""Re-download and verify the explicitly licensed teaching gallery.

The curated annotations live in data/gallery.json. No API key is required.
Only Met records with isPublicDomain=true are accepted; local files are resized
to at most 512 pixels on their longest side. Original API records stay in the
manifest under source_metadata for provenance.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import json
from pathlib import Path
import time
from urllib.parse import quote, urlencode, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
API = "https://collectionapi.metmuseum.org/public/collection/v1/objects/"
SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1.1/search"
POLICY = "https://www.metmuseum.org/hubs/open-access"
USER_AGENT = "LocalChineseRetrievalLearning/1.0 (educational CC0 gallery)"


def has_cjk(value: str) -> bool:
    """Detect lost Chinese text even when the JSON remains syntactically valid."""
    return isinstance(value, str) and any(0x4E00 <= ord(char) <= 0x9FFF for char in value)


def request_bytes(url: str) -> bytes:
    if urlparse(url).scheme != "https":
        raise ValueError("Only HTTPS sources are allowed")
    # A few official image paths contain spaces or commas; preserve URL syntax.
    url = quote(url, safe=":/?=&%")
    last_error = None
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=45) as response:
                return response.read()
        except Exception as error:
            last_error = error
            if isinstance(error, HTTPError) and error.code in {400, 403, 404, 410}:
                break
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def request_json(url: str) -> dict:
    return json.loads(request_bytes(url).decode("utf-8"))


def save_image(raw: bytes, target: Path) -> None:
    with Image.open(BytesIO(raw)) as source:
        picture = ImageOps.exif_transpose(source).convert("RGB")
        picture.thumbnail((512, 512), Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        picture.save(target, "JPEG", quality=90, optimize=True)
    with Image.open(target) as saved:
        saved.verify()


def download_item(item: dict, refresh: bool) -> str:
    target = (ROOT / item["file"]).resolve()
    image_root = (ROOT / "data/images").resolve()
    if image_root not in target.parents or target.suffix.lower() != ".jpg":
        raise ValueError(f"Invalid gallery path: {item['file']}")
    if target.exists() and not refresh:
        with Image.open(target) as image:
            image.verify()
        return f"Verified {item['id']}"
    stored = item.get("source_metadata", {})
    object_id = stored.get("objectID")
    if not isinstance(object_id, int) or stored.get("isPublicDomain") is not True:
        raise ValueError(f"Missing public-domain evidence for {item['id']}")
    current = request_json(API + str(object_id))
    if current.get("isPublicDomain") is not True or not current.get("primaryImageSmall"):
        raise ValueError(f"Source no longer exposes an Open Access image: {object_id}")
    save_image(request_bytes(current["primaryImageSmall"]), target)
    return f"Downloaded {item['id']}"


def discover(output: Path) -> None:
    """Optional provenance-first discovery; candidates still need visual review."""
    buckets = ["Vase", "Cup", "Chair", "Bird", "Boat", "Clock", "Flowers", "Cat"]
    records = []
    used = set()
    def candidate_metadata(oid):
        try:
            return request_json(API + str(oid))
        except RuntimeError:
            return None  # Search can contain retired object IDs.
    for bucket in buckets:
        params = urlencode({"hasImages": "true", "title": "true", "q": bucket, "limit": 60})
        found = request_json(SEARCH + "?" + params).get("objectIDs") or []
        accepted = []
        # Four concurrent read requests, with no mass crawl of the collection.
        for start in range(0, len(found), 4):
            with ThreadPoolExecutor(max_workers=4) as pool:
                metadata = list(pool.map(candidate_metadata, found[start:start + 4]))
            for record in metadata:
                if (record and record.get("isPublicDomain") is True and record.get("primaryImageSmall")
                        and record["objectID"] not in used):
                    used.add(record["objectID"])
                    accepted.append({"bucket": bucket, "metadata": record})
            if len(accepted) >= 8:
                break
        records.extend(accepted[:8])
        print(f"{bucket}: {len(accepted[:8])} public-domain image candidates", flush=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    def get_candidate(record):
        meta = record["metadata"]
        target = ROOT / f"data/images/met_{meta['objectID']}.jpg"
        if target.exists():
            with Image.open(target) as image:
                image.verify()
            return True
        try:
            save_image(request_bytes(meta["primaryImageSmall"]), target)
            return True
        except RuntimeError:
            print(f"Skipped unavailable image {meta['objectID']}", flush=True)
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        available = sum(pool.map(get_candidate, records))
    print(f"Saved {available} candidate images; visual review is required.", flush=True)


def validate() -> tuple[int, int]:
    manifest = json.loads((ROOT / "data/gallery.json").read_text(encoding="utf-8"))
    items = manifest["items"]
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate gallery IDs")
    files = [item["file"] for item in items]
    if len(files) != len(set(files)):
        raise ValueError("Duplicate gallery image paths")
    for item in items:
        if not all(item.get(key) for key in ("id", "title", "caption", "file", "source_url", "license", "tags")):
            raise ValueError("Missing gallery field")
        if not has_cjk(item["title"]) or not has_cjk(item["caption"]):
            raise ValueError(f"Chinese title or caption is missing for {item['id']}")
        if not isinstance(item["tags"], list) or not all(has_cjk(tag) for tag in item["tags"]):
            raise ValueError(f"Chinese tags are missing for {item['id']}")
        if item["license"] != "CC0-1.0" or item["source_metadata"].get("isPublicDomain") is not True:
            raise ValueError("Invalid license evidence")
        metadata = item["source_metadata"]
        if (item["source_url"] != metadata.get("objectURL") or
                urlparse(item["source_url"]).hostname not in {"www.metmuseum.org", "metmuseum.org"}):
            raise ValueError("Source URL does not match official provenance")
        path = (ROOT / item["file"]).resolve()
        if (ROOT / "data/images").resolve() not in path.parents:
            raise ValueError("Image is outside the gallery")
        with Image.open(path) as picture:
            picture.load()
            if max(picture.size) > 512:
                raise ValueError("Image exceeds the documented size")
    queries = json.loads((ROOT / "data/queries.json").read_text(encoding="utf-8"))["queries"]
    query_ids = [q["id"] for q in queries]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("Duplicate query IDs")
    for query in queries:
        if not has_cjk(query.get("text", "")):
            raise ValueError(f"Chinese query text is missing for {query['id']}")
        relevant = query["relevant_ids"]
        if not relevant or len(relevant) != len(set(relevant)) or set(relevant) - set(ids):
            raise ValueError(f"Invalid relevant IDs for {query['id']}")
        if query["category"] not in {"object", "attribute", "negative"}:
            raise ValueError("Unknown query category")
        if query["split"] not in {"validation", "test"}:
            raise ValueError("Unknown query split")
    return len(items), len(queries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-download existing images after checking source rights")
    parser.add_argument("--check", action="store_true", help="Validate local images and annotation references without network")
    parser.add_argument("--discover", metavar="OUTPUT_JSON", help="Discover candidates for a new curated version; requires manual review")
    args = parser.parse_args()
    if args.discover:
        discover(ROOT / args.discover)
        return
    if not args.check:
        manifest = json.loads((ROOT / "data/gallery.json").read_text(encoding="utf-8"))
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(download_item, item, args.refresh) for item in manifest["items"]]
            for future in as_completed(futures):
                print(future.result(), flush=True)
    count, queries = validate()
    print(f"Validated {count} images and {queries} queries.")


if __name__ == "__main__":
    main()
