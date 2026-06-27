import datetime

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from CTFd.models import Awards, Teams, db

TARGET_URL = "http://10.0.10.10:31337/king"
INTERVAL_SECONDS = 60
POINTS_PER_TICK = 10

def poll_and_award(app):
    with app.app_context():
        try:
            resp = requests.get(TARGET_URL, timeout=5)
            resp.raise_for_status()
            king_name = resp.text.strip()
        except Exception as e:
            app.logger.warning(f"[koth] could not reach target agent: {e}")
            return

        if not king_name:
            return

        team = Teams.query.filter(
            db.func.lower(Teams.name) == king_name.lower()
        ).first()

        if team is None:
            app.logger.info(f"[koth] '{king_name}' does not match any registered team")
            return

        user_id = team.captain_id
        if not user_id and team.members:
            user_id = team.members[0].id

        db.session.add(Awards(
            user_id=user_id,
            team_id=team.id,
            name="King of the Hill",
            description=f"Controlled the hill at {datetime.datetime.utcnow().isoformat()}Z",
            value=POINTS_PER_TICK,
            category="KoTH",
        ))
        db.session.commit()
        app.logger.info(f"[koth] awarded {POINTS_PER_TICK} points to '{team.name}'")


def load(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: poll_and_award(app),
        trigger="interval",
        seconds=INTERVAL_SECONDS,
        id="koth_poll",
        replace_existing=True,
    )
    scheduler.start()