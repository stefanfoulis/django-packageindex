django-packageindex
===================


.. Warning::
   this is work in progress. django-packageindex was forked from djangopypi and
   received some model changes. Its main focus right now is on mirroring pypi
   (in contrast to djangopypis goal of providing a custom pypi).
   In the process some standard pypi mechanisms (e.g package upload from 
   the commandline) may have broken. That functionality will be restored in the
   future.
   As of now this code is highly experimental and is likely to brake all over
   the place.


django-packageindex is a Django application that provides a re-implementation of the 
`Python Package Index <http://pypi.python.org>`_.
It has various modes to mirror pypi.
