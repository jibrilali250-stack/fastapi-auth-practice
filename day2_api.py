from fastapi import FastAPI, Query
from functools import lru_cache
import logging
import time

app = FastAPI()

logging.basicConfig(level=logging.INFO)


# 1. CACHING
@lru_cache(maxsize=100)
def calculate_square(number: int) -> int:
    logging.info("Calculating square of %s", number)
    return number * number


# 2. FASTAPI ENDPOINT
@app.get("/squares")
def get_squares(limit: int = Query(default=5, ge=1, le=20)):

    # 3. TRACKING: Start the timer
    start_time = time.perf_counter()

    results = []

    # 4. ITERATION
    for number in range(1, limit + 1):
        square = calculate_square(number)

        results.append({
            "number": number,
            "square": square
        })

    # 5. TRACKING: Measure elapsed time
    elapsed = time.perf_counter() - start_time

    logging.info(f"Processed {len(results)} numbers (limit={limit}) in {elapsed:.6f} seconds")



    # 6. RETURN THE RESPONSE
    return {
        "total": len(results),
        "elapsed_seconds": round(elapsed, 6),
        "cache_stats": str(calculate_square.cache_info()),
        "results": results
    }



    

    

   


