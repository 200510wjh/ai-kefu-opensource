from __future__ import annotations

import time

from .workflow import run_full_pack


def run_full_pack_task(tenant_id: str, actor_id: str, product_id: str) -> str:
    """Celery/RQ target placeholder.

    Production deployment should bind this function to Celery using Redis as the
    broker. Keeping orchestration here prevents automation logic from leaking
    into API routes.
    """

    result = run_full_pack(tenant_id, actor_id, product_id)
    return result.workflow_id


if __name__ == "__main__":
    print("Material Factory worker placeholder started. Bind Celery/RQ here for production.")
    while True:
        time.sleep(60)
