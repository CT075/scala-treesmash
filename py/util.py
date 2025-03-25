from collections.abc import Iterator
from typing import Optional


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
