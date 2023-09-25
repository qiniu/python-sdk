import abc

import qiniu.config as config

# type import
from qiniu.auth import Auth # noqa


class UploaderBase(object):
    """
    Attributes
    ----------
    bucket_name: str
    auth: Auth
    regions: list[Region]
    """
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        bucket_name,
        **kwargs
    ):
        """
        Parameters
        ----------
        bucket_name: str
            The name of bucket which you want to upload to.
        auth: Auth
            The instance of Auth to sign requests.
        regions: list[Region], default=[]
            The regions of bucket. It will be queried if not specified.
        kwargs
            The others arguments may be used by subclass.
        """
        self.bucket_name = bucket_name

        # change the default when implements AuthProvider
        self.auth = kwargs.get('auth', None)

        regions = kwargs.get('regions', [])
        # remove the check when implement RegionsProvider
        # if not regions:
        #     raise TypeError('You must provide the regions')
        self.regions = regions

        hosts_cache_dir = kwargs.get('hosts_cache_dir', None)
        self.hosts_cache_dir = hosts_cache_dir

    def get_up_token(self, **kwargs):
        """
        Generate up token

        Parameters
        ----------
        bucket_name: str
        key: str
        expired: int
        policy: dict
        strict_policy: bool

        Returns
        -------
        str
        """
        if not self.auth:
            raise ValueError('can not get up_token by auth not provided')

        bucket_name = kwargs.get('bucket_name', self.bucket_name)

        kwargs_for_up_token = {
            k: kwargs[k]
            for k in [
                'key', 'expires', 'policy', 'strict_policy'
            ] if k in kwargs
        }
        up_token = self.auth.upload_token(
            bucket=bucket_name,
            **kwargs_for_up_token
        )
        return up_token

    def _get_regions(self):
        if self.regions:
            return self.regions

        default_region = config.get_default('default_zone')
        if default_region:
            self.regions = [default_region]

        return self.regions

    def _get_up_hosts(self, access_key=None):
        """
        This will be deprecated when implement regions and endpoints

        Returns
        -------
        list[str]
        """
        if not self.auth and not access_key:
            raise ValueError('Must provide access_key if auth is unavailable.')
        if not access_key:
            access_key = self.auth.get_access_key()

        regions = self._get_regions()

        if not regions:
            raise ValueError('No region available.')

        if regions[0].up_host and regions[0].up_host_backup:
            return [
                regions[0].up_host,
                regions[0].up_host_backup
            ]

        # this is correct, it does return hosts. bad function name by legacy
        return regions[0].get_up_host(
            ak=access_key,
            bucket=self.bucket_name,
            home_dir=self.hosts_cache_dir
        )

    @abc.abstractmethod
    def upload(
        self,
        key,
        file_path,
        data,
        data_size,
        modify_time,

        part_size,
        mime_type,
        metadata,
        file_name,
        custom_vars,
        **kwargs
    ):
        """
        Upload method

        Parameters
        ----------
        key: str
        file_path: str
        data: IOBase
        data_size: int
        modify_time: int

        part_size: int
        mime_type: str
        metadata: dict
        file_name: str
        custom_vars: dict
        kwargs: dict

        Returns
        -------
        ret: dict
            The parsed response body
        info
            The response
        """
