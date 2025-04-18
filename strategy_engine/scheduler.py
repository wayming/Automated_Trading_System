
from apscheduler.schedulers.blocking import BlockingScheduler
from cli import live_trade

def job():
    print("Running scheduled strategy...")
    live_trade()

scheduler = BlockingScheduler()
scheduler.add_job(job, 'interval', weeks=1)  # 每周执行一次
scheduler.start()
