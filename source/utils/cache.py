from __future__ import annotations

from collections import OrderedDict


class LRUCache:
    def __init__(self, max_size=256):
        self.max_size = max_size
        self._data = OrderedDict()

    def get(self, key, default=None):
        if key not in self._data:
            return default
        value = self._data.pop(key)
        self._data[key] = value
        return value

    def set(self, key, value):
        if key in self._data:
            self._data.pop(key)
        self._data[key] = value
        if len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def __len__(self):
        return len(self._data)

