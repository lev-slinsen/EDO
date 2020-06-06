import functools
import time

import settings as s

log = s.logger_dev.logger


def timer(func):
    @functools.wraps(func)
    async def timer_d(*args, **kwargs):
        start_time = time.perf_counter()
        value = await func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        log.debug(f'{func.__name__} finished in {run_time}')
        return value
    return timer_d


def bug_catcher(func):
    @functools.wraps(func)
    async def bug_catcher_d(*args, **kwargs):
        try:
            value = await func(*args, **kwargs)
        except Exception:
            log.error("Huston, we have a problem!", exc_info=True)
            return
        return value
    return bug_catcher_d
