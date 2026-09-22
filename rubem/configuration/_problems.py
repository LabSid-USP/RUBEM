"""Configuration problems reported by the input models."""

from pydantic import BaseModel, ConfigDict


class Problem(BaseModel):
    """A problem found while validating the configuration.

    :param description: What was checked.
    :param reason: Why the check failed.
    :param implication: What the failure means for a run.
    :param file: The file the problem refers to, if any.
    :param blocking: Whether the simulation must not run with this problem.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str
    reason: str
    implication: str = ""
    file: str | None = None
    blocking: bool = False

    def __str__(self) -> str:
        parts = [f"{self.description}: {self.reason}"]
        if self.implication:
            parts.append(self.implication)
        if self.file:
            parts.append(self.file)
        return " ".join(parts)


class ConfigurationError(ValueError):
    """Raised when a configuration carries blocking problems.

    :param problems: The problems found; the blocking ones are listed in the message.
    :ivar problems: The problems the constructor was given, blocking or not.
    :vartype problems: list[Problem]
    """

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = list(problems)
        blocking = [problem for problem in self.problems if problem.blocking]
        lines = [f"The configuration has {len(blocking)} blocking problem(s):"]
        lines.extend(f"- {problem}" for problem in blocking)
        super().__init__("\n".join(lines))

    def __reduce__(self) -> tuple:
        """Rebuild the exception from its problems, not from its message.

        ``BaseException`` pickles itself through ``args``, which here is the
        formatted message: unpickling would call the constructor with a string
        and fail. Rebuilding from :attr:`problems` (each a pydantic model,
        itself picklable) keeps the exception crossing a process boundary as
        itself, with its problems intact. The instance dictionary travels as
        the pickle state, so notes added to the exception survive as well.
        """
        return (type(self), (self.problems,), self.__dict__)
