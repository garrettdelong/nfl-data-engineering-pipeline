LOG_LEVEL_CHOICES = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
]


def parse_truthy(value):
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def add_run_id_argument(parser, required=False):
    parser.add_argument(
        "--run-id",
        required=required,
        help="Pipeline run identifier used for audit metadata",
    )


def add_environment_name_argument(parser):
    parser.add_argument(
        "--environment-name",
        help="Pipeline environment name for audit metadata",
    )


def add_log_level_argument(parser):
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVEL_CHOICES,
        default="INFO",
        help="Python logging level",
    )


def add_manifest_output_argument(parser):
    parser.add_argument(
        "--manifest-output-path",
        type=str,
        help="Path where ingestion manifest JSON should be written",
    )


def add_manifest_input_argument(parser):
    parser.add_argument(
        "--manifest-path",
        required=True,
        help="Path to ingestion manifest JSON created by data.ingest_s3",
    )
