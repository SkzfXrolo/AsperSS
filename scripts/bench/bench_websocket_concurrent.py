#!/usr/bin/env python3
import asyncio
import time


async def fake_ws_client(_id: int):
    await asyncio.sleep(0.001)
    return 1


async def run(n=1000):
    t0 = time.perf_counter()
    await asyncio.gather(*(fake_ws_client(i) for i in range(n)))
    ms = (time.perf_counter() - t0) * 1000
    print("clients,total_ms")
    print(f"{n},{ms:.3f}")


if __name__ == "__main__":
    asyncio.run(run())
