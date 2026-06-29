import logging


def configure_logging(log_level="INFO"):
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s %(name)s %(levelname)s - %(message)s",
    )
