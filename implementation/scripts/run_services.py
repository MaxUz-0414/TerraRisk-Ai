#!/usr/bin/env python3
"""Run the eight TerraRisk services as eight separate processes on your own computer (no Docker needed).

    python scripts/run_services.py            # start them, wait until healthy, print what to put in .env, stay running
    python scripts/run_services.py --env      # only print the .env lines (ports are fixed, so you can copy them once)

Then, in another terminal, start the website in "http" mode so it talks to them over real HTTP, exactly like in production:

    SERVICES_MODE=http python manage.py runserver

Stop everything with Ctrl-C. Data (billing database, geocode cache, satellite picture cache) is kept in ./.local-services/.
Each service is the same code that the Docker images run; here the Flask development server is used instead of gunicorn.
"""
import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:  # the services read the same .env as the website (GEMINI_API_KEY, USE_FAKE_DATA, GEE_* ...)
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass
SERVICES = ["analysis", "satellite", "risk", "advisory", "report", "billing", "geocode", "chatbot"]
BASE_PORT = 8101
DATA = ROOT / ".local-services"
TOKEN = os.environ.get("INTERNAL_TOKEN", "dev-internal-token")


def port(name):
    return BASE_PORT + SERVICES.index(name)


def url(name):
    return f"http://127.0.0.1:{port(name)}"


def env_lines():
    lines = ["SERVICES_MODE=http", f"INTERNAL_TOKEN={TOKEN}"]
    lines += [f"{name.upper()}_URL={url(name)}" for name in SERVICES]
    return lines


def child_env(name):
    env = dict(os.environ)
    env.update(INTERNAL_TOKEN=TOKEN, BILLING_DB=str(DATA / "billing.sqlite3"), GEOCODE_DB=str(DATA / "geocode.sqlite3"),
               CACHE_DIR=str(DATA / "satellite-cache"), PYTHONUNBUFFERED="1")
    env.update({f"{n.upper()}_URL": url(n) for n in SERVICES})
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "services" / "common"), str(ROOT / "services" / name)])
    return env


def healthy(name):
    try:
        request = urllib.request.Request(url(name) + "/healthz", headers={"X-Service-Token": TOKEN})
        with urllib.request.urlopen(request, timeout=2) as reply:
            return reply.status == 200
    except Exception:
        return False


LAUNCHER = ("from werkzeug.serving import run_simple; from tr_{name}.app import create_app; "
            "run_simple('127.0.0.1', {port}, create_app(), threaded=True, use_reloader=False)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", action="store_true", help="only print the .env lines and exit")
    args = parser.parse_args()
    if args.env:
        print("\n".join(env_lines()))
        return 0

    DATA.mkdir(exist_ok=True)
    procs = {}
    for name in SERVICES:
        code = LAUNCHER.format(name=name, port=port(name))
        procs[name] = subprocess.Popen([sys.executable, "-c", code], env=child_env(name), cwd=ROOT,
                                       stdout=open(DATA / f"{name}.log", "w"), stderr=subprocess.STDOUT)

    def stop(*_):
        for proc in procs.values():
            proc.terminate()
        for proc in procs.values():
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("\nAll services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    deadline = time.time() + 60
    waiting = set(SERVICES)
    while waiting and time.time() < deadline:
        for name in list(waiting):
            if procs[name].poll() is not None:
                print(f"x {name} stopped at start-up. Last lines of {DATA / (name + '.log')}:")
                print("".join(open(DATA / f"{name}.log").readlines()[-12:]))
                stop()
            if healthy(name):
                waiting.discard(name)
                print(f"+ {name:<9} {url(name)}")
        time.sleep(0.4)
    if waiting:
        print("x did not become healthy in 60 s:", ", ".join(sorted(waiting)))
        stop()

    print("\nAll services are up. Add these lines to .env (or export them), then start the website:\n")
    print("\n".join("    " + line for line in env_lines()))
    print("\n    python manage.py runserver\n\nPress Ctrl-C to stop the services. Logs: .local-services/<name>.log")
    while True:
        for name, proc in procs.items():
            if proc.poll() is not None:
                print(f"! {name} stopped (exit code {proc.returncode}); see .local-services/{name}.log")
                procs.pop(name)
                break
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
