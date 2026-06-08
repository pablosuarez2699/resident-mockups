import logging
import sys
import uuid

run_id = str(uuid.uuid4())[:8]

logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [{run_id}] %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
