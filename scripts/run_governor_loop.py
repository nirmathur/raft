from time import sleep

from loguru import logger
from prometheus_client import start_http_server

from agent.core.governor import run_one_cycle

if __name__ == "__main__":
    start_http_server(8002)
    logger.info("Prometheus metrics serving on :8002")
    while True:
        try:
            run_one_cycle()
        except Exception as e:
            logger.exception("governor cycle failed: {}", e)
        sleep(2)
