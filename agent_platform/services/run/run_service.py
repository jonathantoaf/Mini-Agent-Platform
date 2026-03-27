import logging

from agent_platform.data_models.run import (
    ChatMessage,
    RunRequest,
    RunResponse,
    ToolCallRecord,
)
from agent_platform.db.models.execution import Execution
from agent_platform.exceptions import (
    AgentNotFoundError,
    InvalidModelError,
    MaxIterationsError,
    ToolNotAssignedError,
)
from agent_platform.repositories.agent_repository import AgentRepository
from agent_platform.repositories.execution_repository import ExecutionRepository
from agent_platform.services.run.guardrail import PromptInjectionGuardrail
from agent_platform.services.run.mock_llm import MockLlmAdapter
from agent_platform.services.run.mock_tool_executor import MockToolExecutor
from agent_platform.services.run.prompt_builder import PromptBuilder


class RunService:
    def __init__(  # noqa: PLR0913
        self,
        agent_repo: AgentRepository,
        execution_repo: ExecutionRepository,
        guardrail: PromptInjectionGuardrail,
        llm: MockLlmAdapter,
        tool_executor: MockToolExecutor,
        prompt_builder: PromptBuilder,
        allowed_models: list[str],
        max_iterations: int,
    ) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._agent_repo = agent_repo
        self._execution_repo = execution_repo
        self._guardrail = guardrail
        self._llm = llm
        self._tool_executor = tool_executor
        self._prompt_builder = prompt_builder
        self._allowed_models = allowed_models
        self._max_iterations = max_iterations

    async def run_agent(self, tenant_id: str, agent_id: str, data: RunRequest) -> RunResponse:
        # 1. Validate model
        if data.model not in self._allowed_models:
            self._logger.warning(f"Invalid model requested model={data.model}")
            raise InvalidModelError

        # 2. Load agent
        agent = await self._agent_repo.get_by_id(tenant_id, agent_id)
        if not agent:
            self._logger.warning(f"Agent not found tenant_id={tenant_id} agent_id={agent_id}")
            raise AgentNotFoundError

        # 3. Run guardrail
        self._guardrail.check(data.task)

        # 4. Build initial messages and tools
        messages = self._prompt_builder.build_messages(agent, data.task)
        tools = self._prompt_builder.build_tools(agent)
        assigned_tool_names = {tool.name for tool in agent.tools}
        tool_calls_log: list[ToolCallRecord] = []

        # 5. Execution loop
        completed = False
        for iteration in range(self._max_iterations):
            assistant_msg = self._llm.complete(messages, tools)
            messages.append(assistant_msg)

            # No tool calls → final response
            if not assistant_msg.tool_calls:
                completed = True
                break

            # Process tool calls
            for tool_call in assistant_msg.tool_calls:
                tool_name = tool_call.function.name

                # Validate tool is assigned to agent
                if tool_name not in assigned_tool_names:
                    self._logger.warning(
                        f"Tool not assigned to agent tool={tool_name} agent_id={agent_id}"
                    )
                    raise ToolNotAssignedError

                # Execute mock tool
                result = self._tool_executor.execute(tool_name, tool_call.function.arguments)

                # Append tool result to messages
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id,
                    )
                )

                # Record tool call
                tool_calls_log.append(
                    ToolCallRecord(
                        tool_call_id=tool_call.id,
                        tool_name=tool_name,
                        arguments=tool_call.function.arguments,
                        result=result,
                    )
                )

            self._logger.debug(
                f"Execution loop iteration={iteration} agent_id={agent_id} "
                f"tool_calls={len(assistant_msg.tool_calls)}"
            )

        if not completed:
            self._logger.warning(
                f"Max iterations reached agent_id={agent_id} max={self._max_iterations}"
            )
            raise MaxIterationsError

        # Extract final response
        final_response = assistant_msg.content or ""

        # 6. Store execution record
        messages_json = [msg.model_dump(mode="json", exclude_none=True) for msg in messages]
        tool_calls_json = [tc.model_dump(mode="json") for tc in tool_calls_log]

        execution = Execution(
            tenant_id=tenant_id,
            agent_id=agent_id,
            task=data.task,
            model=data.model,
            messages=messages_json,
            tool_calls=tool_calls_json,
            final_response=final_response,
        )
        execution = await self._execution_repo.create(execution)

        self._logger.info(
            f"Agent run completed tenant_id={tenant_id} agent_id={agent_id} "
            f"execution_id={execution.id} tool_calls={len(tool_calls_log)}"
        )

        # 7. Return response
        return RunResponse(
            execution_id=execution.id,
            agent_id=agent_id,
            task=data.task,
            model=data.model,
            final_response=final_response,
            tool_calls=tool_calls_log,
            messages=messages,
            created_at=execution.created_at,
        )
