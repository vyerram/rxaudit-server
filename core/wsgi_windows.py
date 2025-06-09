activate_this = "C:/Users/aspyr_1/OneDrive/Documents/GitHub/Aspyr-API/.venv/Scripts/activate_this.py"
# execfile(activate_this, dict(__file__=activate_this))
exec(open(activate_this).read(), dict(__file__=activate_this))

import os
import sys
import site

# Add the site-packages of the chosen virtualenv to work with
site.addsitedir(
    "C:/Users/aspyr_1/OneDrive/Documents/GitHub/Aspyr-API/.venv/Lib/site-packages"
)


# Add the app's directory to the PYTHONPATH
sys.path.append("C:/Users/aspyr_1/OneDrive/Documents/GitHub/Aspyr-API")
sys.path.append("C:/Users/aspyr_1/OneDrive/Documents/GitHub/Aspyr-API/core")
sys.path.append("C:/Users/aspyr_1/OneDrive/Documents/GitHub/Aspyr-API/static")

os.environ["DJANGO_SETTINGS_MODULE"] = "settings"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
