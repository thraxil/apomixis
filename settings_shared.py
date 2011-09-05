# Django settings for apomixis project.
import os.path

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = ( )

MANAGERS = ADMINS

DATABASE_ENGINE = 'sqlite3' 
DATABASE_NAME = 'apomixis.sqlite' 
DATABASE_USER = ''         
DATABASE_PASSWORD = ''     
DATABASE_HOST = ''         
DATABASE_PORT = ''         

TIME_ZONE = 'America/New_York'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = False
MEDIA_ROOT = "/var/www/apomixis/uploads/"
SECRET_KEY = 'ASDFGHXCVBERrtdfscvsbwerg'
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.debug',
    'django.core.context_processors.request',
    )

MIDDLEWARE_CLASSES = (
)

ROOT_URLCONF = 'apomixis.urls'

TEMPLATE_DIRS = (
    "/var/www/apomixis/templates/",
    os.path.join(os.path.dirname(__file__),"templates"),
)

import djcelery
djcelery.setup_loader()


INSTALLED_APPS = (
    'main',
    'djcelery',
)

FILE_UPLOAD_PERMISSIONS = 0644
EMAIL_SUBJECT_PREFIX = "[apomixis] "
EMAIL_HOST = 'localhost'
SERVER_EMAIL = "apomixis@ccnmtl.columbia.edu"

#CELERY_RESULT_BACKEND = "database"
BROKER_HOST = "localhost"
BROKER_PORT = 5672
#BROKER_USER = "guest"
#BROKER_PASSWORD = "guest"
BROKER_VHOST = "/"
CELERYD_CONCURRENCY = 4

UPLOAD_KEYS = None

CLUSTER = {
    'name' : 'testcluster', # name of the cluster
    'uuid' : 'fillmein', # my UUID (randomly generated)
    'secret' : 'this is secret stuffs', # shared secret for the cluster
    'location' : 'butler', # my location
    'nodes' : ['http://localhost:8001/'], # other nodes in the cluster
    'nickname' : 'behemoth1', # my nickname in the cluster
    'replication' : 3, # how many copies of each image it will try to maintain
    'location_replication' : 1, # how many locations it will try to spread those copies over
    'writeable' : True, # i can handle uploads
    'announce_frequency' : 300, # how often to re-announce self to the cluster (seconds)
    'base_url' : "http://localhost:8000/",
    }




