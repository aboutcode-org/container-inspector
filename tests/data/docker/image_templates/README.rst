These are test images created and exported in images.tar this way:

```
$ cat layer.tar | docker import -m "initial import" - me/test_image_tar:1.0 
sha256:4d955704d3bfe618753e3f969db87e2b60dd4206132a701f23de1dfe0325664e

$ docker image ls
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
me/test_image_tar   1.0                 4d955704d3bf        7 seconds ago       142 B

$ docker build  --label "Some label" -t "you/secondimage:1.2" --file Dockerfile.from_tar .
Sending build context to Docker daemon 8.192 kB
Step 1/4 : FROM me/test_image_tar:1.0
 ---> 4d955704d3bf
Step 2/4 : MAINTAINER Me Myself and I.
 ---> Running in 6272bde354c2
 ---> f75ca9480d6b
Removing intermediate container 6272bde354c2
Step 3/4 : ADD hello /
 ---> 4a2081571b18
Removing intermediate container d1756dee35e8
Step 4/4 : LABEL "Some label" ''
 ---> Running in 721d16a40a4c
 ---> 12372b2d7bc1
Removing intermediate container 721d16a40a4c
Successfully built 12372b2d7bc1

$ docker image ls
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
you/secondimage     1.2                 12372b2d7bc1        33 seconds ago      143 B
me/test_image_tar   1.0                 4d955704d3bf        7 minutes ago       142 B


$ docker build  --label "Some other label" -t "she/image_from_scratch:1.0" --file Dockerfile.scratch .
Sending build context to Docker daemon 9.216 kB
Step 1/4 : FROM scratch
 ---> 
Step 2/4 : MAINTAINER You Myself and I.
 ---> Running in e257e8a2015a
 ---> c9850cfdfb0e
Removing intermediate container e257e8a2015a
Step 3/4 : ADD hello /
 ---> 3d2acbdb6119
Removing intermediate container 1b8b1a036b99
Step 4/4 : LABEL "Some other label" ''
 ---> Running in e5addbed082b
 ---> c1edec6e1f0a
Removing intermediate container e5addbed082b
Successfully built c1edec6e1f0a

$ docker image ls
REPOSITORY               TAG                 IMAGE ID            CREATED              SIZE
she/image_from_scratch   1.0                 c1edec6e1f0a        19 seconds ago       1 B
you/secondimage          1.2                 12372b2d7bc1        About a minute ago   143 B
me/test_image_tar        1.0                 4d955704d3bf        8 minutes ago        142 B

$ docker save she/image_from_scratch you/secondimage me/test_image_tar > imagesv11.tar
```
