
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

# 1. VALIDATE USER INPUT
class ProcessRequest(BaseModel):

    numbers: list[int] = Field(
        min_length=1,
        max_length=20
    )

    batch_size: int = Field(
        default=2,
        ge=1,
        le=10
    )

# 2. APPLICATION LIFECYCLE
@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.request_count = 0
    app.state.cache_hits = 0
    app.state.cache_misses = 0
    app.state.cache_resets = 0

    app.state.batch_cache = {}

    print("Application starting")

    yield

    print("Application shutting down")
    print("Total requests:", app.state.request_count)

app = FastAPI(lifespan=lifespan)

# 3. PROCESS USER NUMBERS
@app.post("/process")
def process_numbers(
    data: ProcessRequest,
    request: Request
):

    state = request.app.state
    state.request_count += 1

    # Create a unique cache key
    cache_key = (
        tuple(data.numbers),
        data.batch_size
    )

    # 4. CHECK THE CACHE
    if cache_key in state.batch_cache:

        batches = state.batch_cache[cache_key]

        state.cache_hits += 1
        cache_hit = True

    else:

        batches = []

        # Outer loop: divide numbers into batches
        for start in range(
            0,
            len(data.numbers),
            data.batch_size
        ):

            current_batch = data.numbers[
                start:start + data.batch_size
            ]

            squared_batch = []

            # Inner loop: calculate squares
            for number in current_batch:

                squared_batch.append(number ** 2)

            batches.append(squared_batch)

        # Save results
        state.batch_cache[cache_key] = batches

        state.cache_misses += 1
        cache_hit = False

    return {
        "numbers": data.numbers,
        "batch_size": data.batch_size,
        "batches": batches,
        "cache_hit": cache_hit,
        "request_count": state.request_count
    }

# 5. TRACK STATISTICS
@app.get("/stats")
def get_stats(request: Request):

    state = request.app.state
    state.request_count += 1

    return {
        "total_requests": state.request_count,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "cache_resets": state.cache_resets,
        "cached_configurations": len(
            state.batch_cache
        )
    }

# 6. RESET CACHE
@app.post("/reset-cache")
def reset_cache(request: Request):

    state = request.app.state
    state.request_count += 1

    state.batch_cache.clear()
    state.cache_resets += 1

    return {
        "message": "Cache cleared",
        "cache_resets": state.cache_resets
    }