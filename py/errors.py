from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Tuple, Callable, Any


known_errors = dict()


@dataclass
class Error(ABC):
    filepath: str
    row: int
    colspan: Tuple[int, int]

    @abstractmethod
    def resolve(self, file: list[str]) -> bool: ...


def register_error(prefix: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def inner[T](
        x: Callable[[str, int, Tuple[int, int]], T],
    ) -> Callable[[str, int, Tuple[int, int]], T]:
        known_errors[prefix] = x
        return x

    return inner


def make_error(filepath: str, msg: str, row: int, colspan: Tuple[int, int]) -> Error:
    for prefix, wrapper in known_errors.items():
        if msg.startswith(prefix):
            return wrapper(filepath, row, colspan)
    return GenericError(filepath, row, colspan)


class GenericError(Error):
    def resolve(self, file: list[str]) -> bool:
        # shut up about unused param
        _ = file
        return False


@register_error("Context bounds will map to context parameters")
class ContextBoundError(Error):
    def resolve(self, file: list[str]) -> bool:
        line = file[self.row - 1]

        if self.colspan[1] < len(line):
            if not line[self.colspan[1] + 1 :].startswith("using"):
                file[self.row - 1] = (
                    line[: self.colspan[1] + 1] + "using " + line[self.colspan[1] + 1 :]
                )
                return True
        return False
