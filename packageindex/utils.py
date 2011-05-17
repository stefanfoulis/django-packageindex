import sys, traceback



def debug(func):
    # @debug is handy when debugging distutils requests
    def _wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            traceback.print_exception(*sys.exc_info())
    return _wrapped