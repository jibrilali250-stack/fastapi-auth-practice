# day1_practice.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from functools import lru_cache

# ---- TRACKING: a simple in-memory counter ----
stats = {"processed_items": 0}

# ---- LIFECYCLE: startup / shutdown events ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the app starts
    print("🟢 App starting up...")
    stats["processed_items"] = 0
    yield
    # Runs once when the app shuts down
    print(f"🔴 App shutting down. Total processed: {stats['processed_items']}")

app = FastAPI(lifespan=lifespan)

# ---- CACHING: remember results for the same input ----
@lru_cache(maxsize=128)
def square(n: int) -> int:
    """Cache the square of each number so we don't recalculate."""
    print(f"  ⚙️  Computing square of {n}")
    return n * n

# ---- ITERATION + everything combined ----
@app.get("/process/{numbers}")
def process_numbers(numbers: str):
    """
    Accept comma-separated numbers, e.g. /process/1,2,3,4,5
    Iterate, compute squares (cached), track how many items processed.
    """
    # Convert "1,2,3" -> [1, 2, 3]
    nums = [int(x.strip()) for x in numbers.split(",") if x.strip()]


    squares = []
    for n in nums:                       # ITERATION
        squares.append(square(n))        # CACHING via lru_cache

    stats["processed_items"] += len(nums)  # TRACKING

    return {
        "input": nums,
        "squares": squares,
        "total_processed": stats["processed_items"],
    }
