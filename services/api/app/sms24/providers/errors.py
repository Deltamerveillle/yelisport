"""Safe provider failures shared by SMS24 adapters and runners."""


class ProviderAccessRestrictedError(RuntimeError):
    """The requested capability is unavailable; contains no upstream details."""

    code = "provider_access_restricted"

    def __init__(self) -> None:
        super().__init__(self.code)
