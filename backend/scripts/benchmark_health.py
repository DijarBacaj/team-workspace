import argparse
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def request_once(url: str) -> float:
    started_at = time.perf_counter()
    with urllib.request.urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected status code: {response.status}")
        response.read()
    return (time.perf_counter() - started_at) * 1000


def percentile(values: list[float], percentage: float) -> float:
    position = max(0, round((len(values) - 1) * percentage))
    return sorted(values)[position]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the API health endpoint.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=20)
    arguments = parser.parse_args()
    if arguments.requests < 1 or arguments.concurrency < 1:
        parser.error("requests and concurrency must be positive")

    started_at = time.perf_counter()
    with ThreadPoolExecutor(max_workers=arguments.concurrency) as executor:
        latencies = list(
            executor.map(
                request_once,
                [arguments.url] * arguments.requests,
            )
        )
    duration = time.perf_counter() - started_at

    print(f"Requests: {arguments.requests}")
    print(f"Concurrency: {arguments.concurrency}")
    print(f"Throughput: {arguments.requests / duration:.2f} requests/second")
    print(f"Mean latency: {statistics.mean(latencies):.2f} ms")
    print(f"p50 latency: {percentile(latencies, 0.50):.2f} ms")
    print(f"p95 latency: {percentile(latencies, 0.95):.2f} ms")
    print(f"p99 latency: {percentile(latencies, 0.99):.2f} ms")


if __name__ == "__main__":
    main()
