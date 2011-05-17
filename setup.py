import os
from setuptools import setup, find_packages

def fread(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

version = '0.1.0'

setup(
    name='django-packageindex',
    version=version,
    description="A Django application that emulates the Python Package Index.",
    long_description="it does stuff",
    classifiers=[
        "Framework :: Django",
        "Development Status :: 4 - Beta",
        #"Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "Environment :: Web Environment",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Topic :: System :: Software Distribution",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords='django pypi packaging index',
    author='Stefan Foulis',
    author_email='stefan@foulis.ch',
    maintainer='Stefan Foulis',
    maintainer_email='stefan@foulis.ch',
    url='http://github.com/stefanfoulis/django-packageindex',
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'setuptools',
        'docutils',
    ],
)
