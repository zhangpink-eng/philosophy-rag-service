"""
Load Testing Script for Philosophia RAG Service
端到端压测脚本
"""

import asyncio
import aiohttp
import time
import random
from typing import List, Dict
import json


class LoadTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_duration": 0,
            "response_times": [],
            "errors": []
        }

    async def health_check(self, session: aiohttp.ClientSession) -> bool:
        """Check if service is healthy"""
        try:
            async with session.get(f"{self.base_url}/") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def test_rag_query(self, session: aiohttp.ClientSession) -> float:
        """Test RAG query endpoint"""
        start = time.time()
        try:
            payload = {
                "query": random.choice([
                    "什么是哲学咨询？",
                    "如何面对人生的困境？",
                    "自由与责任的关系是什么？",
                    "如何理解死亡？",
                    "生命的意义是什么？"
                ]),
                "top_k": 5
            }
            async with session.post(
                f"{self.base_url}/api/rag/query",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                self.results["total_requests"] += 1
                if resp.status == 200:
                    self.results["successful_requests"] += 1
                    await resp.json()
                else:
                    self.results["failed_requests"] += 1
                    error_text = await resp.text()
                    self.results["errors"].append(f"Status {resp.status}: {error_text[:100]}")
                return time.time() - start
        except asyncio.TimeoutError:
            self.results["total_requests"] += 1
            self.results["failed_requests"] += 1
            self.results["errors"].append("Request timeout")
            return time.time() - start
        except Exception as e:
            self.results["total_requests"] += 1
            self.results["failed_requests"] += 1
            self.results["errors"].append(str(e)[:100])
            return time.time() - start

    async def test_voice_tts(self, session: aiohttp.ClientSession) -> float:
        """Test TTS endpoint"""
        start = time.time()
        try:
            payload = {
                "text": "你好，我是Oscar，一个哲学咨询师。有什么可以帮助你的吗？"
            }
            async with session.post(
                f"{self.base_url}/api/voice/tts",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                self.results["total_requests"] += 1
                if resp.status == 200:
                    self.results["successful_requests"] += 1
                    # Read response to ensure it's complete
                    await resp.read()
                else:
                    self.results["failed_requests"] += 1
                return time.time() - start
        except Exception as e:
            self.results["total_requests"] += 1
            self.results["failed_requests"] += 1
            self.results["errors"].append(str(e)[:100])
            return time.time() - start

    async def test_safety_check(self, session: aiohttp.ClientSession) -> float:
        """Test safety check endpoint"""
        start = time.time()
        try:
            payload = {
                "content": random.choice([
                    "我想谈谈工作压力",
                    "最近感到有些迷茫",
                    "人生有什么意义？",
                    "我该怎么办？"
                ])
            }
            async with session.post(
                f"{self.base_url}/api/safety/check",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                self.results["total_requests"] += 1
                if resp.status == 200:
                    self.results["successful_requests"] += 1
                    await resp.json()
                else:
                    self.results["failed_requests"] += 1
                return time.time() - start
        except Exception as e:
            self.results["total_requests"] += 1
            self.results["failed_requests"] += 1
            self.results["errors"].append(str(e)[:100])
            return time.time() - start

    async def run_concurrent_requests(
        self,
        endpoint: str,
        count: int,
        concurrency: int = 10
    ):
        """Run concurrent requests to an endpoint"""
        print(f"\n[TEST] Running {count} concurrent requests to {endpoint}...")

        async with aiohttp.ClientSession() as session:
            # Check health first
            if not await self.health_check(session):
                print("[ERROR] Service is not available!")
                return

            semaphore = asyncio.Semaphore(concurrency)

            async def bounded_request():
                async with semaphore:
                    if endpoint == "rag":
                        return await self.test_rag_query(session)
                    elif endpoint == "tts":
                        return await self.test_voice_tts(session)
                    elif endpoint == "safety":
                        return await self.test_safety_check(session)

            start_time = time.time()
            tasks = [bounded_request() for _ in range(count)]
            response_times = await asyncio.gather(*tasks)
            duration = time.time() - start_time

            self.results["total_duration"] += duration
            self.results["response_times"].extend(response_times)

            print(f"[RESULT] Completed in {duration:.2f}s")
            print(f"[RESULT] Requests/sec: {count/duration:.2f}")

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("LOAD TEST SUMMARY")
        print("="*60)

        total = self.results["total_requests"]
        success = self.results["successful_requests"]
        failed = self.results["failed_requests"]

        print(f"Total Requests:    {total}")
        print(f"Successful:        {success} ({success/total*100:.1f}%)" if total > 0 else "Successful:        0")
        print(f"Failed:            {failed} ({failed/total*100:.1f}%)" if total > 0 else "Failed:            0")

        if self.results["response_times"]:
            times = sorted(self.results["response_times"])
            avg_time = sum(times) / len(times)
            p50 = times[int(len(times) * 0.5)]
            p95 = times[int(len(times) * 0.95)]
            p99 = times[int(len(times) * 0.99)]

            print(f"\nResponse Times:")
            print(f"  Average: {avg_time*1000:.0f}ms")
            print(f"  P50:     {p50*1000:.0f}ms")
            print(f"  P95:     {p95*1000:.0f}ms")
            print(f"  P99:     {p99*1000:.0f}ms")

        if self.results["errors"]:
            print(f"\nErrors ({len(self.results['errors'])}):")
            for err in self.results["errors"][:10]:
                print(f"  - {err}")
            if len(self.results["errors"]) > 10:
                print(f"  ... and {len(self.results['errors']) - 10} more")

        print("="*60)


async def run_load_test():
    """Run full load test suite"""
    tester = LoadTester()

    print("Starting Philosophia RAG Service Load Test")
    print("="*60)

    # Test scenarios
    scenarios = [
        ("rag", 50, 10),      # 50 RAG queries, 10 concurrent
        ("tts", 30, 5),       # 30 TTS requests, 5 concurrent
        ("safety", 100, 20),  # 100 safety checks, 20 concurrent
    ]

    for endpoint, count, concurrency in scenarios:
        await tester.run_concurrent_requests(endpoint, count, concurrency)

    tester.print_summary()


async def run_websocket_test():
    """Test WebSocket connection"""
    print("\n[TEST] WebSocket Connection Test")
    print("-"*40)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                "http://localhost:8000/api/voice/ws/test_session"
            ) as ws:
                print("[OK] WebSocket connected")

                # Send a text message
                await ws.send_json({
                    "type": "text",
                    "text": "你好"
                })
                print("[OK] Sent text message")

                # Wait for response
                msg = await ws.receive_json()
                print(f"[OK] Received: {msg.get('type')}")

                await ws.close()
                print("[OK] WebSocket closed")
    except Exception as e:
        print(f"[ERROR] WebSocket test failed: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--websocket":
        asyncio.run(run_websocket_test())
    else:
        asyncio.run(run_load_test())
