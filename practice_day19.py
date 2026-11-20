
import logging
import string
import uuid

from contextlib import asynccontextmanager
from time import monotonic, perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# 1. Cache expiry time: 10 seconds
CACHE_TTL_SECONDS = 10

# 2. Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("day19")


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


# 6. Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.total_requests = 0
    app.state.error_requests = 0
    app.state.analyze_requests = 0

    app.state.cache_hits = 0
    app.state.cache_misses = 0
    app.state.cache_expirations = 0

    app.state.cache = {}
    app.state.request_durations_ms = []

    logger.info("Day 19 application starting")

    yield

    logger.info("Day 19 application shutting down")


app = FastAPI(lifespan=lifespan)


# 7. Middleware: request tracking and performance
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


# 8. Remove expired cache entries
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


# 9. Analyse text and use TTL caching
@app.post("/analyze")
async def analyze(data: TextRequest, request: Request):

    start_time = perf_counter()
    state = request.app.state

    words = list(iter_words(data.text))

    if not words:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least one valid word"
        )

    state.analyze_requests += 1

    # Remove expired entries first
    remove_expired_cache(request.app)

    # Create a unique cache key
    cache_key = (tuple(words), data.batch_size)

    # Check whether the result exists
    cached_entry = state.cache.get(cache_key)

    if cached_entry is not None:

        state.cache_hits += 1

        remaining_seconds = round(
            cached_entry["expires_at"] - monotonic(), 2
        )

        processing_ms = round(
            (perf_counter() - start_time) * 1000, 3
        )

        return {
            **cached_entry["result"],
            "cache_hit": True,
            "cache_expires_in_seconds": remaining_seconds,
            "processing_ms": processing_ms,
            "request_id": request.state.request_id
        }

    # Cache miss: calculate a new result
    state.cache_misses += 1

    batches = list(iter_batches(words, data.batch_size))

    result = {
        "batches": batches,
        "total_words": len(words),
        "total_batches": len(batches),
        "unique_words": len(set(words))
    }

    # Save result with an expiry time
    state.cache[cache_key] = {
        "result": result,
        "expires_at": monotonic() + CACHE_TTL_SECONDS
    }

    processing_ms = round(
        (perf_counter() - start_time) * 1000, 3
    )

    return {
        **result,
        "cache_hit": False,
        "cache_expires_in_seconds": CACHE_TTL_SECONDS,
        "processing_ms": processing_ms,
        "request_id": request.state.request_id
    }


# 10. Check cache information
@app.get("/cache")
async def cache_info(request: Request):

    remove_expired_cache(request.app)

    return {
        "cached_configurations": len(request.app.state.cache),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "cache_hits": request.app.state.cache_hits,
        "cache_misses": request.app.state.cache_misses,
        "cache_expirations": request.app.state.cache_expirations
    }


# 11. Display performance and tracking statistics
@app.get("/stats")
async def stats(request: Request):

    state = request.app.state

    durations = state.request_durations_ms

    average_ms = (
        round(sum(durations) / len(durations), 3)
        if durations else 0
    )

    last_request_ms = durations[-1] if durations else 0

    return {
        "total_requests": state.total_requests,
        "error_requests": state.error_requests,
        "analyze_requests": state.analyze_requests,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "cache_expirations": state.cache_expirations,
        "cached_configurations": len(state.cache),
        "average_request_ms": average_ms,
        "last_request_ms": last_request_ms
    }


# 12. Reset the cache
@app.post("/reset-cache")
async def reset_cache(request: Request):

    state = request.app.state
    removed_entries = len(state.cache)

    state.cache.clear()

    return {
        "message": "Cache cleared",
        "removed_entries": removed_entries
    }
