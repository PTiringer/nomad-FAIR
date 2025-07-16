from dataclasses import asdict, is_dataclass

from temporalio import workflow
from temporalio.worker import (
    ExecuteWorkflowInput,
    Interceptor,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
)

with workflow.unsafe.imports_passed_through():
    from nomad.workflows.activities import update_process_failure


class _NomadWorkflowInterceptor(WorkflowInboundInterceptor):
    async def execute_workflow(self, input: ExecuteWorkflowInput):
        workflow_info = workflow.info()
        try:
            return await super().execute_workflow(input)
        except Exception as e:
            if not workflow.unsafe.is_replaying():
                with workflow.unsafe.sandbox_unrestricted():
                    if len(input.args) == 1 and is_dataclass(input.args[0]):
                        update_process_failure(
                            workflow_info.workflow_type,
                            asdict(input.args[0]),  # type: ignore
                            e,  # type: ignore
                        )
            raise e


class NomadTemporalInterceptor(Interceptor):
    def workflow_interceptor_class(
        self, input: WorkflowInterceptorClassInput
    ) -> type[WorkflowInboundInterceptor] | None:
        return _NomadWorkflowInterceptor
