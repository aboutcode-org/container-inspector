Changelog
=========

v21.4.26 (2021-04-26)
--------------------

This is a minor release. There is no API change

- Add new find_root function to find the root of a filesystem
- Add new minor tests for extra distro


v21.3.3 (2021-03-03)
--------------------

This is a major release.

- Drop support for Python 2. The minimum Python version is now Python 3.6
- Drop support for Docker imgae v1-style format
- Add new tests for distro


v3.1.1 (2020-07-07)
-------------------

This is a major release that has been significantly reworked
and is non-compatible with any previous versions.

 * Remove dependency on extractcode. Use the tarfile module instead.
 * Remove code and command line option to use truncate image and layer ids.
 * Remove support for v1.0 image layouts
 * Refactor all the API for simplicity


v2.0.0
------

 * Initial release.
