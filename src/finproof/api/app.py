"""FastAPI composition for the organizer evaluation contract."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from finproof.api.dependencies import ApiDependencies
from finproof.api.errors import safe_failure
from finproof.api.routes.answer import router as answer_router
from finproof.core.settings import Settings


def create_app(
    settings: Settings | None = None, *, dependencies: ApiDependencies | None = None
) -> FastAPI:
    """Create the exact, route-minimal organizer application."""
    runtime_settings = settings or Settings()
    runtime_dependencies = dependencies or ApiDependencies()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with runtime_dependencies.open_session(runtime_settings) as session:
            app.state.answer_orchestrator = runtime_dependencies.create_orchestrator(session)
            yield

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.router.redirect_slashes = False
    app.include_router(answer_router)

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
    async def unexpected_error(request: Request, _: Exception) -> JSONResponse:
        response = safe_failure(
            question_id=request.query_params.get("question_id", ""),
            question=request.query_params.get("question", ""),
        )
        return JSONResponse(status_code=500, content=response.model_dump(mode="json"))

    return app
