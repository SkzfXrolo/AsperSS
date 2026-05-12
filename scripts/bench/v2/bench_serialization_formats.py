from __future__ import annotations
import json,time
obj={"id":1,"name":"argus","scores":[1,2,3],"ok":True}
N=200000
t0=time.perf_counter()
for _ in range(N): json.dumps(obj)
print(json.dumps({"benchmark":"serialization_formats","json_s":round(time.perf_counter()-t0,4),"note":"extend with msgpack/protobuf/cbor"},indent=2))
