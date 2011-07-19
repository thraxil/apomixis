from settings_shared import *

TEMPLATE_DIRS = (
    "/var/www/apomixis/apomixis/templates",
)

MEDIA_ROOT = '/var/www/apomixis/uploads/'
# put any static media here to override app served static media
STATICMEDIA_MOUNTS = (
    ('/sitemedia', '/var/www/apomixis/apomixis/sitemedia'),	
)


DEBUG = False
TEMPLATE_DEBUG = DEBUG
USE_XSENDFILE = True

try:
    from local_settings import *
except ImportError:
    pass
