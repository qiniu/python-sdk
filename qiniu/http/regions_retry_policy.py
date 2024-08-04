from qiniu.retry.abc import RetryPolicy

from .region import Region


class RegionsRetryPolicy(RetryPolicy):
    def __init__(
        self,
        regions_provider,
        service_names,
        preferred_endpoints_provider=None,
        on_change_region=None
    ):
        """
        Parameters
        ----------
        regions_provider: Iterable[Region]
        service_names: list[ServiceName or str]
        preferred_endpoints_provider: Iterable[Endpoint]
        on_change_region: Callable
            `(context: dict) -> None`
        """
        self.regions_provider = regions_provider
        self.service_names = service_names
        if not service_names:
            raise ValueError('Must provide at least one service name')
        if preferred_endpoints_provider is None:
            preferred_endpoints_provider = []
        self.preferred_endpoints_provider = preferred_endpoints_provider
        self.on_change_region = on_change_region

    def init_context(self, context):
        """
        Parameters
        ----------
        context: dict
        """
        self._init_regions(context)
        self._prepare_endpoints(context)

    def should_retry(self, attempt):
        """
        Parameters
        ----------
        attempt: Attempt
        """
        return (
            len(attempt.context.get('alternative_regions', [])) > 0 or
            len(attempt.context.get('alternative_service_names', [])) > 0
        )

    def prepare_retry(self, attempt):
        """
        Parameters
        ----------
        attempt: Attempt
        """
        if attempt.context.get('alternative_service_names'):
            # change service for next try
            attempt.context['service_name'] = attempt.context.get('alternative_service_names').pop(0)
        elif attempt.context.get('alternative_regions'):
            # change region for next try
            attempt.context['region'] = attempt.context.get('alternative_regions').pop(0)
            if callable(self.on_change_region):
                self.on_change_region(attempt.context)
        else:
            raise RuntimeError('There isn\'t available region or service for next try')
        self._prepare_endpoints(attempt.context)

    def _init_regions(self, context):
        """
        Parameters
        ----------
        context: dict
        """
        regions = list(self.regions_provider)
        preferred_endpoints = list(self.preferred_endpoints_provider)
        if not regions and not preferred_endpoints:
            raise ValueError('There isn\'t available region or preferred endpoint')

        if not preferred_endpoints:
            # regions are not empty implicitly by above if condition
            context['alternative_regions'] = regions
            context['region'] = context['alternative_regions'].pop(0)
            # shallow copy list
            # change to `list.copy` for more readable when min version of python update to >= 3
            context['alternative_service_names'] = self.service_names[:]
            context['service_name'] = context['alternative_service_names'].pop(0)
            return

        # find preferred service name and region by preferred endpoints
        preferred_region_index = -1
        preferred_service_index = -1
        for ri, region in enumerate(regions):
            for si, service_name in enumerate(self.service_names):
                if any(
                    pe.host in [
                        e.host for e in region.services.get(service_name, [])
                    ]
                    for pe in preferred_endpoints
                ):
                    preferred_region_index = ri
                    preferred_service_index = si
                    break

        # initialize the order of service_names and regions
        if preferred_region_index < 0:
            # shallow copy list
            # change to `list.copy` for more readable when min version of python update to >= 3
            context['alternative_service_names'] = self.service_names[:]
            context['service_name'] = context['alternative_service_names'].pop(0)

            context['region'] = Region(
                region_id='preferred_region',
                services={
                    context['service_name']: preferred_endpoints
                }
            )
            context['alternative_regions'] = regions
        else:
            # regions are not empty implicitly by above if condition
            # preferred endpoints are in a known region, then reorder the regions and services
            context['alternative_regions'] = regions
            context['region'] = context['alternative_regions'].pop(preferred_region_index)
            # shallow copy list
            # change to `list.copy` for more readable when min version of python update to >= 3
            context['alternative_service_names'] = self.service_names[:]
            context['service_name'] = context['alternative_service_names'].pop(preferred_service_index)

    def _prepare_endpoints(self, context):
        """
        Parameters
        ----------
        context: dict
        """
        # shallow copy list
        # change to `list.copy` for more readable when min version of python update to >= 3
        endpoints = context['region'].services.get(context['service_name'], [])[:]
        while not endpoints:
            if context['alternative_service_names']:
                context['service_name'] = context['alternative_service_names'].pop(0)
                endpoints = context['region'].services.get(context['service_name'], [])[:]
            elif context['alternative_regions']:
                context['region'] = context['alternative_regions'].pop(0)
                # shallow copy list
                # change to `list.copy` for more readable when min version of python update to >= 3
                context['alternative_service_names'] = self.service_names[:]
                context['service_name'] = context['alternative_service_names'].pop(0)
                endpoints = context['region'].services.get(context['service_name'], [])[:]
                if callable(self.on_change_region):
                    self.on_change_region(context)
            else:
                raise RuntimeError(
                    'There isn\'t available endpoint for {0} service(s) in any available regions'.format(
                        ', '.join(self.service_names)
                    )
                )
        context['alternative_endpoints'] = endpoints
        context['endpoint'] = context['alternative_endpoints'].pop(0)
