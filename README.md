Apomixis
========

Apomixis is a distributed image and thumbnail server.

History/Motivation
------------------

When building web applications that allow users to upload images, one
faces a number of challenges. 

A naive approach is to allow the users to upload the image file, dump
it into a directory on the same server as the web-server, and the
provide a way to access the uploaded image via a URL. Almost
immediately, you will realize that users can and will upload images of
any size and you can't just serve the full-size images. You will
almost certainly want to scale the images down to reasonable web
size. Probably even more than one size, as it's common to have a
medium sized view of the image as well as small thumbnails for index
pages. A typical response to this is to, when accepting the upload,
use Imagemagick, PIL or something similar to create a couple scaled
versions of the images and save those alongside the original
image. This may be good enough for many applications. In my experience
though, I run into trouble when the design of the site changes and
then different size thumbnails are needed than what were originally
created. For design flexibility, I've been impressed with the approach
of sorl.thumbnail, a popular Django image thumbnailing library. Sorl
provides a template tag (and model field type) where the designer can
specify the dimensions of the thumbnail to generate in the HTML
templates and sorl creates that thumbnail as the page loads (if
necessary). The downside to that approach is that it requires the
directory of images to be at least mounted by the web application
server (if not just on the same disk). For even moderately large or
high traffic sites, it is problematic to couple the image/file server
and application server so tightly. It also requires PIL, a fairly
heavyweight Python library to be compiled and installed on the app
server and loaded into memory.

Image upload directories with a fair number of images and derived
thumbnails also tend to have large numbers of files and directories
and can become fairly tricky to efficiently backup and/or replicate
for higher availability. 

For addressing replication and high availability, I've experimented
with Tahoe-LAFS, a web-based distributed filesystem. I like Tahoe-LAFS
for many applications, but it does not deal well with this image
serving use-case since files stored in Tahoe-LAFS are not directly
available as files on a filesystem that can be accessed by the
resizing libraries. If images are stored in Tahoe, to resize them,
they must be downloaded via HTTP GET (which involves decrypting and
de-erasure coding them), resized, and then inserted back into the grid
via HTTP POST (which involves encrypting and erasure coding them). The
latency involved in that pretty much requires the approach of scaling
the images to preset sizes beforehand (and losing that sorl style
design flexibility). 

System Description
------------------

Apomixis attempts to address these issues and achieve a good balance. 

Apomixis runs as one or more nodes (probably on seperate servers) with
an HTTP/REST interface. The nodes are aware of each other and will
distribute the storage of images between themselves in an intelligent
fashion. Any image stored in the grid can be retrieved through any
node in the grid. Images are retrieved via HTTP by their id, which is
a short string hash of the contents of the full-size image, and a size
specification. It looks something like this:

* a "client" web application accepts an image upload from a user, and
  POSTs that image file to one of the apomixis nodes that it knows
  about.
* the apomixis node stores the image to one or more nodes in the grid
  and gives the client the image id for later retrieval
* the client saves that image id (probably in a database
  somewhere). It's just a tiny text string, so that's easy.
* the display/view/template layer of the client application, on a page
  where that image is to be displayed, just constructs a URL pointing
  to an apomixis node with the image id and a size specification and
  puts that URL into the src of an image tag.
* the user's browser loads the page, parses out the image tag and
  makes a GET request to the apomixis node
* the apomixis node retrieves the image either from it's own local
  storage or from another node in the grid that has it, scales it to
  the requested size (if necessary), and serves it to the browser.

The advantages of this approach:

* image storing/serving/resizing is separated from the main
  application server, allowing you to scale those resources separately
  and/or differently
* design flexibility for thumbnail size is retained (no batch resize
  scripts to write)
* the cluster can be nicely load-balanced (nginx's load balancing and
  caching is a winner here)
* the cluster handles replication and high availability automatically
  (it uses a distributed hash table to spread image copies between
  nodes in a stable, efficient manner). If you have enough nodes and
  enough replication, you might not need extra backup solutions.
* The cluster supports easy dynamic adding and dropping of nodes. (The
  approach is inspired by Riak and Amazon's Dynamo model).


Implementation Details
----------------------

Written in Django (python), using PIL for image scaling/cropping. Uses
sqlite for lightweight database stuff (just keeping track of other
nodes in the cluster). 

Images ids are just SHA1 hashes of the contents of the images. Images
are stored on disk in a directory structure based on the hash (ie, no
database hits required to check if the node has an image). 

Inter-node communication is HTTP. Nodes "gossip" with the other nodes
they are aware of to keep the entire cluster updated about all nodes'
status. Much of this happens in background jobs managed with Celery
(and probably RabbitMQ).

Apomixis is a Django app, but uses X-sendfile to allow Apache (or
lighttpd/nginx) to handle the actual serving of files for efficiency.


Configuration
-------------

TODO. look at the CLUSTER part of settings_shared to start. It's
fairly self-explanatory.

Known Issues
------------

See: https://github.com/thraxil/apomixis/issues

Future Roadmap
--------------

* Verification job. Runs regularly, walks the directory of images on
  the node, recalculates the hashes of the images, compares to the
  hashes they were stored as and repairs and/or rebalances them as
  necessary. 
* experiment with porting to C to speed things up even more
* allow suggested image sizes upon upload. Ie, a client knows that
  particular sizes are likely to be requested in the future so it
  might as well create them beforehand.
* experiment with just using Riak for image storing via its luwak file
  storage. The problem with this is probably that resizing again
  requires downloading via HTTP, resizing, then re-uploading. 
* move to something more lightweight than Celery/RabbitMQ for job
  queues.
* distributing images between nodes on upload could be done in
  background tasks to improve latency on upload.
* location aware replication. Ie, you've got multiple datacenters
  where nodes run and you want to make sure that uploaded images
  always get stored to each datacenter in addition to the basic
  replication level. This provides basic disaster recovery support.

