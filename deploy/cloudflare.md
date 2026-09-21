# Cloudflare setup

1. **DNS:** add an `A` record pointing at the droplet, proxied (orange cloud).
2. **SSL/TLS:** set the mode to *Full (strict)*. Create an Origin Certificate
   (SSL/TLS → Origin Server) and install it at `/etc/ssl/cloudflare/origin.{pem,key}`,
   which is where `nginx.conf` expects it.
3. **Caching:** nginx already sends the right `Cache-Control` headers. Cloudflare only
   caches static extensions by default, and `.json` isn't one of them, so add one
   **Cache Rule**:
   - *When:* URI Path equals `/today.json`
   - *Then:* Eligible for cache, Edge TTL = "Use cache-control header if present"
     (nginx sends `s-maxage=300`).

   Images, fonts, JS and CSS are cached by default and honour the origin's `max-age`.
4. **Purge on build:** create an API token with only *Zone → Cache Purge → Purge* for
   this zone. Put it in `/etc/todays-darling.env` as `CF_API_TOKEN`, with `CF_ZONE_ID`
   (shown on the zone's Overview page) and `SITE_URL`. After each successful build the
   job purges `SITE_URL/today.json`. If the purge fails, it's logged and the 5-minute
   edge TTL takes over.
5. **After changing art or code:** purge those URLs (or "Purge Everything") from the
   dashboard. Art is cached for 30 days, and JS/CSS/HTML for an hour.
