"""
Management command for loading all the known packages from the official
pypi.
"""

from django.core.management.base import BaseCommand
from packageindex.models import Package
from packageindex.operations.packages import awesome_test

class Command(BaseCommand):
    args = '<package_name package_name ...>'
    help = """Update the package index (packages only. no releases.)"""
    def handle(self, *args, **options):
        awesome_test()
