"""Domain exceptions for the agent platform."""


class ToolNotFoundError(Exception):
    pass


class ToolAlreadyExistsError(Exception):
    pass


class AgentNotFoundError(Exception):
    pass


class AgentAlreadyExistsError(Exception):
    pass
