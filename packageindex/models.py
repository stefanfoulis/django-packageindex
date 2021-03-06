import os
import xmlrpclib
from setuptools.package_index import distros_for_filename, distros_for_url
from z3c.pypimirror import mirror
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.utils import simplejson as json
from django.utils.datastructures import MultiValueDict
from django.utils.translation import ugettext_lazy as _
from z3c.pypimirror.mirror import PackageError
from packageindex import conf
import datetime
import time
import urllib2

PYPI_API_URL = 'http://pypi.python.org/pypi'
PYPI_SIMPLE_URL = 'http://pypi.python.org/simple'
MIRROR_FILETYPES = ['*.zip', '*.tgz', '*.egg', '*.tar.gz', '*.tar.bz2']

class PackageInfoField(models.Field):
    description = u'Python Package Information Field'
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        kwargs['editable'] = False
        super(PackageInfoField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, basestring):
            if value:
                return MultiValueDict(json.loads(value))
            else:
                return MultiValueDict()
        if isinstance(value, dict):
            return MultiValueDict(value)
        if isinstance(value, MultiValueDict):
            return value
        raise ValueError('Unexpected value encountered when converting data to python')

    def get_prep_value(self, value):
        if isinstance(value, MultiValueDict):
            return json.dumps(dict(value.iterlists()))
        if isinstance(value, dict):
            return json.dumps(value)
        if isinstance(value, basestring) or value is None:
            return value
        raise ValueError('Unexpected value encountered when preparing for database')

    def get_internal_type(self):
        return 'TextField'

class Classifier(models.Model):
    name = models.CharField(max_length=255, primary_key=True)

    class Meta:
        verbose_name = _(u"classifier")
        verbose_name_plural = _(u"classifiers")
        ordering = ('name',)

    def __unicode__(self):
        return self.name


class PackageIndexManager(models.Manager):
    pass


class PackageIndex(models.Model):
    slug = models.CharField(max_length=255, unique=True, default='pypi')
    updated_from_remote_at = models.DateTimeField(null=True, blank=True)
    xml_rpc_url = models.URLField(blank=True, verify_exists=False, default=PYPI_API_URL)
    simple_url = models.URLField(blank=True, verify_exists=False, default=PYPI_SIMPLE_URL)

    objects = PackageIndexManager()

    class Meta:
        verbose_name_plural = 'package indexes'

    def __unicode__(self):
        return self.slug

    @property
    def client(self):
        if not hasattr(self, '_client'):
            self._client = xmlrpclib.ServerProxy(self.xml_rpc_url)
        return self._client
    
    def update_package_list(self, since=None, full=False):
        now = datetime.datetime.now()
        since = since or self.updated_from_remote_at
        if since and not full:
            timestamp = int(time.mktime(since.timetuple()))
            packages = set([item[0] for item in self.client.changelog(timestamp)])
        else:
            packages = self.client.list_packages()
        for package_name in packages:
            package, created = Package.objects.get_or_create(index=self, name=package_name, defaults={'updated_from_remote_at': now})
            print package, created
            package.update_release_metadata(update_distribution_metadata=True)
        self.updated_from_remote_at = now
        self.save()



class Package(models.Model):
    index = models.ForeignKey(PackageIndex)
    name = models.CharField(max_length=255, unique=True, primary_key=True)
    auto_hide = models.BooleanField(default=True, blank=False)
    updated_from_remote_at = models.DateTimeField(null=True, blank=True)
    parsed_external_links_at = models.DateTimeField(null=True, blank=True)


    class Meta:
        verbose_name = _(u"package")
        verbose_name_plural = _(u"packages")
        get_latest_by = "releases__latest"
        ordering = ['name', ]

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('packageindex-package', (), {'package': self.name})

    @property
    def latest(self):
        try:
            return self.releases.latest()
        except Release.DoesNotExist:
            return None

    def get_release(self, version):
        """Return the release object for version, or None"""
        try:
            return self.releases.get(version=version)
        except Release.DoesNotExist:
            return None

    def update_release_metadata(self, update_distribution_metadata=True):
        now = datetime.datetime.now()
        try:
            name = self.name.encode('ascii')
        except UnicodeEncodeError:
            print "illegal package name!"
            return 
        for release_string in self.index.client.package_releases(self.name, True): # True -> show hidden
            data = self.index.client.release_data(self.name, release_string)
            kwargs = {
                'hidden': data.get('_pypi_hidden', False),
                'package_info': MultiValueDict(),
                'is_from_external': False,
            }
            for key, value in data.items():
                kwargs['package_info'][key] = value
            release, created = Release.objects.get_or_create(package=self, version=release_string, defaults=kwargs)
            if not created:
                for key, value in kwargs.items():
                    setattr(release, key, value)
                release.save()
            if update_distribution_metadata:
                release.update_distribution_metatdata()
        self.updated_from_remote_at = now
        self.save()

    def update_external_release_metadata(self, update_distribution_metadata=True):
        try:
            name = self.name.encode('ascii')
        except UnicodeEncodeError:
            print "illegal package name!"
            return
        mpackage = mirror.Package(package_name=name,
                                  pypi_base_url=self.index.simple_url)
        try:
            files = mpackage.ls(filename_matches='*', external_links=True, follow_external_index_pages=True)
        except (PackageError,), e:
            print type(e), e
            files = []
        for (dist_url, file_name, md5sum) in files:
            if dist_url.startswith('../../'):
                # Ignore relative urls, as they are files hosted on pypi and have already been fetched over the xml-rpc
                # api
                continue
            i = 1
            for dist in distros_for_url(dist_url):
                if not dist.project_name == self.name or not dist.version:
                    continue
                release = Release.objects.get_or_create(package=self,
                                                        version=dist.version,
                                                        defaults={'is_from_external': True})[0]
                pyversion = dist.py_version or 'any'
                f, ext = os.path.splitext(file_name)
                if ext.startswith('.egg'):
                    filetype = 'bdist_egg'
                elif ext in ('.exe',):
                    filetype = 'bdist_wininst'
                elif ext in ('.dmg', '.pgk'):
                    filetype = 'bdist_dmg'
                elif ext in ('.rpm',):
                    filetype = 'bdist_rpm'
                elif ext in ('.tar.gz', '.zip', '.bz2'):
                    filetype = 'sdist'
                else:
                    continue
                defaults = {
                    'filename': file_name,
                    'url': dist_url,
                    'is_from_external': True
                }
                distribution = Distribution.objects.get_or_create(
                    release=release, pyversion=pyversion, filetype=filetype,
                    defaults=defaults
                )[0]
                if distribution.is_from_external and not distribution.file:
                    # we only overwrite the url if the package has not been mirrored yet and it is not a real pypi
                    # hosted package
                    distribution.filename = file_name
                    distribution.url = dist_url
                    distribution.save()

                print i, dist.project_name, dist.py_version, dist.version, distribution
                i += 1
        self.parsed_external_links_at = datetime.datetime.now()
        self.save()





class Release(models.Model):
    package = models.ForeignKey(Package, related_name="releases")
    version = models.CharField(max_length=128)
    metadata_version = models.CharField(max_length=64, default='1.0')
    package_info = PackageInfoField(blank=False)
    hidden = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    is_from_external = models.BooleanField(default=False)

    class Meta:
        verbose_name = _(u"release")
        verbose_name_plural = _(u"releases")
        unique_together = ("package", "version")
        get_latest_by = 'created'
        ordering = ['-created']

    def __unicode__(self):
        return self.release_name

    @property
    def release_name(self):
        return u"%s-%s" % (self.package.name, self.version)

    @property
    def summary(self):
        return self.package_info.get('summary', u'')

    @property
    def description(self):
        return self.package_info.get('description', u'')

    @property
    def classifiers(self):
        return self.package_info.getlist('classifier')

    @models.permalink
    def get_absolute_url(self):
        return ('packageindex-release', (), {'package': self.package.name,
                                           'version': self.version})

    def update_distribution_metatdata(self):
        for dist in self.package.index.client.release_urls(self.package.name, self.version):
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
                                        release=self,
                                        filetype=dist['packagetype'],
                                        pyversion=dist['python_version'],
                                        defaults=data)
            if not created:
                # this means we have to update the existing record
                for key, value in data.items():
                    setattr(distribution, key, value)
                distribution.save()

class Distribution(models.Model):
    release = models.ForeignKey(Release, related_name="distributions")
    filename = models.CharField(blank=True, default='', max_length=255,
                                help_text="the filename as provided by pypi")
    file = models.FileField(upload_to=conf.RELEASE_UPLOAD_TO,
                            null=True, blank=True,
                            help_text='the distribution file (if it was mirrord locally)',
                            max_length=255)
    url = models.URLField(verify_exists=False, null=True, blank=True,
                          help_text='the original url provided by pypi',
                            max_length=255)
    size = models.IntegerField(null=True, blank=True)
    md5_digest = models.CharField(max_length=32, blank=True)
    filetype = models.CharField(max_length=32, blank=False,
                                choices=conf.DIST_FILE_TYPES)
    pyversion = models.CharField(max_length=16, blank=True,
                                 choices=conf.PYTHON_VERSIONS)
    comment = models.TextField(blank=True, default='')
    signature = models.TextField(blank=True, default='')

    uploaded_at = models.DateTimeField(null=True, blank=True,
                                       help_text='the time at which the package was uploaded (on pypi)')
    mirrored_at = models.DateTimeField(null=True, blank=True,
                                       help_text='the time at which the package was downloaded to this mirror.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_from_external = models.BooleanField(default=False)


    class Meta:
        verbose_name = _(u"distribution")
        verbose_name_plural = _(u"distributions")
        unique_together = ("release", "filetype", "pyversion")

    def __unicode__(self):
        return self.filename

    def get_absolute_url(self):
        return "%s#md5=%s" % (self.path, self.md5_digest)

    @property
    def display_filetype(self):
        for key, value in conf.DIST_FILE_TYPES:
            if key == self.filetype:
                return value
        return self.filetype

    @property
    def path(self):
        if self.file:
            return self.file.url
        else:
            return self.url
    
    @property
    def is_hosted_locally(self):
        if self.file:
            return True
        else:
            return False
    
    def mirror_package(self, overwrite=False, commit=True):
        if not overwrite and self.file:
            # file already downloaded. do nothing
            print u"already downloaded %s" % self.file
            return
        needs_save = False
#        # try to find the package in my existing local mirror location
#        EXISTING_MIRROR = '/Users/stefanfoulis/Coding/mirrors/mypypi/files/'
#        maybe = os.path.abspath(os.path.join(EXISTING_MIRROR,
#                                             self.release.package.name,
#                                             self.filename))
#        if os.path.exists(maybe):
#            # yay! we already have the file!
#            if False:
#                # copy the file
#                self.file = UploadedFile(name=maybe)
#            else:
#                # hardlink the file
#                print "   hardlinking to '%s'" % maybe
#                path = conf.RELEASE_UPLOAD_TO(instance=self, filename=self.filename)
#                fullpath = os.path.join(settings.MEDIA_ROOT, path)
#                if not os.path.exists(os.path.dirname(fullpath)):
#                    os.makedirs(os.path.dirname(fullpath))
#                if not os.path.exists(fullpath):
#                    os.link(maybe, fullpath)
#                self.file = path
#            self.mirrored_at = datetime.datetime.now()
#            needs_save = True
        if self.url:
            print "   downloading from '%s'" % self.url
            try:
                self.file = SimpleUploadedFile(
                                name=self.filename,
                                content=urllib2.urlopen(self.url).read())
                self.mirrored_at = datetime.datetime.now()
                needs_save = True
            except (urllib2.HTTPError, urllib2.URLError, ValueError), e:
                print u"      failed! %s (%s)" % (e, type(e),)
                
        if needs_save and commit:
            self.save()
    mirror_package.alters_data = True


try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ["^packageindex\.models\.PackageInfoField"])
except ImportError:
    pass
