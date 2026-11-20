
import asyncio
import logging
import string
import uuid

from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# 1. Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("day18")


# 2. Validate incoming data
class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    batch_size: int = Field(default=3, ge=1, le=10)


# 3. Generator: iterate through words
def iter_words(text):
    for word in text.lower().split():
        cleaned = word.strip(string.punctuation)

        if cleaned:
            yield cleaned


# 4. Generator: create batches
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
    app.state.slow_requests = 0

    app.state.analyze_requests = 0
    app.state.cache_hits = 0
    app.state.cache_misses = 0

    app.state.cache = {}

    # Store the latest 100 request durations
    app.state.request_durations_ms = []

    logger.info("Day 18 application starting")

    yield

    logger.info("Day 18 application shutting down")


app = FastAPI(lifespan=lifespan)


# 6. Middleware: measure every request
DOC_PATHS = {"/docs", "/openapi.json", "/redoc"}

SLOW_REQUEST_THRESHOLD_MS = 100


@app.middleware("http")
async def monitor_requests(request: Request, call_next):

    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id

    path = request.url.path

    if path not in DOC_PATHS:
        app.state.total_requests += 1

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

    duration_ms = round(
        (perf_counter() - start_time) * 1000, 3
    )

    if path not in DOC_PATHS:

        # Save the request duration
        durations = app.state.request_durations_ms
        durations.append(duration_ms)

        # Keep only the latest 100 measurements
        if len(durations) > 100:
            durations.pop(0)

        # Track unsuccessful requests
        if response.status_code >= 400:
            app.state.error_requests += 1

        # Track slow requests
        if duration_ms >= SLOW_REQUEST_THRESHOLD_MS:
            app.state.slow_requests += 1

    logger.info(
        "request_id=%s method=%s path=%s status_code=%s duration_ms=%s",
        request_id,
        request.method,
        path,
        response.status_code,
        duration_ms
    )

    response.headers["X-Request-ID"] = request_id

    return response


# 7. Analyse text and use caching
@app.post("/analyze")
async def analyze(data: TextRequest, request: Request):

    start_time = perf_counter()

    words = list(iter_words(data.text))

    if not words:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least one valid word"
        )

    app.state.analyze_requests += 1

    cache_key = (tuple(words), data.batch_size)

    if cache_key in app.state.cache:

        app.state.cache_hits += 1

        result = app.state.cache[cache_key]

        processing_ms = round(
            (perf_counter() - start_time) * 1000, 3
        )

        return {
            **result,
            "cache_hit": True,
            "processing_ms": processing_ms,
            "request_id": request.state.request_id
        }

    app.state.cache_misses += 1

    batches = list(iter_batches(words, data.batch_size))

    result = {
        "batches": batches,
        "total_words": len(words),
        "total_batches": len(batches),
        "unique_words": len(set(words))
    }

    app.state.cache[cache_key] = result

    processing_ms = round(
        (perf_counter() - start_time) * 1000, 3
    )

    return {
        **result,
        "cache_hit": False,
        "processing_ms": processing_ms,
        "request_id": request.state.request_id
    }


# 8. Create a deliberately slow endpoint
@app.get("/demo-slow")
async def demo_slow(
    delay_seconds: float = Query(default=0.3, ge=0.1, le=2.0)
):

    await asyncio.sleep(delay_seconds)

    return {
        "message": "Slow request completed",
        "delay_seconds": delay_seconds
    }


# 9. Demonstrate a controlled error
@app.get("/demo-error")
async def demo_error():

    raise HTTPException(
        status_code=400,
        detail="This is a demonstration error"
    )


# 10. Display performance statistics
@app.get("/stats")
async def stats(request: Request):

    durations = app.state.request_durations_ms

    if durations:
        average_ms = round(
            sum(durations) / len(durations), 3
        )
        last_request_ms = durations[-1]
    else:
        average_ms = 0
        last_request_ms = 0

    return {
        "total_requests": app.state.total_requests,
        "error_requests": app.state.error_requests,
        "slow_requests": app.state.slow_requests,
        "analyze_requests": app.state.analyze_requests,
        "cache_hits": app.state.cache_hits,
        "cache_misses": app.state.cache_misses,
        "cached_configurations": len(app.state.cache),
        "average_request_ms_last_100": average_ms,
        "last_request_ms": last_request_ms,
        "duration_samples": len(durations),
        "request_id": request.state.request_id
    }


# 11. Reset the cache
@app.post("/reset-cache")
async def reset_cache():

    app.state.cache.clear()

    return {
        "message": "Cache cleared successfully"
    }
