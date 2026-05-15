# Deprecated: use backend.components.task_artifact instead.
# Shim kept during the DisplayFrame → TaskArtifact rename migration.
from backend.components.task_artifact import TaskArtifact as DisplayFrame, BuildingBlock  # noqa: F401
