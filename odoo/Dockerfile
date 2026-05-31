# # syntax=docker/dockerfile:1.6
# #
# # Custom Odoo 19 image — prunes the bundled addons folder so only
# # core (base/web/base_setup) + HR (and its hard dependencies) remain.
# # Everything else (Sale, Purchase, Stock, Accounting, CRM, Website, MRP, …)
# # is removed at build time, so users cannot install or even see those apps.
# #

# FROM odoo:19.0

# LABEL maintainer="ZenCore DevOps <devops@zencore.local>"
# LABEL org.opencontainers.image.title="odoo19-custom"
# LABEL org.opencontainers.image.description="Odoo 19 limited to Core + HR + custom addons"

# USER root

# # --- Whitelist-prune Odoo's bundled addons --------------------------------------
# COPY scripts/prune_addons.py /tmp/prune_addons.py

# RUN python3 /tmp/prune_addons.py \
#     && rm -f /tmp/prune_addons.py

# # --- Ensure required runtime dirs exist with correct ownership -------------------
# RUN mkdir -p /mnt/extra-addons /var/log/odoo \
#     && chown -R odoo:odoo /mnt/extra-addons /var/log/odoo

# # --- Install curl (used by the healthcheck) -------------------------------------
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends curl \
#     && rm -rf /var/lib/apt/lists/*

# USER odoo

# EXPOSE 8069 8072

# # Keep the official Odoo image entrypoint (handles PASSWORD_FILE → CLI flags).
# # Just override CMD to point to our config file.
# CMD ["odoo", "-c", "/etc/odoo/odoo.conf"]

# syntax=docker/dockerfile:1.6
#
# Custom Odoo 19 image limited to core modules + mounted custom addons.
#
# Apps-menu lockdown is enforced after bootstrap by entrypoint.sh applying
# lock_modules.sql. Do not physically delete bundled addons before base
# initialization; Odoo 19's base metadata references many bundled module records.
#
FROM odoo:19.0

LABEL maintainer="ZenCore DevOps <devops@zencore.local>"
LABEL org.opencontainers.image.title="odoo19-custom"
LABEL org.opencontainers.image.description="Odoo 19 limited to Core + HR + custom addons"

USER root

# ── 1. Build-time whitelist generation ───────────────────────────────────────
#
# prune_addons.py writes /opt/odoo-whitelist.txt — a canonical source of truth
# that entrypoint.sh later combines with custom addons and injects into SQL.
COPY scripts/prune_addons.py /tmp/prune_addons.py
RUN python3 /tmp/prune_addons.py \
 && rm -f /tmp/prune_addons.py

# ── 2. Runtime helpers (entrypoint + SQL lock template) ──────────────────────
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/lock_modules.sql /opt/lock_modules.sql
RUN chmod +x /usr/local/bin/entrypoint.sh

# ── 3. Required runtime dirs ─────────────────────────────────────────────────
RUN mkdir -p /mnt/extra-addons /var/log/odoo \
 && chown -R odoo:odoo /mnt/extra-addons /var/log/odoo /opt/odoo-whitelist.txt /opt/lock_modules.sql

# ── 4. Install curl (healthcheck) + postgresql-client (entrypoint psql/pg_isready) ──
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl postgresql-client \
 && rm -rf /var/lib/apt/lists/*

USER odoo

EXPOSE 8069 8072

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["odoo", "-c", "/etc/odoo/odoo.conf"]
