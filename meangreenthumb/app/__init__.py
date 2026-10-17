from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.plants import plants_bp
    from app.routes.my_plants import my_plants_bp
    from app.routes.care_tasks import care_tasks_bp
    from app.routes.tips import tips_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(plants_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(my_plants_bp)
    app.register_blueprint(care_tasks_bp)
    app.register_blueprint(tips_bp)

    with app.app_context():
        db.create_all()

    from app.scheduler import setup_scheduler
    setup_scheduler(app)

    return app
