import os

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from CTFd.models import Awards, Teams, db

# One hill per group: the king box of group N is always 10.0.N0.10 (Terraform
# private-N). KOTH_GROUPS is set by the bastion bootstrap (number of subnets).
GROUPS = int(os.environ.get("KOTH_GROUPS", "4"))
KOTH_PORT = int(os.environ.get("KOTH_PORT", "31337"))
HILLS = {n: f"http://10.0.{n * 10}.10:{KOTH_PORT}/king" for n in range(1, GROUPS + 1)}
INTERVAL_SECONDS = 60
POINTS_PER_TICK = 10


def award_hill(app, n, url):
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        king_name = resp.text.strip()
    except Exception as e:
        app.logger.warning(f"[koth] group {n}: could not reach {url}: {e}")
        return

    if not king_name:
        return

    team = Teams.query.filter(
        db.func.lower(Teams.name) == king_name.lower()
    ).first()

    if team is None:
        app.logger.info(f"[koth] group {n}: '{king_name}' does not match any registered team")
        return

    user_id = team.captain_id
    if not user_id and team.members:
        user_id = team.members[0].id

    db.session.add(Awards(
        user_id=user_id,
        team_id=team.id,
        name="King of the Hill",
        description=f"Controlled the hill of group {n}",
        value=POINTS_PER_TICK,
        category="KoTH",
    ))
    db.session.commit()
    app.logger.info(f"[koth] group {n}: awarded {POINTS_PER_TICK} points to '{team.name}'")


def poll_and_award(app):
    with app.app_context():
        for n, url in HILLS.items():
            award_hill(app, n, url)


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
