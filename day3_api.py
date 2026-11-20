from contextlib import asynccontextmanager
from functools import lru_cache
from time import perf_counter
import logging

from fastapi import FastAPI, Query, Request

logging.basicConfig(level=logging.INFO)


# 1. APPLICATION LIFECYCLE
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.request_count = 0

    logging.info("Application starting")

    yield

    logging.info("Application shutting down")


app = FastAPI(lifespan=lifespan)


# 2. CACHING
@lru_cache(maxsize=100)
def calculate_square(number: int) -> int:
    logging.info("Calculating square of %s", number)
    return number * number


# 3. FASTAPI ENDPOINT
@app.get("/squares")
def get_squares(
    request: Request,
    limit: int = Query(default=10, ge=1, le=20)
):
    # TRACKING: Count endpoint requests
    request.app.state.request_count += 1
    current_request = request.app.state.request_count

    # TRACKING: Start timer
    start_time = perf_counter()

    # ITERATION: Calculate each square
    results = []

    for number in range(1, limit + 1):
        results.append({
            "number": number,
            "square": calculate_square(number)
        })

    # TRACKING: Measure elapsed time
    elapsed = perf_counter() - start_time

    logging.info(
        "Request %s processed %s numbers in %.6f seconds",
        current_request,
        len(results),
        elapsed
    )

    return {
        "request_number": current_request,
        "total": len(results),
        "elapsed_seconds": round(elapsed, 6),
        "results": results
    }