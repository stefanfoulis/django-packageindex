from django.conf import settings
from django.core.urlresolvers import reverse
from django.forms.models import inlineformset_factory
from django.http import Http404
from django.views.generic import list_detail, create_update
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext

from packageindex import conf
from packageindex.decorators import user_maintains_package
from packageindex.models import Package, Release, Distribution
from packageindex.forms import ReleaseForm, DistributionUploadForm

def index(request, **kwargs):
    kwargs.setdefault('template_object_name', 'release')
    kwargs.setdefault('queryset', Release.objects.filter(hidden=False))
    return list_detail.object_list(request, **kwargs)

def details(request, package, version, **kwargs):
    release = get_object_or_404(Package, name=package).get_release(version)

    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))

    kwargs.setdefault('template_object_name', 'release')
    kwargs.setdefault('template_name', 'packageindex/release_detail.html')
    kwargs.setdefault('extra_context', {})
    kwargs.setdefault('mimetype', settings.DEFAULT_CONTENT_TYPE)

    kwargs['extra_context'][kwargs['template_object_name']] = release

    return render_to_response(kwargs['template_name'], kwargs['extra_context'],
                              context_instance=RequestContext(request),
                              mimetype=kwargs['mimetype'])

def doap(request, package, version, **kwargs):
    kwargs.setdefault('template_name', 'packageindex/release_doap.xml')
    kwargs.setdefault('mimetype', 'text/xml')
    return details(request, package, version, **kwargs)

@user_maintains_package()
def manage(request, package, version, **kwargs):
    release = get_object_or_404(Package, name=package).get_release(version)

    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))

    kwargs['object_id'] = release.pk

    kwargs.setdefault('form_class', ReleaseForm)
    kwargs.setdefault('template_name', 'packageindex/release_manage.html')
    kwargs.setdefault('template_object_name', 'release')

    return create_update.update_object(request, **kwargs)

@user_maintains_package()
def manage_metadata(request, package, version, **kwargs):
    kwargs.setdefault('template_name', 'packageindex/release_manage.html')
    kwargs.setdefault('template_object_name', 'release')
    kwargs.setdefault('extra_context', {})
    kwargs.setdefault('mimetype', settings.DEFAULT_CONTENT_TYPE)

    release = get_object_or_404(Package, name=package).get_release(version)

    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))

    if not release.metadata_version in conf.METADATA_FORMS:
        #TODO: Need to change this to a more meaningful error
        raise Http404('Metadata Version is not supported')

    kwargs['extra_context'][kwargs['template_object_name']] = release

    form_class = conf.METADATA_FORMS[release.metadata_version]
    if isinstance(form_class, basestring):
        app_module, class_name = form_class.rsplit('.', 1)
        form_class = getattr(__import__(app_module, {}, {}, [class_name]), class_name)
        conf.METADATA_FORMS[release.metadata_version] = form_class

    initial = {}
    multivalue = ('classifier',)

    for key, values in release.package_info.iterlists():
        if key in multivalue:
            initial[key] = values
        else:
            initial[key] = '\n'.join(values)

    if request.method == 'POST':
        form = form_class(data=request.POST, initial=initial)

        if form.is_valid():
            for key, value in form.cleaned_data.iteritems():
                if isinstance(value, basestring):
                    release.package_info[key] = value
                elif hasattr(value, '__iter__'):
                    release.package_info.setlist(key, list(value))

            release.save()
            return create_update.redirect(kwargs.get('post_save_redirect', None),
                                          release)
    else:
        form = form_class(initial=initial)

    kwargs['extra_context']['form'] = form

    return render_to_response(kwargs['template_name'], kwargs['extra_context'],
                              context_instance=RequestContext(request),
                              mimetype=kwargs['mimetype'])

@user_maintains_package()
def manage_files(request, package, version, **kwargs):
    release = get_object_or_404(Package, name=package).get_release(version)

    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))

    kwargs.setdefault('formset_factory_kwargs', {})
    kwargs['formset_factory_kwargs'].setdefault('fields', ('comment',))
    kwargs['formset_factory_kwargs']['extra'] = 0

    kwargs.setdefault('formset_factory', inlineformset_factory(Release, Distribution, **kwargs['formset_factory_kwargs']))
    kwargs.setdefault('template_name', 'packageindex/release_manage_files.html')
    kwargs.setdefault('template_object_name', 'release')
    kwargs.setdefault('extra_context', {})
    kwargs.setdefault('mimetype', settings.DEFAULT_CONTENT_TYPE)
    kwargs['extra_context'][kwargs['template_object_name']] = release
    kwargs.setdefault('formset_kwargs', {})
    kwargs['formset_kwargs']['instance'] = release
    kwargs.setdefault('upload_form_factory', DistributionUploadForm)

    if request.method == 'POST':
        formset = kwargs['formset_factory'](data=request.POST,
                                            files=request.FILES,
                                            **kwargs['formset_kwargs'])
        if formset.is_valid():
            formset.save()
            formset = kwargs['formset_factory'](**kwargs['formset_kwargs'])
    else:
        formset = kwargs['formset_factory'](**kwargs['formset_kwargs'])

    kwargs['extra_context']['formset'] = formset
    kwargs['extra_context'].setdefault('upload_form',
                                       kwargs['upload_form_factory']())

    return render_to_response(kwargs['template_name'], kwargs['extra_context'],
                              context_instance=RequestContext(request),
                              mimetype=kwargs['mimetype'])

@user_maintains_package()
def upload_file(request, package, version, **kwargs):
    release = get_object_or_404(Package, name=package).get_release(version)

    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))

    kwargs.setdefault('form_factory', DistributionUploadForm)
    kwargs.setdefault('post_save_redirect', reverse('packageindex-release-manage-files',
                                                    kwargs={'package': package,
                                                            'version': version}))
    kwargs.setdefault('template_name', 'packageindex/release_upload_file.html')
    kwargs.setdefault('template_object_name', 'release')
    kwargs.setdefault('extra_context', {})
    kwargs.setdefault('mimetype', settings.DEFAULT_CONTENT_TYPE)
    kwargs['extra_context'][kwargs['template_object_name']] = release

    if request.method == 'POST':
        form = kwargs['form_factory'](data=request.POST, files=request.FILES)
        if form.is_valid():
            dist = form.save(commit=False)
            dist.release = release
            dist.uploader = request.user
            dist.save()

            return create_update.redirect(kwargs.get('post_save_redirect'),
                                          release)
    else:
        form = kwargs['form_factory']()

    kwargs['extra_context']['form'] = form

    return render_to_response(kwargs['template_name'], kwargs['extra_context'],
                              context_instance=RequestContext(request),
                              mimetype=kwargs['mimetype'])
