"""Stand-in for ``numba.core.dispatcher``: no compiled dispatchers exist, so isinstance checks are always False."""


class Dispatcher:  # never instantiated
    pass
