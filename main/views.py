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

@rendered_with("main/index.html")
def index(request):
    if request.method == "POST":
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

            return HttpResponse(simplejson.dumps(data),mimetype="application/json")
        else:
            return HttpResponse("no image uploaded")
    else:
        return dict()

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

