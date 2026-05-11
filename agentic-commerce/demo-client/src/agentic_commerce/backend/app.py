from .core import create_app
from .router import DemoRouteError, router

app = create_app(routers=[router])


@app.exception_handler(DemoRouteError)
async def demo_route_error_handler(_request, exc: DemoRouteError):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.error.model_dump(),
    )
