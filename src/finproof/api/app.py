"""FastAPI composition for the organizer evaluation contract."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from finproof.api.dependencies import ApiDependencies
from finproof.api.routes.answer import router as answer_router
from finproof.core.logging import configure_runtime_logging
from finproof.core.settings import Settings
from finproof.service.limits import RequestDeadline

_LOGGER = logging.getLogger("finproof.api")


def create_app(
    settings: Settings | None = None, *, dependencies: ApiDependencies | None = None
) -> FastAPI:
    """Create the exact, route-minimal organizer application."""
    configure_runtime_logging()
    runtime_settings = settings or Settings()
    runtime_dependencies = dependencies or ApiDependencies()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with runtime_dependencies.open_session(runtime_settings) as session:
            async with runtime_dependencies.open_orchestrator(
                session, runtime_settings
            ) as orchestrator:
                app.state.answer_orchestrator = orchestrator
                yield

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.router.redirect_slashes = False
    app.include_router(answer_router)

    @app.middleware("http")
    async def issue_deadline(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.deadline = RequestDeadline.start(clock=runtime_dependencies.clock)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {key: item[key] for key in ("type", "loc", "msg") if key in item}
                    for item in error.errors()
                ]
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> Response:
        correlation_id = getattr(request.state, "correlation_id", None)
        if type(correlation_id) is not str:
            correlation_id = uuid4().hex
        _LOGGER.error(
            "unexpected evaluation failure",
            extra={
                "correlation_id": correlation_id,
                "exception_type": type(error).__name__,
            },
        )
        publication = getattr(request.state, "safe_publication", None)
        if publication is None:
            return JSONResponse(status_code=500, content={"detail": "evaluation failure"})
        return Response(
            status_code=500,
            content=publication.body,
            media_type="application/json",
        )

    return app
