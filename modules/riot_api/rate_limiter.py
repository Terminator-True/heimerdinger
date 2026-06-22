import time
import threading


class TokenBucketLimiter:
    def __init__(self, rate: float, capacity: int = 1):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.lock = threading.Lock()
        self.timestamp = time.monotonic()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            self.timestamp = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            # need to wait
            needed = (1 - self.tokens) / self.rate
        time.sleep(needed)
        return self.acquire()
