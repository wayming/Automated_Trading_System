from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> bool:
        if key not in self.cache:
            return False
        self.cache.move_to_end(key)
        return True

    def put(self, key: str) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
            self.cache[key] = True

    def __len__(self):
        return len(self.cache)
