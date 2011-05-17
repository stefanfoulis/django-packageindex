from django.conf import settings

from packageindex.models import Package

if 'haystack' in settings.INSTALLED_APPS:
    from haystack import site
    from haystack.indexes import SearchIndex
    from haystack.fields import CharField, MultiValueField

    class PackageSearchIndex(SearchIndex):
        name = CharField(model_attr='name')
        text = CharField(document=True, use_template=True, null=True, stored=False,
                         template_name='packageindex/haystack/package_text.txt')
        author = MultiValueField(stored=False, null=True)
        classifier = MultiValueField(stored=False, null=True,
                                     model_attr='latest__classifiers')
        summary = CharField(stored=False, null=True,
                            model_attr='latest__summary')
        description = CharField(stored=False, null=True,
                                model_attr='latest__description')
        
        def prepare_author(self, obj):
            output = []
            for user in list(obj.owners.all()) + list(obj.maintainers.all()):
                output.append(user.get_full_name())
                if user.email:
                    output.append(user.email)
            if obj.latest:
                info = obj.latest.package_info
                for field in ('author','author_email', 'maintainer',
                    'maintainer_email',):
                    if info.get(field):
                        output.append(info.get(field))
            return output
    
    site.register(Package, PackageSearchIndex)
