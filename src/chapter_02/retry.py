import time
import random


class ExponentialBackoffRetry:
    """指数退避重试 —— 遇到可重试错误时自动延迟重试"""

    def __init__(self, max_retries=3, base_delay=1.0, max_delay=30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def retry(self, func, *args, **kwargs):
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt == self.max_retries:
                    raise

                delay = min(
                    self.base_delay * (2 ** attempt) + random.uniform(0, 0.5),
                    self.max_delay,
                )

                print(f"  ⚠ 第 {attempt + 1} 次重试失败，{delay:.1f}s 后重试... (原因: {e})")
                time.sleep(delay)

        raise last_exception
