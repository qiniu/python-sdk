from .timeout import handle_timeout
from .echo import handle_echo

routes = {
    '/timeout': handle_timeout,
    '/echo': handle_echo
}
