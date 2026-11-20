from fastapi import FastAPI
from functools import lru_cache
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)


@lru_cache(maxsize=100)
def calculate_square(number: int) -> int:
    logging.info("Calculating square for %s", number)
    return number * number


@app.get("/squares")
def get_squares():
    results = []

    for number in range(1, 6):
        results.append({
            "number": number,
            "square": calculate_square(number)
        })

    logging.info("Starting square calculations")

    return {
        "total": len(results),
        "results": results
    }
