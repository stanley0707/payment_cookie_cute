import logging

import structlog

logging.basicConfig(format="%(message)s", level=logging.INFO, handlers=[logging.StreamHandler()])

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.PATHNAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        structlog.dev.ConsoleRenderer(
            pad_event=30,
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        ),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str):
    return structlog.get_logger(name=name)
