import argparse
import json
import random
import string
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DetectResponse:
    detections: List[Dict[str, Any]]
    detection_count: int
    processing_time_ms: int


def _http_post_json(url: str, payload: Dict[str, Any], timeout_s: int = 60) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from {url}: {raw}") from e


def detect(base_url: str, text: str, source_type: str = "pii_test", timeout_s: int = 60) -> DetectResponse:
    url = base_url.rstrip("/") + "/api/v1/pii/detect"
    payload = {
        "text": text,
        "source_type": source_type,
    }
    data = _http_post_json(url, payload, timeout_s=timeout_s)
    return DetectResponse(
        detections=data.get("detections", []) or [],
        detection_count=int(data.get("detection_count", 0) or 0),
        processing_time_ms=int(data.get("processing_time_ms", 0) or 0),
    )


def redact(
    base_url: str,
    text: str,
    redaction_type: str = "tag",
    timeout_s: int = 60,
) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/api/v1/pii/redact"
    payload = {
        "text": text,
        "redaction_type": redaction_type,
        "mask_char": "*",
        "preserve_length": False,
    }
    return _http_post_json(url, payload, timeout_s=timeout_s)


def _contains_expected(detections: List[Dict[str, Any]], expected: str) -> bool:
    expected = expected.strip()
    for d in detections:
        entity_type = str(d.get("entity_type", ""))
        engine = str(d.get("engine", ""))
        if expected.lower() in entity_type.lower():
            return True
        if expected.lower() in engine.lower():
            return True
    return False


def run_functional_tests(base_url: str) -> int:
    print("=" * 60)
    print("RUNNING FUNCTIONAL PII/SECRET TESTS (API)")
    print("Base URL:", base_url)
    print("=" * 60)

    # NOTE: Using only Presidio built-in recognizers (no custom HIGH_ENTROPY_SECRET)
    # Passwords/secrets won't be detected - only standard PII like email, SSN, credit card
    test_cases = [
        ("Standard Email", "Please contact me at john.doe@example.com for details.", "EMAIL", True),
        ("Standard US SSN", "My SSN is 168-99-6765.", "SSN", True),
        ("Credit Card", "Card: 4111 1111 1111 1111", "CREDIT", True),
        ("Phone Number", "Call me at (555) 123-4567", "PHONE", True),
        ("Regular text", "This is a normal sentence with no PII.", "", False),
    ]

    passed = 0
    for name, text, expected, should_find in test_cases:
        r = detect(base_url, text, source_type="functional_test", timeout_s=60)

        ok = False
        if should_find:
            ok = r.detection_count > 0 and (expected == "" or _contains_expected(r.detections, expected))
        else:
            ok = r.detection_count == 0

        if ok:
            print(f"[PASS] {name} | detections={r.detection_count} | api_ms={r.processing_time_ms}")
            passed += 1
        else:
            print(f"[FAIL] {name} | detections={r.detection_count} | api_ms={r.processing_time_ms}")
            if r.detections:
                types = sorted({str(d.get('entity_type')) for d in r.detections})
                engines = sorted({str(d.get('engine')) for d in r.detections})
                print("  Detected entity_types:", types)
                print("  Detected engines:", engines)

    print(f"\nFunctional results: {passed}/{len(test_cases)} passed\n")
    return 0 if passed == len(test_cases) else 1


def _make_large_text(size_chars: int) -> str:
    # Build mostly-random text with a few known tokens to detect.
    # Keep it deterministic-ish across runs.
    rnd = random.Random(1337)
    chunks: List[str] = []
    chunk_size = 512
    for _ in range(max(1, size_chars // chunk_size)):
        chunks.append("".join(rnd.choices(string.ascii_letters + string.digits + " ", k=chunk_size)))

    # Inject a few detectables.
    if chunks:
        mid = len(chunks) // 2
        chunks[mid] = chunks[mid] + " john.doe@example.com "
        chunks[mid] = chunks[mid] + " Card: 4111 1111 1111 1111 "
        chunks[mid] = chunks[mid] + " PassZini@2025 "

    text = "".join(chunks)
    if len(text) < size_chars:
        text += "a" * (size_chars - len(text))
    return text[:size_chars]


def run_performance_test(base_url: str, sizes: List[int], repeats: int, timeout_s: int) -> None:
    print("=" * 60)
    print("RUNNING PERFORMANCE TEST (API)")
    print(f"repeats={repeats} timeout_s={timeout_s}")
    print("=" * 60)

    for size in sizes:
        text = _make_large_text(size)
        wall_times: List[float] = []
        api_times_ms: List[int] = []
        det_counts: List[int] = []

        for i in range(repeats):
            t0 = time.perf_counter()
            r = detect(base_url, text, source_type=f"perf_{size}", timeout_s=timeout_s)
            t1 = time.perf_counter()
            wall = t1 - t0
            wall_times.append(wall)
            api_times_ms.append(r.processing_time_ms)
            det_counts.append(r.detection_count)
            print(f"size={size} run={i+1}/{repeats} wall_s={wall:.3f} api_ms={r.processing_time_ms} detections={r.detection_count}")

        avg_wall = sum(wall_times) / len(wall_times)
        avg_api_ms = int(sum(api_times_ms) / len(api_times_ms)) if api_times_ms else 0
        kb = size / 1024.0
        kbps = kb / avg_wall if avg_wall > 0 else 0.0
        print(f"\nSUMMARY size={size} chars ({kb:.1f} KB): avg_wall_s={avg_wall:.3f} avg_api_ms={avg_api_ms} throughput={kbps:.1f} KB/s avg_detections={sum(det_counts)/len(det_counts):.1f}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="PII/Secret functional + performance test harness (calls the running API).")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Base URL of the running remediation-engine")
    parser.add_argument("--sizes", default="1000,10000,100000", help="Comma-separated payload sizes in characters")
    parser.add_argument("--repeats", type=int, default=3, help="Repeats per payload size")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout seconds")
    parser.add_argument("--skip-functional", action="store_true")
    parser.add_argument("--skip-perf", action="store_true")
    args = parser.parse_args()

    sizes = [int(s.strip()) for s in args.sizes.split(",") if s.strip()]

    rc = 0
    if not args.skip_functional:
        rc = run_functional_tests(args.base_url)

    if not args.skip_perf:
        run_performance_test(args.base_url, sizes=sizes, repeats=args.repeats, timeout_s=args.timeout)

    # Quick redaction demo
    demo = "Email john.doe@example.com and password PassZini@2025 should be redacted"
    redacted = redact(args.base_url, demo, redaction_type="tag", timeout_s=args.timeout)
    print("=" * 60)
    print("REDACTION DEMO")
    print("=" * 60)
    print("Original:", demo)
    print("Redacted:", redacted.get("redacted_text"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
