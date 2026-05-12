from __future__ import annotations
import asyncio,json,time
async def work():
    await asyncio.sleep(0.001)
async def main():
    n=2000
    t0=time.perf_counter()
    await asyncio.gather(*[work() for _ in range(n)])
    dt=time.perf_counter()-t0
    print(json.dumps({"benchmark":"async_throughput","tasks":n,"throughput_tps":round(n/dt,2)},indent=2))
asyncio.run(main())
