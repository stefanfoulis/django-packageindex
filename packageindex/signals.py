from django.db.models import signals
from django.utils.hashcompat import md5_constructor

from packageindex.models import Package, Release, Distribution

def autohide_new_release_handler(sender, instance, created, *args, **kwargs):
    """ Autohide other releases on the creation of a new release when the 
    package 'auto-hide' is True"""
    if not created or not instance.package.auto_hide:
        return
    
    for release in instance.package.releases.exclude(pk=instance.pk).filter(hidden=False):
        release.hidden = True
        release.save()
    
    if instance.hidden:
        instance.hidden = False
        instance.save()

def autohide_save_release_handler(sender, instance, *args, **kwargs):
    """ When saving a release, check to see if it should be hidden or not """
    if instance.pk is None:
        return
    
    if not instance.package.auto_hide:
        return
    
    try:
        latest = instance.package.releases.latest('created')
    except Release.DoesNotExist:
        return
    
    if instance != latest and not instance.hidden:
        instance.hidden = True

def autohide_save_package_handler(sender, instance, *args, **kwargs):
    if not instance.auto_hide:
        return
    
    for release in instance.releases.filter(hidden=False):
        release.save()

def distribution_hash(sender, instance, *args, **kwargs):
    if not instance.md5_digest and instance.content:
        digest = md5_constructor()
        try:
            fh = instance.content.storage.open(instance.content.name)
            map(digest.update,fh.readlines())
            fh.close()
            instance.md5_digest = digest.hexdigest()
            instance.save()
        except Exception, e:
            print str(e)

signals.post_save.connect(autohide_new_release_handler, sender=Release)
signals.pre_save.connect(autohide_save_release_handler, sender=Release)
signals.pre_save.connect(autohide_save_package_handler, sender=Package)
signals.post_save.connect(distribution_hash, sender=Distribution)
