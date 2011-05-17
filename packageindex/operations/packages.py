#-*- coding: utf-8 -*-
from packageindex.models import Package, Release, Distribution
import datetime
import pprint
import time
import xmlrpclib

PYPI_API_URL = 'http://pypi.python.org/pypi'
TIMEFORMAT = "%Y%m%dT%H:%M:%S"

def get_package(package, create=False):
    """
    returns a package or none if it does not exist. 
    """
    if isinstance(package, basestring):
        if create:
            package = Package.objects.get_or_create(name=package)[0]
        else:
            try:
                package = Package.objects.get(name=package)
            except Package.DoesNotExist:
                package = None
    return package

def update_package_list(url=None):
    client = xmlrpclib.ServerProxy(PYPI_API_URL)
    for package_name in client.list_packages():
        package, created = Package.objects.get_or_create(name=package_name)
        print package, created
#    pprint.pprint(client.list_packages())
#    pprint.pprint(client.package_releases('django-filer'))
#    pprint.pprint(client.package_urls('django-filer', '0.8.1'))
#    
#    pprint.pprint(client.package_releases('paramiko'))
#    pprint.pprint(client.package_urls('paramiko', '1.7.6'))

def update_packages(package_names=None):
    package_names = package_names or []
    for package_name in package_names:
        update_package(package_name)

def update_package(package, create=False, update_releases=True, 
                   update_distributions=True, mirror_distributions=False):
    package = get_package(package, create=create)
    print "updating %s" % package.name
    client = xmlrpclib.ServerProxy(PYPI_API_URL)
    if update_releases:
        for release in client.package_releases(package.name, True): # True-> show hidden
            release = create_or_update_release(
                            package, release, 
                            update_distributions=update_distributions, 
                            mirror_distributions=mirror_distributions)

def create_or_update_release(package, release, 
                             update_distributions=False, 
                             mirror_distributions=False):
    client = xmlrpclib.ServerProxy(PYPI_API_URL)
    package = get_package(package)
    if isinstance(release, basestring):
        if not len(release) <= 128:
            # TODO: more general validation and save to statistics
            print u'  "%s" is not  a valid version number!' % release
            return
        release, created = Release.objects.get_or_create(package=package, 
                                                         version=release)
    data = client.release_data(package.name, release.version)
    release.hidden = data.get('_pypi_hidden', False)
    for key, value in data.items():
        release.package_info[key] = value
    release.save()
    if update_distributions:
        for dist in client.release_urls(package.name, release.version):
#            pprint.pprint({'name': package.name, 'release': release.version, 'dist':dist})
            data = {
                'filename': dist['filename'],
                'md5_digest': dist['md5_digest'],
                'size': dist['size'],
                'url': dist['url'],
                'comment': dist['comment_text'],
            }
            try:
                data['uploaded_at'] = datetime.datetime.strptime(dist['upload_time'].value, TIMEFORMAT)
            except:
                pass
            distribution, created = Distribution.objects.get_or_create(
                                        release=release,
                                        filetype=dist['packagetype'],
                                        pyversion=dist['python_version'],
                                        defaults=data)
            if not created:
                # this means we have to update the existing record
                for key, value in data.items():
                    setattr(distribution, key, value)
            distribution.mirror_package(commit=False)
            distribution.save()

def process_changelog(since, update_releases=True, 
                      update_distributions=True, mirror_distributions=False):
    client = xmlrpclib.ServerProxy(PYPI_API_URL)
    timestamp = int(time.mktime(since.timetuple()))
    packages = {}
    for item in client.changelog(timestamp):
        packages[item[0]] = True
    print "packages that will be updated: %s" % (", ".join(packages.keys()),)
    for package in packages.keys():
        update_package(package, create=True,
                       update_releases=update_releases, 
                       update_distributions=update_distributions,
                       mirror_distributions=mirror_distributions)

def awesome_test():
    client = xmlrpclib.ServerProxy(PYPI_API_URL)
#    pprint.pprint(client.list_packages())
    pprint.pprint(client.package_releases('django-filer'))
    pprint.pprint(client.package_urls('django-filer', '0.8.2'))
    
    pprint.pprint(client.package_releases('Django'))
    pprint.pprint(client.package_urls('Django', '1.3'))
    
#    from pkgtools import pypi
#    print pypi
#    print pypi.real_name('django')