from dataclasses import dataclass,asdict
@dataclass
class Item:
    name: str
    price: int
print(asdict(Item("book",20)))
