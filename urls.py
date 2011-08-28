from django.conf.urls.defaults import *
from django.conf import settings
import os.path

site_media_root = os.path.join(os.path.dirname(__file__),"media")

urlpatterns = patterns('',
                       (r'^$','main.views.index'),
                       (r'^announce/$','main.views.announce'),
                       (r'^status/$','main.views.status'),
                       (r'^bootstrap/$','main.views.bootstrap'),
                       (r'^image/(?P<sha>\w+)/(?P<size>\w+)/(?P<basename>\w+)\.(?P<ext>\w{,4})$','main.views.image'),
                       (r'^site_media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': site_media_root}),
                       (r'^uploads/(?P<path>.*)$','django.views.static.serve',{'document_root' : settings.MEDIA_ROOT}),
) 

