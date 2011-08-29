from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseNotFound
from django.http import HttpResponsePermanentRedirect
import hmac, hashlib
from django.conf import settings
import tempfile
import os.path
import shutil
import re
import Image, cStringIO
import simplejson
from models import Node, current_neighbors, normalize_url, hash_keys, ring, write_ring, write_order
from datetime import datetime
from restclient import POST

def square_resize(img,size):
    sizes = list(img.size)
    trim = abs(sizes[1] - sizes[0]) / 2
    if sizes[0] < sizes[1]:
        img = img.crop((0,trim,sizes[0],trim + sizes[0]))
    if sizes[1] < sizes[0]:
        img = img.crop((trim,0,trim + sizes[1],sizes[1]))
    return img.resize((size,size),Image.ANTIALIAS)    

def resize(img,width=None,height=None,square=False):
    if width is None and height is None and not square:
        # no dimensions specified
        return img
    if square:
        size = width or height or min(list(img.size))
        img = square_resize(img,size)
    else:
        sizes = list(img.size)
        if width is None:
            # only constraining on height
            width = sizes[0]
        if height is None:
            height = sizes[1]
        img.thumbnail((width,height),Image.ANTIALIAS)

    # workaround for PIL bug
    if img.size[0] == 0:
        img = img.resize((1,img.size[1]))
    if img.size[1] == 0:
        img = img.resize((img.size[0],1))
        
    return img

class rendered_with(object):
    def __init__(self, template_name):
        self.template_name = template_name

    def __call__(self, func):
        def rendered_func(request, *args, **kwargs):
            items = func(request, *args, **kwargs)
            if type(items) == type({}):
                return render_to_response(self.template_name, items, context_instance=RequestContext(request))
            else:
                return items

        return rendered_func

def path_from_hash(sha1):
    # convert from "8b7e052215635bfc2774e23dcb5c7aaadf81b42b" 
    #           to "8b/7e/05/22/15/63/5b/fc/27/74/e2/3d/cb/5c/7a/aa/df/81/b4/2b"
    return os.path.join(*["%s%s" % (a,b) for (a,b) in zip(sha1[::2],sha1[1::2])])

def full_path_from_hash(sha1):
    return os.path.join(settings.MEDIA_ROOT, "data", path_from_hash(sha1))

def url_from_hash(sha1):
    return os.path.join(settings.MEDIA_URL, "data", path_from_hash(sha1))


def announce(request):
    """ all purpose announce/gossip url. 
    returns info about itself and about the other nodes it knows in the cluster
    can be passed info about the node calling """
    # TODO: authenticate

    n = dict()
    if request.method == 'GET':
        n = request.GET
    else:
        n = request.POST
    if 'json' in n.keys():
        # let them just pass it in as a json dict
        # TODO: allow POST body as json (look at content-type)
        n = simplejson.loads(n['json'])

    if 'uuid' in n.keys():
        # neighbor is announcing to us, let's listen to what they have to say
        nuuid = n['uuid']
        r = Node.objects.filter(uuid=nuuid)
        if r.count():
            # we've met this neighbor before. just update.
            neighbor = r[0]
            neighbor.last_seen = datetime.now()
            neighbor.save()
        else:
            # hello new neighbor!
            neighbor = Node.objects.create(uuid=nuuid,
                                           nickname=n['nickname'],
                                           base_url=n['base_url'],
                                           location=n['location'],
                                           writeable=n['writeable'],
                                           )

    # be polite and respond with data about myself
    protocol = request.is_secure() and "https" or "http"
    data = {
        'nickname' : settings.CLUSTER['nickname'], 
        'uuid' : settings.CLUSTER['uuid'], 
        'location' : settings.CLUSTER['location'],
        'nodes' : [n.as_dict() for n in current_neighbors()], 
        # TODO: determine based on storage caps
        'writeable' : settings.CLUSTER['writeable'], 
        'base_url' : normalize_url("%s://%s/" % (protocol,request.get_host())),
        }
    return HttpResponse(simplejson.dumps(data),mimetype="application/json")

@rendered_with("main/status.html")
def status(request):
    """ just basic human readable status information 
    on what the node knows about the cluster """
    # TODO: authenticate

    protocol = request.is_secure() and "https" or "http"
    data = {
        'nickname' : settings.CLUSTER['nickname'], 
        'uuid' : settings.CLUSTER['uuid'], 
        'location' : settings.CLUSTER['location'],
        'nodes' : Node.objects.all(),
        # TODO: determine based on storage caps
        'writeable' : settings.CLUSTER['writeable'], 
        'base_url' : normalize_url("%s://%s/" % (protocol,request.get_host())),
        'hash_keys' : hash_keys(settings.CLUSTER['uuid']),
        'ring' : ring(),
        }
    return data

def bootstrap(request):
    """ announce ourselves to all the nodes in the cluster config to get things started """
    myinfo = settings.CLUSTER
    protocol = request.is_secure() and "https" or "http"
    myinfo['base_url'] = normalize_url("%s://%s/" % (protocol,request.get_host()))
    for url in settings.CLUSTER['nodes']:
        try:
            r = POST(url + "announce/",params=myinfo,async=False)
            n = simplejson.loads(r)
            nuuid = n['uuid']
            r = Node.objects.filter(uuid=nuuid)
            if r.count():
                # we've met this neighbor before. just update.
                neighbor = r[0]
                neighbor.last_seen = datetime.now()
                neighbor.save()
            else:
                # hello new neighbor!
                neighbor = Node.objects.create(uuid=nuuid,
                                               nickname=n['nickname'],
                                               base_url=n['base_url'],
                                               location=n['location'],
                                               writeable=n['writeable'],
                                               )
        except Exception, e:
            pass
    return HttpResponse("done")

@rendered_with("main/index.html")
def index(request):
    upload_key_required = settings.UPLOAD_KEYS is not None
    if request.method == "POST":
        if upload_key_required:
            upload_key = request.POST.get("upload_key","")
            if upload_key not in settings.UPLOAD_KEYS:
                return HttpResponse("missing/wrong upload key")
        if request.FILES.get('image',None):
            original_filename = request.FILES['image'].name
            extension = os.path.splitext(original_filename)[1].lower()
            if extension == ".jpeg":
                extension = ".jpg"
            if extension not in [".jpg",".png",".gif"]:
                return HttpResponse("unsupported image format")

            tmpfile = tempfile.NamedTemporaryFile(delete=False)
            sha1 = hashlib.sha1()
            for chunk in request.FILES['image'].chunks():
                sha1.update(chunk)
                tmpfile.file.write(chunk)
            tmpfile.file.close()
            sha1 = sha1.hexdigest()
            path = full_path_from_hash(sha1)
            try:
                os.makedirs(path)
            except Exception, e:
                pass
            # OPTIMIZE: if target file already exists (duplicate upload)
            #           no need to copy the file over it
            shutil.move(tmpfile.name,os.path.join(path,"image" + extension))
            if settings.FILE_UPLOAD_PERMISSIONS is not None:
                os.chmod(os.path.join(path,"image" + extension), settings.FILE_UPLOAD_PERMISSIONS)

            data = dict(hash=sha1,extension=extension,
                        full_url="/image/%s/full/image%s" % (sha1,extension))

            # TODO: this should be a background job
            # distribute out the the cluster
            satisfied = False
            copies = 1
            wr = write_order(long(sha1,16))
            for node in wr:
                if copies >= settings.CLUSTER['replication']:
                    satisfied = True
                else:
                    if node.uuid == settings.CLUSTER['uuid']:
                        # skip ourselves
                        continue
                    r = node.stash(sha1,extension,request.FILES['image'])
                    if r:
                        copies += 1
                    else:
                        # failure to write!
                        # take it off the writeable list for now
                        node.last_failed = datetime.now()
                        node.writeable = False
                        node.save()
            data['satisfied'] = satisfied
            return HttpResponse(simplejson.dumps(data),mimetype="application/json")
        else:
            return HttpResponse("no image uploaded")
    else:
        return dict(upload_key_required=upload_key_required)

def stash(request):
    if request.method == "POST":
        extension = request.POST['extension']
        tmpfile = tempfile.NamedTemporaryFile(delete=False)
        sha1 = request.POST['hash']
        for chunk in request.FILES['image'].chunks():
            tmpfile.file.write(chunk)
        tmpfile.file.close()
        path = full_path_from_hash(sha1)
        try:
            os.makedirs(path)
        except Exception, e:
            pass
        # OPTIMIZE: if target file already exists (duplicate upload)
        #           no need to copy the file over it
        shutil.move(tmpfile.name,os.path.join(path,"image" + extension))
        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(os.path.join(path,"image" + extension), settings.FILE_UPLOAD_PERMISSIONS)        
        return HttpResponse("done")
    return HttpResponse("requires POST")

def normalize_size_format(size):
    """ always go width first. ie, 100h100w gets converted to 100w100h """
    if "h" in size and "w" in size:
        width, height = 0,0
        m = re.search('(\d+)w', size)
        if m:
            width = int(m.groups(0)[0])
        m = re.search('(\d+)h', size)
        if m:
            height = int(m.groups(0)[0])
        return "%dw%dh" % (width,height)
    else:
        # nothing to normalize
        return size

def serve_file(filename,ext):
    USE_XSENDFILE = getattr(settings, 'USE_XSENDFILE', False)
    if USE_XSENDFILE:
        response = HttpResponse()
        response['X-Sendfile'] = filename
        response['Content-Type'] = ''
        return response
    else:
        data = open(filename).read()
        mimes = dict(jpg="image/jpeg",gif="image/gif",png="image/png")
        return HttpResponse(data,mimes[ext])

def image(request,sha,size,basename,ext):
    # TODO: handle etags
    # TODO: handle if-modified-since headers
    # TODO: send image dimensions in headers
    # TODO: detect noop resizes and 301 to existing ones
    #       instead of creating duplicate files
    ext = ext.lower()
    if ext == "jpeg":
        ext = "jpg"
    dirpath = full_path_from_hash(sha)
    full_filename = "image.%s" % ext
    if size == "full":
        filename = full_filename
    else:
        size = normalize_size_format(size)
        filename = "%s.%s" % (size,ext)
    if os.path.exists(os.path.join(dirpath,filename)):
        # if that file exists already, we can just serve it
        return serve_file(os.path.join(dirpath,filename),ext)
    else:
        # it doesn't exist. let's first check to see if it exists with a 
        # different extension though and redirect to that
        for test_ext in ["jpg","gif","png"]:
            test_filename = "%s.%s" % (size,test_ext)
            if os.path.exists(os.path.join(dirpath,test_filename)):
                # aha! this file exists, just with a different extension
                # redirect them to that one instead
                return HttpResponsePermanentRedirect("/image/%s/%s/image.%s" % (sha,size,test_ext))
        square = False
        # otherwise, we need to create it first
        # parse file size spec
        height = None
        width = None

        if size.endswith("s"):
            # crop to square
            width = int(size[:-1])
            square = True
        else:
            # get width and/or height
            m = re.search('(\d+)w', size)
            if m:
                width = int(m.groups(0)[0])
            m = re.search('(\d+)h', size)
            if m:
                height = int(m.groups(0)[0])

        im = Image.open(os.path.join(dirpath,full_filename))
        im = resize(im,width,height,square)
        im.save(os.path.join(dirpath,filename))
        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(os.path.join(dirpath,filename), settings.FILE_UPLOAD_PERMISSIONS)

        return serve_file(os.path.join(dirpath,filename),ext)

