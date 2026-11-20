from contextlib import asynccontextmanager
from time import perf_counter
import string
import logging
import uuid

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field


# 1. Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("day16")


# 2. Validate incoming data
class TextRequest(BaseModel):

    text: str = Field(min_length=1, max_length=1000)

    batch_size: int = Field(default=3, ge=1, le=10)


# 3. Generate words one at a time
def iter_words(text):

    for raw_word in text.lower().split():

        word = raw_word.strip(string.punctuation)

        if word:
            yield word


# 4. Generate batches
def iter_batches(words, batch_size):

    current_batch = []

    for word in words:

        current_batch.append(word)

        if len(current_batch) == batch_size:

            yield current_batch

            current_batch = []

    if current_batch:
        yield current_batch


# 5. Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.total_requests = 0
    app.state.analyze_requests = 0

    app.state.cache_hits = 0
    app.state.cache_misses = 0

    app.state.batches_generated = 0
    app.state.cache_resets = 0

    app.state.total_processing_seconds = 0
    app.state.last_processing_ms = 0

    app.state.cache = {}

    logger.info("Day 16 application starting")

    yield

    logger.info("Application shutting down")

    logger.info(
        "Total requests: %s",
        app.state.total_requests
    )


app = FastAPI(lifespan=lifespan)


# 6. Track requests using middleware
TRACKED_PATHS = {
    "/analyze",
    "/stats",
    "/reset-cache"
}


@app.middleware("http")
async def track_requests(request: Request, call_next):

    # Generate a unique ID
    request_id = uuid.uuid4().hex[:8]

    request.state.request_id = request_id

    # Count our API endpoint requests
    if request.url.path in TRACKED_PATHS:

        request.app.state.total_requests += 1

    start_time = perf_counter()

    response = await call_next(request)

    elapsed_ms = round(
        (perf_counter() - start_time) * 1000,
        3
    )

    # Record the request information
    logger.info(
        "request_id=%s method=%s path=%s status_code=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms
    )

    # Send request ID back to the client
    response.headers["X-Request-ID"] = request_id

    return response


# 7. Analyse text
@app.post("/analyze")
def analyze(data: TextRequest, request: Request):

    start_time = perf_counter()

    state = request.app.state

    words = list(iter_words(data.text))

    if not words:

        raise HTTPException(
            status_code=400,
            detail="Please enter some words."
        )

    state.analyze_requests += 1

    cache_key = (tuple(words), data.batch_size)

    if cache_key in state.cache:

        result = state.cache[cache_key]

        state.cache_hits += 1

        cache_hit = True

    else:

        batches = []

        for batch in iter_batches(words, data.batch_size):

            batches.append(batch)

            state.batches_generated += 1

        result = {
            "batches": batches,
            "total_words": len(words),
            "total_batches": len(batches),
            "unique_words": len(set(words))
        }

        state.cache[cache_key] = result

        state.cache_misses += 1

        cache_hit = False

    elapsed_seconds = perf_counter() - start_time

    elapsed_ms = round(elapsed_seconds * 1000, 3)

    state.total_processing_seconds += elapsed_seconds

    state.last_processing_ms = elapsed_ms

    return {
        **result,
        "cache_hit": cache_hit,
        "processing_ms": elapsed_ms,
        "request_id": request.state.request_id
    }


# 8. Statistics endpoint
@app.get("/stats")
def stats(request: Request):

    state = request.app.state

    if state.analyze_requests:

        average_ms = round(
            state.total_processing_seconds
            / state.analyze_requests * 1000,
            3
        )

    else:

        average_ms = 0

    return {
        "total_requests": state.total_requests,
        "analyze_requests": state.analyze_requests,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "batches_generated": state.batches_generated,
        "cache_resets": state.cache_resets,
        "cached_configurations": len(state.cache),
        "last_processing_ms": state.last_processing_ms,
        "average_processing_ms": average_ms,
        "request_id": request.state.request_id
    }


# 9. Reset cache
@app.post("/reset-cache")
def reset_cache(request: Request):

    state = request.app.state

    state.cache.clear()

    state.cache_resets += 1

    return {
        "message": "Cache cleared",
        "cache_resets": state.cache_resets,
        "request_id": request.state.request_id
    }