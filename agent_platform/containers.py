import logging.config

from dependency_injector import containers, providers

from agent_platform.db.session import Database


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
