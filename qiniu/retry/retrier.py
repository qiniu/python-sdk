import functools

from .attempt import Attempt


def before_retry_nothing(attempt, policy):
    return True


class Retrier:
    def __init__(self, policies=None, before_retry=None):
        """
        Parameters
        ----------
        policies: list[qiniu.retry.abc.RetryPolicy]
        before_retry: callable
            `(attempt: Attempt, policy: qiniu.retry.abc.RetryPolicy) -> bool`
        """
        self.policies = policies if policies is not None else []
        self.before_retry = before_retry if before_retry is not None else before_retry_nothing

    def __iter__(self):
        retrying = Retrying(
            # change to `list.copy` for more readable when min version of python update to >= 3
            policies=self.policies[:],
            before_retry=self.before_retry
        )
        retrying.init_context()
        while True:
            attempt = Attempt(retrying.context)
            yield attempt
            if (
                hasattr(attempt.exception, 'no_need_retry') and
                attempt.exception.no_need_retry
            ):
                break
            policy = retrying.get_retry_policy(attempt)
            if not policy:
                break
            if not self.before_retry(attempt, policy):
                break
            policy.prepare_retry(attempt)
            retrying.after_retried(attempt, policy)
        if attempt.exception:
            raise attempt.exception

    def try_do(
        self,
        func,
        *args,
        **kwargs
    ):
        attempt = None
        for attempt in self:
            with attempt:
                if kwargs.get('with_retry_context', False):
                    # inject retry_context
                    kwargs['retry_context'] = attempt.context
                if 'with_retry_context' in kwargs:
                    del kwargs['with_retry_context']

                # store result
                attempt.result = func(*args, **kwargs)

        if attempt is None:
            raise RuntimeError('attempt is none')

        return attempt.result

    def _wrap(self, with_retry_context=False):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return self.try_do(
                    func,
                    with_retry_context=with_retry_context,
                    *args,
                    **kwargs
                )

            return wrapper

        return decorator

    def retry(self, *args, **kwargs):
        """
        decorator to retry
        """
        if len(args) == 1 and callable(args[0]):
            return self.retry()(args[0])
        else:
            return self._wrap(**kwargs)


class Retrying:
    def __init__(self, policies, before_retry):
        """
        Parameters
        ----------
        policies: list[qiniu.retry.abc.RetryPolicy]
        before_retry: callable
            `(attempt: Attempt, policy: qiniu.retry.abc.RetryPolicy) -> bool`
        """
        self.policies = policies
        self.before_retry = before_retry
        self.context = {}

    def init_context(self):
        for policy in self.policies:
            policy.init_context(self.context)

    def get_retry_policy(self, attempt):
        """

        Parameters
        ----------
        attempt: Attempt

        Returns
        -------
        qiniu.retry.abc.RetryPolicy

        """
        policy = None

        # find important policy
        for p in self.policies:
            if p.is_important(attempt):
                policy = p
                break
        if policy and policy.should_retry(attempt):
            return policy
        else:
            policy = None

        # find retry policy
        for p in self.policies:
            if p.should_retry(attempt):
                policy = p
                break

        return policy

    def after_retried(self, attempt, policy):
        for p in self.policies:
            p.after_retry(attempt, policy)


"""
Examples
--------
retrier = Retrier()
result = None
for attempt in retrier:
    with attempt:
        endpoint = attempt.context.get('endpoint')
        result = upload(endpoint)
        attempt.result = result
return result
"""

"""
Examples
--------
def foo():
    print('hi')

retrier = Retrier()
retrier.try_do(foo)
"""

"""
Examples
--------
retrier = Retrier()


@retrier.retry
def foo():
    print('hi')

foo()
"""
