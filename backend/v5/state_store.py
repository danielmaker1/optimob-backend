# ==========================================
# TEMPORARY IN-MEMORY STATE STORE
# ------------------------------------------
# This is a temporary persistence mechanism
# to allow demo and operational loop closure.
# In production this must be replaced by
# a real database (PostgreSQL, etc.).
#
# IMPORTANT:
# This in-memory store is volatile and will
# reset if the service restarts. Replace with
# persistent storage in production.
# ==========================================

IN_MEMORY_VALIDATIONS = {}
