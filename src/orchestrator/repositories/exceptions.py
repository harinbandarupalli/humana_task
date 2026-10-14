"""Custom exceptions for repository operations."""


class RepositoryError(Exception):
    """Base exception for all repository data access errors."""
    pass


class EntityNotFoundError(RepositoryError):
    """Raised when an expected entity record is not found."""
    pass


class DuplicateEntityError(RepositoryError):
    """Raised when an entity insertion violates uniqueness constraints."""
    pass
