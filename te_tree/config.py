import json
import dataclasses
import os

from .core.attributes import Currency_Code, Locale_Code  # type: ignore


@dataclasses.dataclass(frozen=True)
class AppConfig:
    application_name: str
    localization: Locale_Code
    allow_item_name_duplicates: bool
    currency: Currency_Code
    editor_precision: int = dataclasses.field()
    show_trailing_zeros: bool
    use_thousands_separator: bool

    def __post_init__(self) -> None:
        if not self.application_name:
            raise AppConfig.ConfigurationError("Application name is empty.")
        if self.currency not in Currency_Code.__args__:
            raise AppConfig.ConfigurationError(
                f"Unknown currency code: {self.currency}. Allowed codes are: {Currency_Code.__args__}"
            )
        if self.localization not in Locale_Code.__args__:
            raise AppConfig.ConfigurationError(
                f"Unknown locale code: {self.localization}. Allowed codes are: {Locale_Code.__args__}"
            )
        if self.editor_precision < 0:
            raise AppConfig.ConfigurationError(
                f"Invalid precision value: {self.localization}. It must be non-negative integer"
            )

    class ConfigurationError(Exception):
        pass


def load_config(path: str) -> AppConfig | None:
    abs_path = os.path.abspath(path)
    try:
        with open(abs_path) as c:
            config_dict = json.load(c)
            return AppConfig(**config_dict)
    except FileNotFoundError:
        print(f"Configuration file was not found on path {abs_path}.")
        return None
    except Exception as e:
        print(f"Error when loading a configuration file: {e}")
        return None
