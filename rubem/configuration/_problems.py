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
    """

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = list(problems)
        blocking = [problem for problem in self.problems if problem.blocking]
        lines = [f"The configuration has {len(blocking)} blocking problem(s):"]
        lines.extend(f"- {problem}" for problem in blocking)
        super().__init__("\n".join(lines))
