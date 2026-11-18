DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'lotus_university',
        'USER': 'root',
        'PASSWORD': 'arirpa25',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}
AUTH_USER_MODEL = 'core.User'
