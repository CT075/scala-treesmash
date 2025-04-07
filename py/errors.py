from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Tuple, Callable, Any
from util import is_prefix, matches_regex, rmatch_paren
import itertools as it
import re


known_errors = []


@dataclass
class Error(ABC):
    filepath: str
    msg: str
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
            return wrapper(filepath, msg, row, colspan)
    return GenericError(filepath, msg, row, colspan)


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


def unmarked_manifest(name: str):
    @register_error(is_prefix(f"value {name} needs result type"))
    class _(Error):
        def resolve(self, file: list[str]) -> bool:
            line = file[self.row - 1]
            ty = line[self.colspan[1]]

            if f"ManifestTyp({name})" not in line:
                return False

            file[self.row - 1] = line.replace(
                f"ManifestTyp({name})", f"ManifestTyp({name}: Manifest[{ty}])"
            )

            return True


for name in ["m", "mA", "mB", "mC", "mD", "mE"]:
    unmarked_manifest(name)


def uninfix(name: str):
    @register_error(is_prefix(f"value {name} is not a member"))
    class _(Error):
        def resolve(self, file: list[str]) -> bool:
            line = file[self.row - 1]
            exp = line[self.colspan[0] : self.colspan[1] - len(name) - 1]

            file[self.row - 1] = line.replace(f"{exp}.{name}", f"infix_{name}({exp})")

            return file[self.row - 1] != line


for name in ["lhs", "rhs", "star"]:
    uninfix(name)


@register_error(
    is_prefix("missing argument for parameter x of method apply in object Const")
)
class UnitConst(Error):
    def resolve(self, file: list[str]) -> bool:
        line = file[self.row - 1]
        file[self.row - 1] = line.replace("Const()", "Const(())")

        return file[self.row - 1] != line


TYP_INSTANCE_REGEX = re.compile(r"No given instance of type .*Typ\[(.*)\] was found")


@register_error(matches_regex(TYP_INSTANCE_REGEX))
class TypInstance(Error):
    def resolve(self, file: list[str]) -> bool:
        line = file[self.row - 1]

        m = TYP_INSTANCE_REGEX.match(self.msg)
        if m is None:
            return False

        typename = "".join(it.takewhile(lambda x: x != "$", m.group(1)))
        # This doesn't account for calls split across lines, but we can fix those by hand.
        loc = rmatch_paren(line, self.colspan[0] - 1)

        if loc is None:
            return False

        file[self.row - 1] = line[:loc] + f"[{typename}]" + line[loc:]

        return True
