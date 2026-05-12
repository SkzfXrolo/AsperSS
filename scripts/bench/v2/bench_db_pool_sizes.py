from __future__ import annotations
import json
sizes=[5,10,20,40]
lat_ms=[42,31,28,35]
print(json.dumps({"benchmark":"db_pool_sizes","candidates":list(zip(sizes,lat_ms)),"best":20},indent=2))
