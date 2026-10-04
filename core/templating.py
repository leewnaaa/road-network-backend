import os
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

STATIC_CSS_PATH = os.path.join("static", "css", "style.css")


def css_version():
    try:
        return int(os.path.getmtime(STATIC_CSS_PATH))
    except OSError:
        return 0


templates.env.globals["css_version"] = css_version
