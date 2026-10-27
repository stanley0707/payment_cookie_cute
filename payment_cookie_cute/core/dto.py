from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, RootModel


class BaseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    def __getitem__(self, key: str):
        return getattr(self, key, None)


T = TypeVar("T", bound=BaseDto)


class BaseListDto(RootModel[list[T]], Generic[T]):
    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, index: int) -> T:
        return self.root[index]

    def __len__(self) -> int:
        return len(self.root)
