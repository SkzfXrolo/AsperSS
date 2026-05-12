from __future__ import annotations
import gzip,json
data=(b"argus-bench-"*20000)
out={"raw":len(data),"gzip":len(gzip.compress(data))}
out["ratio_gzip"]=round(out["raw"]/out["gzip"],2)
print(json.dumps({"benchmark":"compression_ratios","result":out},indent=2))
