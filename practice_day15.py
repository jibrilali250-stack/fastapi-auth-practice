from contextlib import asynccontextmanager
from time import perf_counter
import string

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field


# 1. Validate incoming data
class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    batch_size: int = Field(default=3, ge=1, le=10)


# 2. Generate words one at a time
def iter_words(text):

    for raw_word in text.lower().split():

        word = raw_word.strip(string.punctuation)

        if word:
            yield word


# 3. Generate batches using yield
def iter_batches(words, batch_size):

    current_batch = []

    for word in words:

        current_batch.append(word)

        if len(current_batch) == batch_size:

            yield current_batch
            current_batch = []

    if current_batch:
        yield current_batch


# 4. Application lifecycle
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

    print("Day 15 application starting")

    yield

    print("Application shutting down")
    print("Total API requests:", app.state.total_requests)
    print("Cache hits:", app.state.cache_hits)


app = FastAPI(lifespan=lifespan)


# 5. Analyse text
@app.post("/analyze")
def analyze(data: TextRequest, request: Request):

    start_time = perf_counter()

    state = request.app.state

    state.total_requests += 1

    words = list(iter_words(data.text))

    if not words:
        raise HTTPException(
            status_code=400,
            detail="Please enter some words."
        )

    state.analyze_requests += 1

    # Cache key includes words AND batch size
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

    # Measure processing time
    elapsed_seconds = perf_counter() - start_time

    elapsed_ms = round(elapsed_seconds * 1000, 3)

    state.total_processing_seconds += elapsed_seconds
    state.last_processing_ms = elapsed_ms

    return {
        "normalized_words": words,
        **result,
        "cache_hit": cache_hit,
        "processing_ms": elapsed_ms,
        "request_count": state.total_requests
    }


# 6. Statistics endpoint
@app.get("/stats")
def stats(request: Request):

    state = request.app.state

    state.total_requests += 1

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
        "average_processing_ms": average_ms
    }


# 7. Reset cache
@app.post("/reset-cache")
def reset_cache(request: Request):

    state = request.app.state

    state.total_requests += 1

    state.cache.clear()

    state.cache_resets += 1

    return {
        "message": "Cache cleared",
        "cache_resets": state.cache_resets
    }