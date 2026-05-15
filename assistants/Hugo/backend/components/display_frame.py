# Deprecated: use backend.components.task_artifact instead.
# This shim exists only during the DisplayFrame → TaskArtifact rename migration.
# All callers are being updated; this file will be removed once no imports remain.
from backend.components.task_artifact import TaskArtifact as DisplayFrame, BuildingBlock  # noqa: F401
