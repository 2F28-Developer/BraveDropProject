import os
from datetime import datetime
import django

# -----------------------------------------------------------------------------
# Set up Django settings and initialize
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Center.settings")
django.setup()

from apscheduler.schedulers.blocking import BlockingScheduler
from main.tasks import update_item_prices, poll_withdrawals

# -----------------------------------------------------------------------------
# Create and configure the scheduler
scheduler = BlockingScheduler()

# Run price updates every 15 minutes, starting immediately
scheduler.add_job(
    update_item_prices,
    'interval',
    minutes=15,
    next_run_time=datetime.now()
)

# Run withdrawal polling every minute, starting immediately
scheduler.add_job(
    poll_withdrawals,
    'interval',
    minutes=1,
    next_run_time=datetime.now()
)

# -----------------------------------------------------------------------------
if __name__ == '__main__':
    print("Start APScheduler...")
    scheduler.start()
