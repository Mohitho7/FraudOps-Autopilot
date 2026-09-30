"""FraudOps backend application package.

Ownership
---------
This package root is shared. Each member owns their own sub-package:

* Member 1 (Core Fraud Engine + Backend) owns ``app.api``, ``app.core``,
  ``app.models``, ``app.rules`` and ``app.main``.
* Member 2 (Agentic Investigation System) owns ``app.agents`` plus the
  investigation contract schemas in ``app.schemas`` and
  ``app.services.investigation_service``.
* Member 3 (Frontend) does not own backend modules.
* Member 4 (Database + AWS + Integration) owns migrations, persistence
  infrastructure and notification delivery.

This file intentionally contains no imports so that the package root can be
created by several members without merge conflicts.
"""
