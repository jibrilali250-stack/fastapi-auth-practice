
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query

# 1. APPLICATION LIFECYCLE
@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.request_count = 0
    app.state.cache_hits = 0
    app.state.cache_misses = 0
    app.state.cache_resets = 0

    # Store different batch configurations
    app.state.batch_cache = {}

    print("Application starting")

    yield

    print("Application shutting down")
    print("Total requests:", app.state.request_count)

app = FastAPI(lifespan=lifespan)

# 2. ITERATION AND DYNAMIC BATCH PROCESSING
@app.get("/batches")
def get_batches(
    request: Request,
    limit: int = Query(default=10, ge=1, le=20),
    batch_size: int = Query(default=3, ge=1, le=10)
):

    state = request.app.state
    state.request_count += 1

    # Create a unique cache key
    cache_key = (limit, batch_size)

    # Check whether the result already exists
    if cache_key in state.batch_cache:

        batches = state.batch_cache[cache_key]
        state.cache_hits += 1
        cache_hit = True

    else:

        numbers = list(range(1, limit + 1))
        batches = []

        # Outer loop: divide numbers into batches
        for start in range(0, len(numbers), batch_size):

            current_batch = numbers[start:start + batch_size]
            squared_batch = []

            # Inner loop: calculate each square
            for number in current_batch:
                squared_batch.append(number ** 2)

            batches.append(squared_batch)

        # Save results in cache
        state.batch_cache[cache_key] = batches

        state.cache_misses += 1
        cache_hit = False

    return {
        "limit": limit,
        "batch_size": batch_size,
        "batches": batches,
        "cache_hit": cache_hit,
        "request_count": state.request_count
    }

# 3. TRACKING STATISTICS
@app.get("/stats")
def get_stats(request: Request):

    state = request.app.state
    state.request_count += 1

    return {
        "total_requests": state.request_count,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "cache_resets": state.cache_resets,
        "cached_configurations": len(state.batch_cache)
    }

# 4. SUMMARISE CACHED RESULTS
@app.get("/summary")
def get_summary(request: Request):

    state = request.app.state
    state.request_count += 1

    total_batches = 0
    total_values = 0
    sum_of_squares = 0
    configurations = []

    # Outer loop: examine each cached configuration
    for (limit, batch_size), batches in state.batch_cache.items():

        configurations.append({
            "limit": limit,
            "batch_size": batch_size
        })

        # Middle loop: examine each batch
        for batch in batches:

            total_batches += 1

            # Inner loop: examine each square
            for square in batch:

                total_values += 1
                sum_of_squares += square

    return {
        "configurations": configurations,
        "total_batches": total_batches,
        "total_values": total_values,
        "sum_of_squares": sum_of_squares,
        "request_count": state.request_count
    }

# 5. RESET THE CACHE
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