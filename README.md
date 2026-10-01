# cucm-jabber-builder
Builds Jabber profiles based on SEP profile

Browser UI that clones an existing CUCM device's configuration into **CSF / BOT / TCT / TAB**
devices for an end user (`amorales` → `CSFAMORALES`, `BOTAMORALES`, `TCTAMORALES`, `TABAMORALES`).
The username part is cut to 12 characters so device names never exceed CUCM's 15-character limit.

## Why there are two files

Browsers can't call CUCM's AXL API directly (no CORS headers, usually a self-signed certificate).
`cucm_proxy.py` is a tiny local helper (Python 3.8+, standard library only) that serves the page and
forwards its AXL requests to CUCM. It binds to `127.0.0.1` only and stores nothing.

## Run it

1. Download `index.html` and `cucm_proxy.py` into the same folder.
2. `python cucm_proxy.py`
3. Open <http://127.0.0.1:8080/>
4. Log in, search for the source device, enter the username, tick the device types, **Create devices**.

AXL account needs the **Standard AXL API Access** role. TLS verification of the CUCM certificate is
off by default (self-signed); tick the box to enforce it.

### Using the GitHub Pages copy of the page

Publish `index.html` (and this README) with GitHub Pages, then run the proxy allowing that origin:

```
python cucm_proxy.py --allow-origin https://<you>.github.io
```

Open your Pages URL and set **Local proxy URL** to `http://127.0.0.1:8080`.
Chrome/Edge/Firefox permit an HTTPS page to call `127.0.0.1`. The proxy answers the Private Network Access preflight.

## Notes

- Defaults for security/SIP profile names may differ on your cluster; if CUCM reports a profile not
  found, edit `DEVICE_TYPES` at the top of the script in `index.html`. If the source device is the same
  model as the one being created, its own profiles are reused.
- Owner user ID is set, but the device is not added to the user's controlled devices, and no primary
  extension is set.
- Don't publish anything containing credentials. The page never stores them.
