import abc


class RetryPolicy(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def init_context(self, context):
        """
        initial context values the policy required

        Parameters
        ----------
        context: dict
        """

    @abc.abstractmethod
    def should_retry(self, attempt):
        """
        if returns True, this policy will be applied

        Parameters
        ----------
        attempt: qiniu.retry.attempt.Attempt

        Returns
        -------
        bool
        """

    @abc.abstractmethod
    def prepare_retry(self, attempt):
        """
        apply this policy to change the context values for next attempt

        Parameters
        ----------
        attempt: qiniu.retry.attempt.Attempt
        """

    def is_important(self, attempt):
        """
        if returns True, this policy will be applied, whether it should retry or not.
        this is useful when want to stop retry.

        Parameters
        ----------
        attempt: qiniu.retry.attempt.Attempt

        Returns
        -------
        bool
        """

    def after_retry(self, attempt, policy):
        """
        Parameters
        ----------
        attempt: qiniu.retry.attempt.Attempt
        policy: RetryPolicy
        """
