import time
import threading


class CircuitBreaker:
    """熔断器 —— 当连续失败达到阈值时，暂时拒绝执行，避免雪崩"""

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(self, failure_threshold=3, recovery_timeout=10.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = self.STATE_CLOSED
        self._lock = threading.Lock()

    def execute(self, func, *args, **kwargs):
        with self._lock:
            if self.state == self.STATE_OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = self.STATE_HALF_OPEN
                    print("  🔶 熔断器进入半开状态，尝试探测...")
                else:
                    raise CircuitBreakerOpenError(
                        f"熔断器已打开，{self.recovery_timeout - (time.time() - self.last_failure_time):.0f}s 后可重试"
                    )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = self.STATE_CLOSED

    def _on_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = self.STATE_OPEN
                print(f"  🔴 连续失败 {self.failure_count} 次，熔断器打开！")


class CircuitBreakerOpenError(Exception):
    pass
