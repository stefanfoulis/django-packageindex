from django.contrib import admin
from packageindex.models import Package, Release, Classifier, \
                              Distribution

class PackageReleaseInline(admin.TabularInline):
    model = Release
    extra = 0
    fields = ('version', 'metadata_version', 'hidden',)
    readonly_fields = ('version', 'metadata_version', 'hidden',)

class PackageAdmin(admin.ModelAdmin):
    list_display = ('__unicode__',)
    search_fields = ('name',)
    inlines = (PackageReleaseInline,)

class ReleaseAdmin(admin.ModelAdmin):
    list_display = ('package', 'version', 'hidden',)
    search_fields = ('package__name', 'version',)
    list_filter = ('hidden', )
    raw_id_fields = ('package',)

class DistributionAdmin(admin.ModelAdmin):
    list_display = ('package_name', 'release_version', 'is_hosted_locally', 'path')
    search_fields = ('release__package__name', 'release__version', 'comment',)
    raw_id_fields = ('release',)
    
    def package_name(self, obj):
        return obj.release.package.name
    package_name.admin_order_field = 'release__package__name'
    
    def release_version(self, obj):
        return obj.release.version
    release_version.admin_order_field = 'release__version'
    
    def is_hosted_locally(self, obj):
        return obj.is_hosted_locally
    is_hosted_locally.boolean = True
    is_hosted_locally.admin_order_field = 'file'

admin.site.register(Package, PackageAdmin)
admin.site.register(Release, ReleaseAdmin)
admin.site.register(Distribution, DistributionAdmin)
admin.site.register(Classifier)
