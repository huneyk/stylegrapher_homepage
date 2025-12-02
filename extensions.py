from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_babel import Babel
from flask_compress import Compress
from flask_caching import Cache

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
babel = Babel()
compress = Compress()
cache = Cache() 