"""How the site finds its styling and script files on the live site.

Normally `collectstatic` prepares the files with version numbers in their names. If that step
didn't run, or a file is missing from it, the page links the plain file name instead of failing,
and WhiteNoise serves it straight from the code (WHITENOISE_USE_FINDERS in settings).
"""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name
