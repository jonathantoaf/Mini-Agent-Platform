import logging.config

from dependency_injector import containers, providers

from agent_platform.db.session import Database
from agent_platform.services.run.guardrail import PromptInjectionGuardrail
from agent_platform.services.run.mock_llm import MockLlmAdapter
from agent_platform.services.run.mock_tool_executor import MockToolExecutor
from agent_platform.services.run.prompt_builder import PromptBuilder


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    logging = providers.Resource(
        logging.config.dictConfig,
        config=config.logging,
    )

    db = providers.Singleton(
        Database,
        db_url=config.database_url,
        pool_size=config.database_pool_size,
        max_overflow=config.database_max_overflow,
        debug=config.debug,
    )

    guardrail = providers.Singleton(PromptInjectionGuardrail)
    prompt_builder = providers.Singleton(PromptBuilder)
    mock_llm = providers.Singleton(MockLlmAdapter)
    mock_tool_executor = providers.Singleton(MockToolExecutor)
