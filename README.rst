========================
container-inspector
========================

**container-inspector** is a suite of analysis utilities and command line tools
for Docker images, containers, root filesystems and virtual machine images.

For Docker images, it can process layers and how these relate to each other as
well as Dockerfiles.
 
**container-inspector** provides utilities to:

 - identify Docker images in a file system, its layers and the related metadata.
 - given a Docker image, collect and report its metadata.
 - given a Docker image, extract the layers used to rebuild what how a runtime
   rootfs would look.
 - find and parse Dockerfiles.
 - find how Dockerfiles relate to actual images and their layers.
 - given a Docker image, rootfs or Virtual Machime image collect inventories of
   packages and files installed in an image or layer or rootfs
   (implemented using a provided callable)
 - detect the "distro" of a rootfs of image using os-release files (and an
   extensive test suite for these)
 - detect the operating system, architecture and 


Quick start
-----------

- Only runs on POSIX OSes
- Get Python 3.6+
- Check out a clone or download of container-inspector, then run: `./configure --dev`.
- Then run `env/bin/container-inspector -h` for help.

 
Container image formats
-----------------------

container-inspector handles the formats of Docker images as created by the
`docker save` command. There are three versions for this Docker image format. 
The latest v1.2 is a minor update to v1.1.

- v1.1 provides improved and richer metadata over v1.0 with a top level manifest.json
  file and a Config file for each image with full layer history and ordeing. It also
  use checksum for enhanced security and traceability of images and layers.

- v1.0 uses a simple `repositories` meta file and requires infering the ordering of
  the layers in an image based on each individual layer `json` meta file. This
  format is no longer support in the latest version of container-inspector.

- All V1.x formats use the same storage format for layers e.g the layer format V1.0
  where each layer is stored in a sub-directories named after the layer id. 
  Each of this directories contains a "layer.tar" tarball with the layer payload, 
  a "json" JSON metadata file describing the layer and a "VERSION" file describing
  the layer format version. Each tarball represents a slice or diff of the image
  root file system using the AUFS conventions.

At runtime, in a sequence of layers of an image, each root filesystem slice of a 
layer is "layered" on top of each other from the root bottom layer to the latest
layer (or selected tagged layer) using a union file system (e.g. AUFS).
In AUFS, any file or directory prefixed with .wh. are "white outs" files deleting
files in the underlying layers.

See the image specifications saved in docs/references/


Internal data model
-------------------
- Image: this is a runnable image composed of metadata and a sequence of layers.
- Layer: this is a slice of an image root filesystem with a payload and metadata
- Resource: this a file or directory


Plans
-----
 - in progress: support OCI image layout
 - improved suport for Windows containers


Related tools
-------------
 - Fetching Image from remote registry is available in ScanCode.io
 - Extracting VM Image filesystems as archives is available in ExtractCode
 - Scanning for application and system packages is available in ScanCode Toolkit

