# Django settings for apomixis project.
import os.path

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = ( )

MANAGERS = ADMINS

DATABASE_ENGINE = 'sqlite3' 
DATABASE_NAME = ':memory:' 
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

INSTALLED_APPS = (
    'main',
)

FILE_UPLOAD_PERMISSIONS = 0644
EMAIL_SUBJECT_PREFIX = "[apomixis] "
EMAIL_HOST = 'localhost'
SERVER_EMAIL = "apomixis@ccnmtl.columbia.edu"





