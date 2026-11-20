
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query

# 1. APPLICATION LIFECYCLE
@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.request_count = 0
    app.state.cache_hits = 0
    app.state.cache_misses = 0
    app.state.cache_resets = 0

    # Store results for different batch sizes
    app.state.batch_cache = {}

    print("Application starting")

    yield

    print("Application shutting down")
    print("Total requests:", app.state.request_count)

app = FastAPI(lifespan=lifespan)

# 2. ITERATION AND BATCH PROCESSING
@app.get("/batches")
def get_batches(
    request: Request,
    batch_size: int = Query(default=3, ge=1, le=10)
):
    
   

    state = request.app.state
    state.request_count += 1

    # 3. CHECK THE CACHE
    if batch_size in state.batch_cache:

        state.cache_hits += 1
        batches = state.batch_cache[batch_size]
        cache_hit = True

    else:

        numbers = list(range(1, 11))
        batches = []

        # Divide numbers into batches
        for start in range(0, len(numbers), batch_size):

            current_batch = numbers[start:start + batch_size]

            squared_batch = []

            # Calculate each square
            for number in current_batch:
                squared_batch.append(number ** 2)

            batches.append(squared_batch)

        # Save results in cache
        state.batch_cache[batch_size] = batches

        state.cache_misses += 1
        cache_hit = False

    return {
        "batch_size": batch_size,
        "batches": batches,
        "cache_hit": cache_hit,
        "request_count": state.request_count
    }

# 4. TRACK APPLICATION STATISTICS
@app.get("/stats")
def get_stats(request: Request):

    state = request.app.state
    state.request_count += 1

    return {
        "total_requests": state.request_count,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "cache_resets": state.cache_resets
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
# 6. SUMMARISE ALL CACHED BATCHES

@app.get("/summary")
def get_summary(request: Request):

    state = request.app.state
    state.request_count += 1

    cached_batch_sizes = []
    total_batches = 0
    total_values = 0
    sum_of_squares = 0

    # Outer loop: examine each cached batch size
    for batch_size, batches in state.batch_cache.items():

        cached_batch_sizes.append(batch_size)
        total_batches += len(batches)

        # Middle loop: examine each batch
        for batch in batches:

            # Inner loop: examine each number
            for square in batch:

                total_values += 1
                sum_of_squares += square

    return {
        "cached_batch_sizes": cached_batch_sizes,
        "total_batches": total_batches,
        "total_values": total_values,
        "sum_of_squares": sum_of_squares,
        "request_count": state.request_count
    }