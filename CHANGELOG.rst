Changelog
=========

v31.1.0
--------

This is a minor release with minor updates.

- ``utils.extract_tar`` now returns a list of error messages that occured during
  extraction.
- Add tests for ``utils.extract_tar``


v31.0.0
--------

This is a major release with bug fixes and API changes.

- Remove dependency on extractcode as images only need basic tar to extract.
  - "utils.extract_tar" function now accepts a skip_symlink argument
- Adopt the latest skeleton.
- Add new os-release tests


v30.0.0
--------

This is a minor release with bug fixes and minor updates.

- Switched back to semver from calver like other AboutCode projects.
- Adopted the latest skeleton. With this the virtualenv is created under venv.
- Add new "layer_path_segments" argument to image.Image.to_dict() to allow
  to report the Layer extracted locations as trimmed paths keeping only this
  many trailing path segments.


v21.6.10
--------

This is a minor release with bug fixes.

v21.6.4
--------

This is a minor release with bug fixes and minor API changes.

API changes
~~~~~~~~~~~

The Distro.from_rootfs() now works as expected. It can handle empty location
and works correctly with a base_distro. When a base_distro is provided it
will raise an Exception if the found Distro.os does not match the base Distro.os


v21.5.25
--------

This is a major release.

API changes
~~~~~~~~~~~

The Image and Layer object structures have changed significantly:
- legacy parent_id and parent_digest attributes are removed from Image

- new attributes have been added to correctly track the tarball of an image
  or layer and its extracted location:

  - "extracted_location" is the absolute path where an image or layer is extracted
  - "archive_location" is the absolute path to an image or layer archive

  Therefore we have these attribute renames, additions and deletions:
    - Image.base_location -> Image.extracted_location
    - Image.archive_location: added
    - Layer.extracted_to_location -> Layer.extracted_location
    - Layer.layer_location -> Layer.archive_location
    - Layer.layer_sha256 -> Layer.sha256

  Also:
    - Layer.layer_id is now the sha256 of the Layer archive
    - Image.sha256, os_version, variant: added

- the layer_id is now based on the SHA256 of the layer tarball and not based on
  the UUID-like directory names that contain a "layer.tar" in Docker image.
- Image.config_digest is now prefixed with "sha256:"
- All mappings keys are now lowercased recursively, including for labels.

- Dropped support for Python 2. The minimum Python version is now Python 3.6
- Dropped support for Docker image v1-style format
- Dropped support for Windows as it was never intended to run on Windows.
  Windows as a container is a target though.
- The way Image and Layers archives are extracted has changed significantly.
  Images are extracted as before keeping symlinks (which are essential to support
  certain Docker image layouts). In contrast, Layers are now exracted using
  extractcode and links are ignored.


New features
~~~~~~~~~~~~

- Add new find_root function to find the root of a filesystem

- Add new tests for distro detection and os-release handling using a large
  collection of os-release files

- Layer/Image.to_dict() now accepts a new "exclude_fields" argument with a list
  of field names to optionally exclude.

- Add experimental support for container images using the OCI layout and add a
  new Image attribute "image_format" with the value "docker" or "oci"

- Add experimental support for Windows-based containers.


Misc
~~~~

- The experimental fetch module has been removed
- The master branch has been renamed to main.



v3.1.2 (2020-07-07)
-------------------

Minor packageing fix release.


v3.1.1 (2020-07-07)
-------------------

This is a major release that has been significantly reworked
and is non-compatible with any previous versions.

- Remove dependency on extractcode. Use the tarfile module instead.
- Remove code and command line option to use truncate image and layer ids.
- Remove support for v1.0 image layouts
- Refactor all the API for simplicity


v2.0.0
------

- Initial release.
