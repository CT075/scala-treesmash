from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Callable, Any
import itertools as it
from collections.abc import Iterator
import time
import re

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
ERROR_PREFIX_RE = re.compile(r"\[error\] -- Error: (/(?:[a-zA-Z0-9.]+/?)*):(\d+):\d+")
ERROR_MSG_RE = re.compile(r"\[error\] +\|(.*)")


class Peekable[T]:
    peeked: bool = False
    done: bool = False
    top: T
    inner: Iterator[T]

    def __init__(self, inner: Iterator[T]):
        self.inner = inner

    def __iter__(self):
        return self

    def __next__(self) -> T:
        if self.done:
            raise StopIteration
        if self.peeked:
            self.peeked = False
            result = self.top
            return result
        return next(self.inner)

    def peek(self) -> Optional[T]:
        if self.done:
            return None
        if self.peeked:
            return self.top

        self.peeked = True
        try:
            self.top = next(self.inner)
            return self.top
        except StopIteration:
            self.done = True
            return None


def peek[T](s: Peekable[T]) -> Optional[T]:
    return s.peek()


@dataclass
class Error(ABC):
    filepath: str
    row: int
    colspan: Tuple[int, int]

    @abstractmethod
    def resolve(self, file: list[str]) -> bool:
        ...


known_errors = dict()

def register_error(prefix: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def inner[T](x: Callable[[str, int, Tuple[int, int]], T]) -> Callable[[str, int, Tuple[int, int]], T]:
        known_errors[prefix] = x
        return x
    return inner


def make_error(filepath: str, msg: str, row: int, colspan: Tuple[int, int]) -> Error:
    for prefix, wrapper in known_errors.items():
        if msg.startswith(prefix):
            return wrapper(filepath, row, colspan)
    return GenericError(filepath, row, colspan)


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


class GenericError(Error):
    def resolve(self, file: list[str]) -> bool:
        return False


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def parse_errors(stream: Peekable[str]) -> Iterator[Error]:
    try:
        while True:
            while True:
                header = next(stream)
                h = ERROR_PREFIX_RE.match(header)
                if h:
                    break

            path = h.group(1)
            row = int(h.group(2))

            # discard line showing visual error
            next(stream)

            # line with error highlight
            hl = next(stream)
            hl = "".join(it.dropwhile(lambda c: c != "|", hl))[1:]
            colspan = (hl.index("^"), hl.rindex("^") + 1)

            msg = []
            while True:
                line = peek(stream)
                if line is None:
                    break
                m = ERROR_MSG_RE.match(line)
                if not m:
                    break
                next(stream)
                msg.append(m.group(1))

            yield make_error(path, "\n".join(msg), row, colspan)
    except StopIteration:
        return


class FileMap:
    cache: dict[str, list[str]]

    def __getitem__(self, fname: str) -> list[str]:
        if fname not in self.cache:
            with open(fname) as f:
                lines = f.readlines()
            self.cache[fname] = lines
        return self.cache[fname]

    def __init__(self):
        self.cache = dict()

    def writeback(self):
        for path, lines in self.cache.items():
            with open(path, "w") as f:
                for line in lines:
                    print(line, file=f, end="")


def main(path: str, delay: int):
    while True:
        count = 0
        with open(path) as f:
            log = strip_ansi(f.read()).splitlines()
        stream = Peekable(iter(log))

        errors = list(parse_errors(stream))

        files = FileMap()
        for err in errors:
            file = files[err.filepath]
            if err.resolve(file):
                count += 1
        files.writeback()
        print(f"resolved {count} errors")
        if not count:
            break
        time.sleep(delay)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep", default=15, type=int)
    parser.add_argument("file")
    args = parser.parse_args()
    main(args.file, args.sleep)
