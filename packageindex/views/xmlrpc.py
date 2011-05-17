import xmlrpclib

from django.http import HttpResponseNotAllowed, HttpResponse

from packageindex import conf
from packageindex.models import Package, Release

class XMLRPCResponse(HttpResponse):
    """ A wrapper around the base HttpResponse that dumps the output for xmlrpc
    use """
    def __init__(self, params=(), methodresponse=True, *args, **kwargs):
        super(XMLRPCResponse, self).__init__(xmlrpclib.dumps(params,
                                                             methodresponse=methodresponse),
                                             *args, **kwargs)

def parse_xmlrpc_request(request):
    """
    Parse the request and dispatch to the appropriate view
    """
    args, command = xmlrpclib.loads(request.raw_post_data)
    
    if command in conf.XMLRPC_COMMANDS:
        view_func = conf.XMLRPC_COMMANDS[command]
        if isinstance(view_func, basestring):
            module, func_name = view_func.rsplit('.', 1)
            view_func = getattr(__import__(module, {}, {}, [func_name]), func_name)
            conf.XMLRPC_COMMANDS[command] = view_func
        return view_func(request, *args)
    else:
        return HttpResponseNotAllowed(conf.XMLRPC_COMMANDS.keys())

def list_packages(request):
    return XMLRPCResponse(params=(list(Package.objects.all().values_list('name', flat=True)),),
                          content_type='text/xml')

def package_releases(request, package_name, show_hidden=False):
    try:
        return XMLRPCResponse(params=(list(Package.objects.get(name=package_name).releases.filter(hidden=show_hidden).values_list('version', flat=True)),))
    except Package.DoesNotExist:
        return XMLRPCResponse(params=([],))

def release_urls(request, package_name, version):
    base_url = '%s://%s' % (request.is_secure() and 'https' or 'http',
                              request.get_host())
    dists = []
    try:
        for dist in Package.objects.get(name=package_name).releases.get(version=version).distributions.all():
            dists.append({
                'url': '%s%s' % (base_url, dist.get_absolute_url()),
                'packagetype': dist.filetype,
                'filename': dist.filename,
                'size': dist.size,
                'md5_digest': dist.md5_digest,
                'downloads': 0,
                'has_sig': len(dist.signature)>0,
                'python_version': dist.pyversion,
                'comment_text': dist.comment
            })
    except (Package.DoesNotExist, Release.DoesNotExist):
        pass
    
    return XMLRPCResponse(params=(dists,))

def release_data(request, package_name, version):
    output = {
        'name': '',
        'version': '',
        'stable_version': '',
        'author': '',
        'author_email': '',
        'maintainer': '',
        'maintainer_email': '',
        'home_page': '',
        'license': '',
        'summary': '',
        'description': '',
        'keywords': '',
        'platform': '',
        'download_url': '',
        'classifiers': '',
        'requires': '',
        'requires_dist': '',
        'provides': '',
        'provides_dist': '',
        'requires_external': '',
        'requires_python': '',
        'obsoletes': '',
        'obsoletes_dist': '',
        'project_url': '',
    }
    try:
        release = Package.objects.get(name=package_name).releases.get(version=version)
        output.update({'name': package_name, 'version': version,})
        output.update(release.package_info)
    except (Package.DoesNotExist, Release.DoesNotExist):
        pass
    
    return XMLRPCResponse(params=(output,))

def search(request, spec, operator='or'):
    """
    search(spec[, operator])
    
    Search the package database using the indicated search spec.
    The spec may include any of the keywords described in the above list (except 'stable_version' and 'classifiers'), for example: {'description': 'spam'} will search description fields. Within the spec, a field's value can be a string or a list of strings (the values within the list are combined with an OR), for example: {'name': ['foo', 'bar']}. Valid keys for the spec dict are listed here. Invalid keys are ignored:
    name
    version
    author
    author_email
    maintainer
    maintainer_email
    home_page
    license
    summary
    description
    keywords
    platform
    download_url
    Arguments for different fields are combined using either "and" (the default) or "or". Example: search({'name': 'foo', 'description': 'bar'}, 'or'). The results are returned as a list of dicts {'name': package name, 'version': package release version, 'summary': package release summary}
    
    changelog(since)
    
    Retrieve a list of four-tuples (name, version, timestamp, action) since the given timestamp. All timestamps are UTC values. The argument is a UTC integer seconds since the epoch.
    """
    
    output = {
        'name': '',
        'version': '',
        'summary': '',
    }
    return XMLRPCResponse(params=(output,))

def changelog(since):
    output = {
        'name': '',
        'version': '',
        'timestamp': '',
        'action': '',
    }
    return XMLRPCResponse(params=(output,))

def ratings(request, name, version, since):
    return XMLRPCResponse(params=([],))
