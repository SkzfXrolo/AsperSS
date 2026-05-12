from __future__ import annotations

import logging
import logging.handlers


def export_syslog_cef(findings: list[dict], host="127.0.0.1", port=514):
    logger = logging.getLogger("argus_syslog")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(logging.handlers.SysLogHandler(address=(host, port)))
    sent = 0
    for f in findings:
        cef = f"CEF:0|Argus|Scanner|1.0|{f.get('tipo','finding')}|{f.get('nombre','')[:120]}|5|cs1={f.get('ruta','')}"
        logger.info(cef)
        sent += 1
    return {"sent": sent}

