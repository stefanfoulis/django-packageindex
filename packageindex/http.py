from django.http import HttpResponse, QueryDict
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.utils.datastructures import MultiValueDict
from django.contrib.auth import authenticate


class HttpResponseNotImplemented(HttpResponse):
    status_code = 501


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401

    def __init__(self, realm):
        HttpResponse.__init__(self)
        self['WWW-Authenticate'] = 'Basic realm="%s"' % realm


def parse_distutils_request(request):
    """ This is being used because the built in request parser that Django uses,
    django.http.multipartparser.MultiPartParser is interperting the POST data
    incorrectly and/or the post data coming from distutils is invalid.
    
    One portion of this is the end marker: \r\n\r\n (what Django expects) 
    versus \n\n (what distutils is sending). 
    """
    
    try:
        sep = request.raw_post_data.splitlines()[1]
    except:
        raise ValueError('Invalid post data')
    
    
    request.POST = QueryDict('',mutable=True)
    try:
        request._files = MultiValueDict()
    except Exception, e:
        pass
    
    for part in filter(lambda e: e.strip(), request.raw_post_data.split(sep)):
        try:
            header, content = part.lstrip().split('\n',1)
        except Exception, e:
            continue
        
        if content.startswith('\n'):
            content = content[1:]
        
        if content.endswith('\n'):
            content = content[:-1]
        
        headers = parse_header(header)
        
        if "name" not in headers:
            continue
        
        if "filename" in headers:
            dist = TemporaryUploadedFile(name=headers["filename"],
                                         size=len(content),
                                         content_type="application/gzip",
                                         charset='utf-8')
            dist.write(content)
            dist.seek(0)
            request.FILES.appendlist(headers['name'], dist)
        else:
            request.POST.appendlist(headers["name"],content)
    return

def parse_header(header):
    headers = {}
    for kvpair in filter(lambda p: p,
                         map(lambda p: p.strip(),
                             header.split(';'))):
        try:
            key, value = kvpair.split("=",1)
        except ValueError:
            continue
        headers[key.strip()] = value.strip('"')
    
    return headers
    

def login_basic_auth(request):
    authentication = request.META.get("HTTP_AUTHORIZATION")
    if not authentication:
        return
    (authmeth, auth) = authentication.split(' ', 1)
    if authmeth.lower() != "basic":
        return
    auth = auth.strip().decode("base64")
    username, password = auth.split(":", 1)
    return authenticate(username=username, password=password)
