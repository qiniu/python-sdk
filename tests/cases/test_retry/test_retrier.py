import qiniu.retry
import qiniu.retry.abc


class MaxRetryPolicy(qiniu.retry.abc.RetryPolicy):
    def __init__(self, max_times):
        super().__init__()
        self.max_times = max_times

    def is_important(self, attempt):
        return attempt.context[self]['retriedTimes'] >= self.max_times

    def init_context(self, context):
        context[self] = {
            'retriedTimes': 0
        }

    def should_retry(self, attempt):
        if not attempt.exception:
            return False
        return attempt.context[self]['retriedTimes'] < self.max_times

    def prepare_retry(self, attempt):
        pass

    def after_retry(self, attempt, policy):
        attempt.context[self]['retriedTimes'] += 1


class TestRetry:
    def test_retrier_with_code_block(self):
        retried_times = 0

        def handle_before_retry(_attempt, _policy):
            nonlocal retried_times
            retried_times += 1
            return True

        max_retry_times = 3
        retrier = qiniu.retry.Retrier(
            policies=[
                MaxRetryPolicy(max_times=max_retry_times)
            ],
            before_retry=handle_before_retry
        )

        tried_times = 0
        for attempt in retrier:
            with attempt:
                tried_times += 1
                raise Exception('mocked error')

        assert tried_times == max_retry_times + 1
        assert retried_times == max_retry_times

    def test_retrier_with_try_do(self):
        retried_times = 0

        def handle_before_retry(_attempt, _policy):
            nonlocal retried_times
            retried_times += 1
            return True

        max_retry_times = 3
        retrier = qiniu.retry.Retrier(
            policies=[
                MaxRetryPolicy(max_times=max_retry_times)
            ],
            before_retry=handle_before_retry
        )

        tried_times = 0

        def add_one(n):
            nonlocal tried_times
            tried_times += 1
            if tried_times <= 3:
                raise Exception('mock error')
            return n + 1

        result = retrier.try_do(add_one, 1)
        assert result == 2
        assert tried_times == max_retry_times + 1
        assert retried_times == max_retry_times

    def test_retrier_with_decorator(self):
        retried_times = 0

        def handle_before_retry(_attempt, _policy):
            nonlocal retried_times
            retried_times += 1
            return True

        max_retry_times = 3
        retrier = qiniu.retry.Retrier(
            policies=[
                MaxRetryPolicy(max_times=max_retry_times)
            ],
            before_retry=handle_before_retry
        )

        tried_times = 0

        @retrier.retry
        def add_one(n):
            nonlocal tried_times
            tried_times += 1
            if tried_times <= 3:
                raise Exception('mock error')
            return n + 1

        result = add_one(1)
        assert result == 2
        assert tried_times == max_retry_times + 1
        assert retried_times == max_retry_times
