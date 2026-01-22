from enum import Enum


class TaskQueue(str, Enum):
    CPU = 'cpu-task-queue'
    GPU = 'gpu-task-queue'
    NOMAD_INTERNAL_WORKFLOWS = 'nomad-internal-workflows-task-queue'
