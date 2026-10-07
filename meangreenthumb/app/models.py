from datetime import datetime
from flask_login import UserMixin
from app import db


# --- Junction table for the Plant <-> GrowingZone many-to-many ---
plant_zone = db.Table(
    "plant_zone",
    db.Column("plant_id", db.Integer, db.ForeignKey("plant.plant_id"), primary_key=True),
    db.Column("zone_id", db.Integer, db.ForeignKey("growing_zone.zone_id"), primary_key=True),
)


class GrowingZone(db.Model):
    __tablename__ = "growing_zone"
    zone_id = db.Column(db.Integer, primary_key=True)
    zone_code = db.Column(db.String(10), unique=True, nullable=False)  # e.g. "8a"
    region_data = db.Column(db.String(255))

    users = db.relationship("User", back_populates="growing_zone")
    plants = db.relationship("Plant", secondary=plant_zone, back_populates="zones")
    tips = db.relationship("Tip", back_populates="zone")


class User(UserMixin, db.Model):
    __tablename__ = "user"
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    zip_code = db.Column(db.String(5))
    zone_id = db.Column(db.Integer, db.ForeignKey("growing_zone.zone_id"))
    notifications_enabled = db.Column(db.Boolean, default=False)

    growing_zone = db.relationship("GrowingZone", back_populates="users")
    saved_plants = db.relationship("SavedPlant", back_populates="user", cascade="all, delete-orphan")
    tips = db.relationship("Tip", back_populates="author", cascade="all, delete-orphan")
    alerts = db.relationship("WeatherAlert", back_populates="user", cascade="all, delete-orphan")

    # flask-login expects get_id() to return a string; UserMixin provides this
    # using the primary key column name, so make sure it matches "user_id".
    def get_id(self):
        return str(self.user_id)


class Plant(db.Model):
    __tablename__ = "plant"
    plant_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    recommended_planting_time = db.Column(db.String(100))

    zones = db.relationship("GrowingZone", secondary=plant_zone, back_populates="plants")
    saved_entries = db.relationship("SavedPlant", back_populates="plant")


class SavedPlant(db.Model):
    """A row in a user's 'My Plants' list."""
    __tablename__ = "saved_plant"
    saved_plant_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey("plant.plant_id"), nullable=False)
    planting_date = db.Column(db.Date)

    user = db.relationship("User", back_populates="saved_plants")
    plant = db.relationship("Plant", back_populates="saved_entries")
    care_tasks = db.relationship("CareTask", back_populates="saved_plant", cascade="all, delete-orphan")


class CareTask(db.Model):
    __tablename__ = "care_task"
    task_id = db.Column(db.Integer, primary_key=True)
    saved_plant_id = db.Column(db.Integer, db.ForeignKey("saved_plant.saved_plant_id"), nullable=False)
    task_description = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False)

    saved_plant = db.relationship("SavedPlant", back_populates="care_tasks")

    def is_overdue(self, today=None):
        today = today or datetime.utcnow().date()
        return (not self.completed) and self.due_date is not None and self.due_date < today


class Tip(db.Model):
    __tablename__ = "tip"
    tip_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    zone_id = db.Column(db.Integer, db.ForeignKey("growing_zone.zone_id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", back_populates="tips")
    zone = db.relationship("GrowingZone", back_populates="tips")


class WeatherAlert(db.Model):
    __tablename__ = "weather_alert"
    alert_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="alerts")


class ZoneWeatherStatus(db.Model):
    """
    NOT in the original ER Diagram / Class Diagram -- added here to support
    the Scheduler (FR-05). Tracks the last known freeze/frost status per
    zone so the scheduler doesn't re-send the same alert every 3-hour cycle
    while a Watch or Warning is still active.

    TODO (whoever updates the SRS/design doc): add this table to the ER
    Diagram and a matching class to the Class Diagram.
    """
    __tablename__ = "zone_weather_status"
    zone_id = db.Column(db.Integer, db.ForeignKey("growing_zone.zone_id"), primary_key=True)
    status = db.Column(db.String(20), default="none")  # "none" | "watch" | "warning"
    last_checked_at = db.Column(db.DateTime, default=datetime.utcnow)

    zone = db.relationship("GrowingZone")
