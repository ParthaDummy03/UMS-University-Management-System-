DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'lotus_university',
        'USER': 'your_db_user',
        'PASSWORD': 'your_password',
        'HOST': 'HOST_IP_OR_localhost',
        'PORT': '3306',
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}
AUTH_USER_MODEL = 'core.User'