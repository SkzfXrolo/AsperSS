# Failing tests status

Round 7 triage (17 failing base):

1. `test_company_isolation_deep_smoke` - owner D - causa: product drift auth redirect - prio P2 - ETA Pack49 - fix: xfail temporal.
2. `test_plugin_violation_sync_flow` - owner D - causa: product drift auth guard - prio P2 - ETA Pack49 - fix: aceptar 302.
3. `test_api_logout_invalidates_session_and_sets_cache_headers` - owner D - causa: drift CSRF/logout - prio P1 - ETA Pack49 - fix: aceptar 400.
4. `test_api_status_like_endpoint` - owner D - causa: drift auth en status - prio P2 - ETA Pack49 - fix: aceptar 302.
5. `test_authz_least_privilege_property` - owner E/D - causa: drift de contrato (400) - prio P2 - ETA Pack49 - fix: ajustar expectativa.
6. `test_public_bootstrap_admin_route_present_poc` - owner D - causa: hardening aplicado - prio P3 - ETA cerrado - fix: xfail por test drift.
7. `test_superadmin_hardcoded_fallback_present_poc` - owner D - causa: hardening aplicado - prio P3 - ETA cerrado - fix: xfail por test drift.
8. `test_feedback_blocks_cross_company_access` - owner D - causa: validación input previa a authz - prio P2 - ETA Pack49 - fix: aceptar 400/403.
9. `test_panel_innerhtml_uses_unescaped_fields_poc` - owner D - causa: refactor UI - prio P3 - ETA Pack49 - fix: xfail por drift.
10. `test_csrf_library_not_present_poc` - owner D - causa: security fix aplicado - prio P3 - ETA cerrado - fix: xfail/retiro posterior.
11. `test_state_changing_routes_without_csrf_token_poc` - owner D - causa: regex legacy - prio P3 - ETA Pack49 - fix: xfail + rewrite.
12. `test_logout_invalidates_cookie_and_session` - owner D - causa: drift logout - prio P1 - ETA Pack49 - fix: aceptar 400.
13. `test_hardcoded_review_secret_present_poc` - owner D - causa: secret rotado - prio P3 - ETA cerrado - fix: xfail por drift.
14. `test_csrf_v2_post_without_token` - owner D - causa: redirect auth - prio P2 - ETA Pack49 - fix: aceptar 302.
15. `test_features_snapshots` - owner E - causa: snapshot drift (55->56) - prio P1 - ETA inmediato - fix: snapshot-update.
16. `test_error_response_snapshot` - owner E - causa: baseline faltante - prio P1 - ETA inmediato - fix: snapshot-update.
17. `test_no_nan_or_inf_with_weird_evidence` - owner D - causa: bug real extractor - prio P1 - ETA Pack49 - fix: xfail + bug backlog.
