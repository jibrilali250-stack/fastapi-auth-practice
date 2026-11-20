
import asyncio
import logging
import string
import uuid

from contextlib import asynccontextmanager
from time import monotonic, perf_counter

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Request
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# 1. Cache settings
CACHE_TTL_SECONDS = 10
CLEANUP_INTERVAL_SECONDS = 5


# 2. Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("day20")


# 3. Validate incoming data
class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    batch_size: int = Field(default=3, ge=1, le=10)


# 4. Generator: iterate through words
def iter_words(text):
    for word in text.lower().split():
        cleaned = word.strip(string.punctuation)

        if cleaned:
            yield cleaned


# 5. Generator: create batches
def iter_batches(words, batch_size):
    batch = []

    for word in words:
        batch.append(word)

        if len(batch) == batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


# 6. Remove expired cache entries
def remove_expired_cache(app):

    now = monotonic()

    expired_keys = [
        key
        for key, entry in app.state.cache.items()
        if entry["expires_at"] <= now
    ]

    for key in expired_keys:
        del app.state.cache[key]

    app.state.cache_expirations += len(expired_keys)

    return len(expired_keys)


# 7. Background worker: automatic cache cleanup
async def cache_cleanup_worker(app):

    while True:

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

        removed = remove_expired_cache(app)

        app.state.cleanup_runs += 1

        if removed:
            logger.info(
                "Background cleanup removed %s expired entries",
                removed
            )


# 8. Background task: log completed analysis
def log_analysis_completed(request_id, total_words, cache_hit):

    logger.info(
        "Background task completed request_id=%s total_words=%s cache_hit=%s",
        request_id,
        total_words,
        cache_hit
    )


# 9. Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.total_requests = 0
    app.state.error_requests = 0
    app.state.analyze_requests = 0

    app.state.cache_hits = 0
    app.state.cache_misses = 0
    app.state.cache_expirations = 0

    app.state.cleanup_runs = 0

    app.state.cache = {}
    app.state.request_durations_ms = []

    logger.info("Day 20 application starting")

    # Start automatic cleanup worker
    cleanup_task = asyncio.create_task(
        cache_cleanup_worker(app)
    )

    try:
        yield

    finally:
        # Stop worker when application shuts down
        cleanup_task.cancel()

        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Background cleanup worker stopped")

        logger.info("Day 20 application shutting down")


app = FastAPI(lifespan=lifespan)


# 10. Middleware: request IDs and tracking
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

    duration_ms = round(
        (perf_counter() - start_time) * 1000, 3
    )

    if path not in DOC_PATHS:

        durations = request.app.state.request_durations_ms
        durations.append(duration_ms)

        if len(durations) > 100:
            durations.pop(0)

        if response.status_code >= 400:
            request.app.state.error_requests += 1

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


# 11. Analyse text with TTL caching
@app.post("/analyze")
async def analyze(
    data: TextRequest,
    request: Request,
    background_tasks: BackgroundTasks
):

    start_time = perf_counter()
    state = request.app.state

    words = list(iter_words(data.text))

    if not words:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least one valid word"
        )

    state.analyze_requests += 1

    # Remove expired entries before checking cache
    remove_expired_cache(request.app)

    cache_key = (tuple(words), data.batch_size)

    # Check the cache
    cached_entry = state.cache.get(cache_key)

    if cached_entry is not None:

        state.cache_hits += 1

        remaining_seconds = round(
            cached_entry["expires_at"] - monotonic(), 2
        )

        processing_ms = round(
            (perf_counter() - start_time) * 1000, 3
        )

        # Run a task after sending the response
        background_tasks.add_task(
            log_analysis_completed,
            request.state.request_id,
            cached_entry["result"]["total_words"],
            True
        )

        return {
            **cached_entry["result"],
            "cache_hit": True,
            "cache_expires_in_seconds": remaining_seconds,
            "processing_ms": processing_ms,
            "request_id": request.state.request_id
        }

    # Cache miss: calculate result
    state.cache_misses += 1

    batches = list(iter_batches(words, data.batch_size))

    result = {
        "batches": batches,
        "total_words": len(words),
        "total_batches": len(batches),
        "unique_words": len(set(words))
    }

    # Store result with expiry time
    state.cache[cache_key] = {
        "result": result,
        "expires_at": monotonic() + CACHE_TTL_SECONDS
    }

    processing_ms = round(
        (perf_counter() - start_time) * 1000, 3
    )

    background_tasks.add_task(
        log_analysis_completed,
        request.state.request_id,
        len(words),
        False
    )

    return {
        **result,
        "cache_hit": False,
        "cache_expires_in_seconds": CACHE_TTL_SECONDS,
        "processing_ms": processing_ms,
        "request_id": request.state.request_id
    }


# 12. Cache information
@app.get("/cache")
async def cache_info(request: Request):

    state = request.app.state

    return {
        "cached_configurations": len(state.cache),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "cleanup_interval_seconds": CLEANUP_INTERVAL_SECONDS,
        "cleanup_runs": state.cleanup_runs,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "cache_expirations": state.cache_expirations
    }


# 13. Performance and application statistics
@app.get("/stats")
async def stats(request: Request):

    state = request.app.state
    durations = state.request_durations_ms

    average_ms = (
        round(sum(durations) / len(durations), 3)
        if durations else 0
    )

    return {
        "total_requests": state.total_requests,
        "error_requests": state.error_requests,
        "analyze_requests": state.analyze_requests,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "cache_expirations": state.cache_expirations,
        "cleanup_runs": state.cleanup_runs,
        "cached_configurations": len(state.cache),
        "average_request_ms": average_ms
    }


# 14. Reset cache
@app.post("/reset-cache")
async def reset_cache(request: Request):

    state = request.app.state
    removed = len(state.cache)

    state.cache.clear()

    return {
        "message": "Cache cleared successfully",
        "removed_entries": removed
    }
