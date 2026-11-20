from contextlib import asynccontextmanager
from time import perf_counter
import logging
import string
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# 1. Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("day17")


# 2. Validate incoming data
class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    batch_size: int = Field(default=3, ge=1, le=10)


# 3. Generator: clean and iterate through words
def iter_words(text):
    for word in text.lower().split():
        cleaned = word.strip(string.punctuation)

        if cleaned:
            yield cleaned


# 4. Generator: divide words into batches
def iter_batches(words, batch_size):
    batch = []

    for word in words:
        batch.append(word)

        if len(batch) == batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


# 5. Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.total_requests = 0
    app.state.error_requests = 0
    app.state.analyze_requests = 0

    app.state.cache_hits = 0
    app.state.cache_misses = 0
    app.state.cache = {}

    logger.info("Day 17 application starting")

    yield

    logger.info("Day 17 application shutting down")


app = FastAPI(lifespan=lifespan)


# 6. Middleware: request IDs, errors and tracking
DOC_PATHS = {"/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def track_requests(request: Request, call_next):

    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id

    path = request.url.path

    if path not in DOC_PATHS:
        request.app.state.total_requests += 1

    start_time = perf_counter()

    try:
        response = await call_next(request)

    except Exception:
        logger.exception(
            "request_id=%s path=%s unexpected error",
            request_id,
            path
        )

        response = JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id
            }
        )

    elapsed_ms = round(
        (perf_counter() - start_time) * 1000, 3
    )

    if path not in DOC_PATHS and response.status_code >= 400:
        request.app.state.error_requests += 1

    logger.info(
        "request_id=%s method=%s path=%s status_code=%s duration_ms=%s",
        request_id,
        request.method,
        path,
        response.status_code,
        elapsed_ms
    )

    response.headers["X-Request-ID"] = request_id

    return response


# 7. Analyse text using iteration and caching
@app.post("/analyze")
async def analyze(data: TextRequest, request: Request):

    words = list(iter_words(data.text))

    if not words:
        raise HTTPException(
            status_code=400,
            detail="Please provide text containing at least one word"
        )

    app.state.analyze_requests += 1

    cache_key = (tuple(words), data.batch_size)

    if cache_key in app.state.cache:
        app.state.cache_hits += 1

        result = app.state.cache[cache_key]

        return {
            **result,
            "cache_hit": True,
            "request_id": request.state.request_id
        }

    app.state.cache_misses += 1

    batches = list(iter_batches(words, data.batch_size))

    result = {
        "batches": batches,
        "total_words": len(words),
        "total_batches": len(batches)
    }

    app.state.cache[cache_key] = result

    return {
        **result,
        "cache_hit": False,
        "request_id": request.state.request_id
    }


# 8. Deliberately create a 400 error
@app.get("/demo-error")
async def demo_error():

    raise HTTPException(
        status_code=400,
        detail="This is a demonstration of a bad request"
    )


# 9. Deliberately create an unexpected 500 error
@app.get("/demo-server-error")
async def demo_server_error():

    raise RuntimeError("This is a test server error")


# 10. Display application statistics
@app.get("/stats")
async def stats(request: Request):

    return {
        "total_requests": app.state.total_requests,
        "error_requests": app.state.error_requests,
        "analyze_requests": app.state.analyze_requests,
        "cache_hits": app.state.cache_hits,
        "cache_misses": app.state.cache_misses,
        "cached_configurations": len(app.state.cache),
        "request_id": request.state.request_id
    }


# 11. Reset the cache
@app.post("/reset-cache")
async def reset_cache():

    app.state.cache.clear()

    return {
        "message": "Cache cleared successfully"
    }