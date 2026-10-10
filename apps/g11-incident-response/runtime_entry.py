from __future__ import annotations

import os,threading,time
from http.server import ThreadingHTTPServer

import psycopg

from http_app import make_handler
from pg_port import PgIncidentResponseGateway
from worker import IncidentResponseWorker,FixtureNeutralTicketAdapter

DB_URL=os.environ["G11_DATABASE_URL"]
HOST=os.environ.get("G11_HOST","0.0.0.0")
PORT=int(os.environ.get("G11_PORT","8011"))
EXECUTOR_ID=os.environ.get("G11_EXECUTOR_ID","g11-default")
TENANT_IDS=[t.strip() for t in os.environ.get("G11_TENANT_IDS","").split(",") if t.strip()]
POLL_INTERVAL=int(os.environ.get("G11_POLL_INTERVAL_SECONDS","5"))


def _run_worker(conn,tenant_ids:list[str])->None:
    port=PgIncidentResponseGateway(conn)
    ticket_adapter=FixtureNeutralTicketAdapter()
    worker=IncidentResponseWorker(port=port,ticket_adapter=ticket_adapter,notify_adapter=None,executor_id=EXECUTOR_ID)
    while True:
        for tenant_id in tenant_ids:
            try:
                result=worker.process_next(tenant_id)
                if result.get("state")!="idle":
                    print(f"[g11-worker] tenant={tenant_id} result={result}")
            except Exception as exc:
                print(f"[g11-worker] tenant={tenant_id} error={exc}")
        time.sleep(POLL_INTERVAL)


if __name__=="__main__":
    conn=psycopg.connect(DB_URL)
    port_gateway=PgIncidentResponseGateway(conn)

    if TENANT_IDS:
        t=threading.Thread(target=_run_worker,args=(conn,TENANT_IDS),daemon=True)
        t.start()

    handler=make_handler(port_gateway)
    server=ThreadingHTTPServer((HOST,PORT),handler)
    print(f"[g11] listening on {HOST}:{PORT}")
    server.serve_forever()
