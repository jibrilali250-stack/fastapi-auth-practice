from contextlib import asynccontextmanager
from functools import lru_cache
import logging

from fastapi import FastAPI, Query, Request

logging.basicConfig(level=logging.INFO)


# 1. APPLICATION LIFECYCLE
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.stats = {
        "requests": 0,
        "numbers_processed": 0
    }

    logging.info("Application started")

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
    limit: int = Query(default=5, ge=1, le=20)
):
    stats = request.app.state.stats

    # TRACKING: Count requests
    stats["requests"] += 1

    results = []

    # ITERATION: Process each number
    for number in range(1, limit + 1):
        square = calculate_square(number)

        results.append({
            "number": number,
            "square": square
        })

    # TRACKING: Count processed items
    stats["numbers_processed"] += len(results)

    logging.info(
        "Request %s processed %s numbers",
        stats["requests"],
        len(results)
    )

    return {
        "total": len(results),
        "results": results
    }


# 4. STATISTICS ENDPOINT
@app.get("/stats")
def get_stats(request: Request):
    return request.app.state.stats