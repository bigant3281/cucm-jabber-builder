#!/usr/bin/env python3
"""
Local helper for the CUCM Jabber Device Builder web page.

Browsers cannot call CUCM's AXL API directly (no CORS headers, usually a
self-signed certificate). This tiny proxy:
  * serves index.html at http://127.0.0.1:8080/
  * forwards the page's AXL requests to https://<cucm>:8443/axl/

It listens on 127.0.0.1 only, stores nothing, and writes no credentials to disk.
Python 3.8+, standard library only.

    python cucm_proxy.py                 # then open http://127.0.0.1:8080
    python cucm_proxy.py --port 9000
    python cucm_proxy.py --allow-origin https://<you>.github.io   # use the Pages-hosted copy of the page
"""
import argparse
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.\-]*[A-Za-z0-9])?(:\d{1,5})?$")
VER_RE = re.compile(r"^\d{1,2}\.\d$")
ALLOWED_ORIGINS = set()


class Handler(BaseHTTPRequestHandler):
    server_version = "CucmLocalProxy/1.0"

    def log_message(self, fmt, *args):  # keep console quiet, never log headers
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---- helpers ----
    def own_origins(self):
        port = self.server.server_address[1]
        return {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    def origin_ok(self):
        origin = self.headers.get("Origin")
        return origin is None or origin in self.own_origins() or origin in ALLOWED_ORIGINS

    def cors(self):
        origin = self.headers.get("Origin")
        if origin and origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers",
                             "Authorization, Content-Type, X-CUCM-Host, X-CUCM-Verify, X-AXL-Version")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def reply(self, code, body, ctype="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.cors()
        self.end_headers()
        self.wfile.write(body)

    # ---- routes ----
    def do_OPTIONS(self):
        if not self.origin_ok():
            return self.reply(403, "Origin not allowed")
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    return self.reply(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                return self.reply(404, "index.html not found next to cucm_proxy.py")
        self.reply(404, "Not found")

    def do_POST(self):
        if self.path != "/proxy":
            return self.reply(404, "Not found")
        if not self.origin_ok():
            return self.reply(403, "Origin not allowed")
        host = (self.headers.get("X-CUCM-Host") or "").strip()
        ver = (self.headers.get("X-AXL-Version") or "14.0").strip()
        auth = self.headers.get("Authorization")
        if not HOST_RE.match(host) or not VER_RE.match(ver) or not auth:
            return self.reply(400, "Bad host, AXL version or credentials")
        if ":" not in host:
            host += ":8443"
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 2_000_000:
            return self.reply(400, "Bad request body size")
        body = self.rfile.read(length)

        ctx = ssl.create_default_context()
        if self.headers.get("X-CUCM-Verify") != "1":
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            f"https://{host}/axl/", data=body, method="POST",
            headers={"Content-Type": "text/xml; charset=utf-8",
                     "SOAPAction": f'"CUCM:DB ver={ver}"',
                     "Authorization": auth})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
                return self.reply(r.status, r.read(), "text/xml; charset=utf-8")
        except urllib.error.HTTPError as e:  # AXL faults come back as HTTP 500 with XML
            return self.reply(e.code, e.read(), "text/xml; charset=utf-8")
        except Exception as e:
            return self.reply(502, f"Could not reach CUCM at {host}: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--allow-origin", action="append", default=[],
                    help="extra web origin allowed to use this proxy (e.g. your GitHub Pages URL); repeatable")
    a = ap.parse_args()
    ALLOWED_ORIGINS.update(o.rstrip("/") for o in a.allow_origin)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"CUCM Device Builder running at http://127.0.0.1:{a.port}/   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
