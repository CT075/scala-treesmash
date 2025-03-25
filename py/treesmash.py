import itertools as it
from collections.abc import Iterator
import time
import re

from errors import Error, make_error
from util import Peekable, peek

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
ERROR_PREFIX_RE = re.compile(r"\[error\] -- Error: (/(?:[a-zA-Z0-9.]+/?)*):(\d+):\d+")
ERROR_MSG_RE = re.compile(r"\[error\] +\|(.*)")


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
