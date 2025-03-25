from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Tuple, Callable, Any
from util import is_prefix


known_errors = []


@dataclass
class Error(ABC):
    filepath: str
    row: int
    colspan: Tuple[int, int]

    @abstractmethod
    def resolve(self, file: list[str]) -> bool: ...


def register_error(
    pred: Callable[[str], bool],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def inner[T](
        x: Callable[[str, int, Tuple[int, int]], T],
    ) -> Callable[[str, int, Tuple[int, int]], T]:
        known_errors.append((pred, x))
        return x

    return inner


def make_error(filepath: str, msg: str, row: int, colspan: Tuple[int, int]) -> Error:
    for pred, wrapper in known_errors:
        if pred(msg):
            return wrapper(filepath, row, colspan)
    return GenericError(filepath, row, colspan)


class GenericError(Error):
    def resolve(self, file: list[str]) -> bool:
        # shut up about unused param
        _ = file
        return False


@register_error(is_prefix("Context bounds will map to context parameters"))
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


@register_error(is_prefix("value m needs result type"))
class UnmarkedManifest(Error):
    def resolve(self, file: list[str]) -> bool:
        line = file[self.row - 1]
        ty = line[self.colspan[1]]

        file[self.row - 1] = line.replace(
            "ManifestTyp(m)", f"ManifestTyp(m: Manifest[{ty}])"
        )

        return True


def uninfix(name: str):
    @register_error(is_prefix(f"value {name} is not a member"))
    class _(Error):
        def resolve(self, file: list[str]) -> bool:
            line = file[self.row - 1]
            exp = line[self.colspan[0]:self.colspan[1]-len(name)-1]

            file[self.row-1] = line.replace(f"{exp}.{name}", f"infix_{name}({exp})")
            return True

for name in ["lhs", "star"]:
    uninfix(name)
