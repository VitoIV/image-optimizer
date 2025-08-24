import os, sys, time, subprocess, redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME = os.getenv("QUEUE_NAME", "batches")
WORKER_PROCESSES = int(os.getenv("WORKER_PROCESSES", "2"))

def launch_worker():
    return subprocess.Popen(["rq", "worker", "-u", REDIS_URL, QUEUE_NAME], stdout=sys.stdout, stderr=sys.stderr)

def main():
    print("[supervisor] starting")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    if not r.get("workers:desired"):
        r.set("workers:desired", str(WORKER_PROCESSES))
    procs = []
    try:
        while True:
            desired = int(r.get("workers:desired") or WORKER_PROCESSES)
            while len(procs) < desired:
                p = launch_worker()
                procs.append(p)
                print("[supervisor] +worker", p.pid)
            while len(procs) > desired:
                p = procs.pop()
                p.terminate()
                print("[supervisor] -worker")
            for i, p in enumerate(list(procs)):
                if p.poll() is not None:
                    print("[supervisor] worker died, respawn")
                    procs[i] = launch_worker()
            auto = (r.get("auto_purge_enabled") or os.getenv("AUTO_PURGE_ENABLED","false")).lower() == "true"
            if auto:
                r.rpush("purge:requests", "auto")
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            try: p.terminate()
            except: pass

if __name__ == "__main__":
    main()
