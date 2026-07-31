import logging
from time import perf_counter

from app.core.observability import elapsed_ms, log_event
from app.llm.provider import LLMProvider


def generate_with_observability(
    provider: LLMProvider,
    logger: logging.Logger,
    operation: str,
    *,
    system_prompt: str,
    user_prompt: str,
    session_id: object | None = None,
) -> str:
    provider_name = type(provider).__name__
    model_id = _model_id(provider)
    started_at = perf_counter()
    log_event(
        logger,
        logging.DEBUG,
        "llm_request_started",
        operation=operation,
        session_id=session_id,
        provider=provider_name,
        model_id=model_id,
    )

    try:
        response = provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except Exception:
        log_event(
            logger,
            logging.ERROR,
            "llm_request_failed",
            operation=operation,
            session_id=session_id,
            provider=provider_name,
            model_id=model_id,
            duration_ms=elapsed_ms(started_at),
            outcome="failure",
        )
        raise

    log_event(
        logger,
        logging.DEBUG,
        "llm_request_completed",
        operation=operation,
        session_id=session_id,
        provider=provider_name,
        model_id=model_id,
        duration_ms=elapsed_ms(started_at),
        outcome="success",
    )
    return response


def _model_id(provider: LLMProvider) -> str | None:
    model_id = getattr(provider, "model_id", None)
    return model_id if isinstance(model_id, str) else None
