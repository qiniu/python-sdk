from .timeout import *
from .echo import *
from .retry_me import *

routes = {
    '/timeout': handle_timeout,
    '/echo': handle_echo,
    '/retry_me': handle_retry_me,
    '/retry_me/__mgr__': handle_mgr_retry_me,
}
