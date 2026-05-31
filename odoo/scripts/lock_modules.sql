-- ============================================================================
-- lock_modules.sql
-- ----------------------------------------------------------------------------
-- Runs ONCE on first boot, AFTER Odoo has initialized `base` and populated
-- `ir.module.module` from the (already-pruned) filesystem.
--
-- Purpose: This is the second half of the "only-whitelisted-apps" fix.
--
--   * Filesystem prune (build time) ensures Odoo's scanner *cannot* discover
--     non-whitelisted modules at boot, so they won't be inserted into
--     ir.module.module on a FRESH DB.
--
--   * This SQL is a DEFENSE-IN-DEPTH lock: if anyone ever drops a stray
--     addon into /mnt/extra-addons (or restores an old DB), this guarantees
--     that ANY module not in the whitelist is:
--         - forced to state = 'uninstallable'   (hidden from Apps menu)
--         - application = false                  (won't show on the apps tab)
--         - auto_install = false                 (won't be picked up by deps)
--
-- The whitelist below MUST be kept in sync with scripts/prune_addons.py.
-- entrypoint.sh reads /opt/odoo-whitelist.txt and substitutes it into this
-- template using psql `\set` / `IN (...)` at runtime.
-- ============================================================================

BEGIN;

-- 1. Hide every non-whitelisted module from the Apps menu, including modules
--    that were installed as dependencies during bootstrap.
UPDATE ir_module_module
   SET application  = FALSE,
       auto_install = FALSE
 WHERE name NOT IN (__WHITELIST_PLACEHOLDER__);

-- 2. Force every non-whitelisted, not-yet-installed module into
--    'uninstallable' state.
--    Odoo's Apps menu hides rows in state = 'uninstallable'.
UPDATE ir_module_module
   SET state = 'uninstallable'
 WHERE name NOT IN (__WHITELIST_PLACEHOLDER__)
   AND state IN ('uninstalled', 'to install', 'to upgrade');

-- 3. Belt-and-braces: if any non-whitelisted module is somehow already
--    installed (e.g. legacy DB), mark it 'to remove' so the next
--    -u all run cleans it up. We DO NOT auto-uninstall here because that
--    can break data; flag it for the admin to action.
-- (Intentionally commented out by default — uncomment if you want hard
-- uninstall of pre-existing non-whitelisted modules.)
--
-- UPDATE ir_module_module
--    SET state = 'to remove'
--  WHERE name NOT IN (__WHITELIST_PLACEHOLDER__)
--    AND state = 'installed';

-- 4. Audit log: count locked vs visible apps
DO $$
DECLARE
    locked_count   INT;
    visible_count  INT;
BEGIN
    SELECT COUNT(*) INTO locked_count
      FROM ir_module_module
     WHERE state = 'uninstallable';

    SELECT COUNT(*) INTO visible_count
      FROM ir_module_module
     WHERE state <> 'uninstallable'
       AND application IS TRUE;

    RAISE NOTICE '[lock_modules] uninstallable (hidden): %', locked_count;
    RAISE NOTICE '[lock_modules] visible apps          : %', visible_count;
END $$;

COMMIT;
