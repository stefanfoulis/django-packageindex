from django.conf import settings
from django.core.files.uploadedfile import UploadedFile, SimpleUploadedFile
from django.db import models
from django.utils import simplejson as json
from django.utils.datastructures import MultiValueDict
from django.utils.translation import ugettext_lazy as _
from packageindex import conf
import datetime
import os
import urllib2


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

class Package(models.Model):
    name = models.CharField(max_length=255, unique=True, primary_key=True)
    auto_hide = models.BooleanField(default=True, blank=False)

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

class Release(models.Model):
    package = models.ForeignKey(Package, related_name="releases")
    version = models.CharField(max_length=128)
    metadata_version = models.CharField(max_length=64, default='1.0')
    package_info = PackageInfoField(blank=False)
    hidden = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

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
#    md5_checked_at = models.DateTimeField(null=True, blank=True,
#                                       help_text='the time at which the md5 sum of the local file was last checked.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    
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
            return
        needs_save = False
        # try to find the package in my existing local mirror location
        EXISTING_MIRROR = '/Users/stefanfoulis/Coding/mirrors/mypypi/files/'
        maybe = os.path.abspath(os.path.join(EXISTING_MIRROR,
                                             self.release.package.name,
                                             self.filename))
        if os.path.exists(maybe):
            # yay! we already have the file!
            if False:
                # copy the file
                self.file = UploadedFile(name=maybe)
            else:
                # hardlink the file
                print "   hardlinking to '%s'" % maybe
                path = conf.RELEASE_UPLOAD_TO(instance=self, filename=self.filename)
                fullpath = os.path.join(settings.MEDIA_ROOT, path)
                if not os.path.exists(os.path.dirname(fullpath)):
                    os.makedirs(os.path.dirname(fullpath))
                if not os.path.exists(fullpath):
                    os.link(maybe, fullpath)
                self.file = path
            self.mirrored_at = datetime.datetime.now()
            needs_save = True
        elif self.url:
            print "   downloading from '%s'" % self.url
            try:
                self.file = SimpleUploadedFile(
                                name=self.filename,
                                content=urllib2.urlopen(self.url).read())
                needs_save = True
            except urllib2.HTTPError, e:
                print "      failed! %s" % e
                
        if needs_save and commit:
            self.save()
    mirror_package.alters_data = True


try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ["^packageindex\.models\.PackageInfoField"])
except ImportError:
    pass
