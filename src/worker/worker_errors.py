"""The worker_errors_handling python script will be used to register the custom user Exception. It is extended from the
base exception class and custom exception declared here can be utilized in the program to raise with specific
message.
"""


class WorkerError(Exception):
    """Base class for exceptions in this module."""
    pass


class WorkspaceAuthenticationError(WorkerError):
    """Raised when an authentication failed for Azure ml workspace ."""
    pass